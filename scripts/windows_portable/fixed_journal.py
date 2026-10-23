"""Versioned fixed-inode two-slot journal; integrity is never DDL authority."""
import hashlib
import json
import struct

from .directories import LeaseRefused, NEXT, PHASES, _pairs

SLOT = 4096
SIZE = 2 * SLOT
BODY_LIMIT = 3072
SCHEMA = 'parkweave-directory-fixed/1'
HEADER = struct.Struct('<8sIIQQI32s32s28s')
ZERO_HASH = bytes(32)


def encode(record):
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    if not 0 < len(raw) <= BODY_LIMIT: raise LeaseRefused('FIXED_BODY_LIMIT')
    return raw


def decode(raw):
    if not 0 < len(raw) <= BODY_LIMIT: raise LeaseRefused('FIXED_BODY_LIMIT')
    try: record = json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError): raise LeaseRefused('FIXED_BODY_INVALID') from None
    keys = {'schema', 'root', 'lock', 'journal', 'generation', 'sequence', 'phase', 'initialized', 'runtime', 'handoff'}
    if (type(record) is not dict or set(record) != keys or record['schema'] != SCHEMA
            or any(type(record[k]) is not int or not 1 <= record[k] < 2**64 for k in ('generation', 'sequence'))
            or any(type(record[k]) is not list or len(record[k]) != 2 or
                   any(type(n) is not int or not 0 <= n < 2**64 for n in record[k]) for k in ('root', 'lock', 'journal'))
            or type(record['phase']) is not str or record['phase'] not in PHASES
            or type(record['initialized']) is not bool or type(record['runtime']) is not str
            or type(record['handoff']) is not str or record['handoff'] not in ('OWNED', 'RELEASE_PENDING')
            or encode(record) != raw):
        raise LeaseRefused('FIXED_BODY_INVALID')
    phase, initialized, runtime = record['phase'], record['initialized'], record['runtime']
    if phase == 'NEW': valid = not initialized and runtime == 'STOPPED'
    elif phase == 'UNKNOWN': valid = runtime == 'UNKNOWN'
    elif phase in ('READY', 'APPLICATION', 'RUNNING', 'READY_STOPPED'):
        valid = initialized and runtime == ('RUNNING' if phase == 'RUNNING' else 'STARTING' if phase == 'APPLICATION' else 'STOPPED')
    else:
        valid = runtime == 'STARTING' and (not initialized or phase in ('CLUSTER', 'VERIFY_DATABASE'))
    if not valid: raise LeaseRefused('FIXED_STATE_INVALID')
    return record


def transition(old, new):
    """Every linked pair must be an original phase transition or handoff."""
    if (new['sequence'] != old['sequence'] + 1 or
            any(new[k] != old[k] for k in ('schema', 'root', 'lock', 'journal'))):
        raise LeaseRefused('FIXED_TRANSITION_INVALID')
    business = ('phase', 'initialized', 'runtime')
    if new['generation'] == old['generation'] + 1:
        valid = (old['phase'] == 'READY_STOPPED' and old['initialized'] and old['runtime'] == 'STOPPED'
                 and old['handoff'] == 'RELEASE_PENDING' and new['handoff'] == 'OWNED'
                 and all(new[k] == old[k] for k in business))
    elif new['generation'] == old['generation']:
        if old['generation'] == 1 and old['sequence'] == 1 and new['sequence'] == 2:
            valid = (old['phase'] == 'NEW' and old['handoff'] == 'OWNED' and new == {**old, 'sequence': 2})
        elif old['handoff'] != 'OWNED': valid = False
        elif new['handoff'] == 'RELEASE_PENDING':
            valid = all(new[k] == old[k] for k in business)
        elif new['phase'] == 'UNKNOWN': valid = new['initialized'] == old['initialized']
        else:
            expected = ('VERIFY_DATABASE' if old['initialized'] else 'CREATE_SCHEMA') if old['phase'] == 'CLUSTER' else NEXT.get(old['phase'])
            valid = (old['phase'] != 'UNKNOWN' and new['handoff'] == 'OWNED' and new['phase'] == expected
                     and (new['initialized'] == old['initialized'] or new['phase'] == 'READY' and new['initialized']))
    else: valid = False
    if not valid: raise LeaseRefused('FIXED_TRANSITION_INVALID')


def slot_bytes(record, index, previous_hash):
    raw = encode(record); decode(raw)
    header = HEADER.pack(b'PWLJv001', 1, index, record['generation'], record['sequence'], len(raw),
                         hashlib.sha256(raw).digest(), previous_hash, bytes(28))
    return header + raw + bytes(SLOT - 256 - len(raw)) + header


def parse_slot(raw, index):
    if len(raw) != SLOT: raise LeaseRefused('FIXED_SLOT_SHORT_READ')
    head = raw[:128]
    if head != raw[-128:]: raise LeaseRefused('FIXED_SLOT_TORN')
    magic, version, slot, generation, sequence, length, digest, previous, reserved = HEADER.unpack(head)
    if (magic != b'PWLJv001' or version != 1 or slot != index or reserved != bytes(28)
            or not 0 < length <= BODY_LIMIT or (sequence - 1) % 2 != index
            or any(raw[128 + length:-128])):
        raise LeaseRefused('FIXED_SLOT_INVALID')
    body = raw[128:128 + length]
    if hashlib.sha256(body).digest() != digest: raise LeaseRefused('FIXED_SLOT_HASH')
    record = decode(body)
    if record['generation'] != generation or record['sequence'] != sequence:
        raise LeaseRefused('FIXED_SLOT_COUNTS')
    return record, previous


def pair(raw):
    if len(raw) != SIZE: raise LeaseRefused('FIXED_FILE_LENGTH')
    slots = [raw[:SLOT], raw[SLOT:]]
    parsed = [parse_slot(value, index) for index, value in enumerate(slots)]  # BOTH required.
    order = sorted(range(2), key=lambda index: parsed[index][0]['sequence'])
    older, newer = order
    old, new = parsed[older][0], parsed[newer][0]
    if parsed[newer][1] != hashlib.sha256(slots[older]).digest(): raise LeaseRefused('FIXED_CHAIN_INVALID')
    if old['sequence'] == 1 and parsed[older][1] != ZERO_HASH: raise LeaseRefused('FIXED_GENESIS_INVALID')
    transition(old, new)
    return new, newer


class FixedJournal:
    """IO owns the held file. No rename, name repair, retries or slot fallback."""
    def __init__(self, io): self.io = io

    def read(self):
        self.io.verify()
        before = self.io.signature()
        if self.io.length() != SIZE: raise LeaseRefused('FIXED_FILE_LENGTH')
        raw = self.io.read_at(0, SLOT) + self.io.read_at(SLOT, SLOT)
        if before != self.io.signature(): raise LeaseRefused('FIXED_CHANGED_DURING_READ')
        record, _ = pair(raw)
        if record['journal'] != self.io.identity() or record['root'] != self.io.root_id or record['lock'] != self.io.lock_id:
            raise LeaseRefused('FIXED_FILE_BINDING')
        self.io.verify()
        return encode(record), raw

    def write(self, raw, expected):
        proposed = decode(raw)
        self.io.verify()
        if proposed['journal'] != self.io.identity() or proposed['root'] != self.io.root_id or proposed['lock'] != self.io.lock_id:
            raise LeaseRefused('FIXED_FILE_BINDING')
        if expected is None:
            if self.io.length() != 0 or proposed['generation'] != 1 or proposed['sequence'] != 2:
                raise LeaseRefused('FIXED_INITIALIZATION_REFUSED')
            first = {**proposed, 'sequence': 1}
            first_raw = slot_bytes(first, 0, ZERO_HASH)
            target = first_raw + slot_bytes(proposed, 1, hashlib.sha256(first_raw).digest())
            pair(target)
            offset, pending = 0, target
        else:
            if self.read() != expected: raise LeaseRefused('FIXED_SNAPSHOT_CHANGED')
            old, newest = pair(expected[1]); transition(old, proposed)
            offset = (1 - newest) * SLOT
            pending = slot_bytes(proposed, 1 - newest, hashlib.sha256(expected[1][newest*SLOT:(newest+1)*SLOT]).digest())
            target = expected[1][:offset] + pending + expected[1][offset + SLOT:]
        # A short write is ambiguous. Preserve it, do not finish/retry/recover.
        if self.io.write_at(offset, pending) != len(pending): raise LeaseRefused('FIXED_SHORT_WRITE_UNKNOWN')
        self.io.flush_file()
        actual = self.read()
        if actual != (raw, target): raise LeaseRefused('FIXED_PUBLICATION_UNKNOWN')
        self.io.verify()
        return actual
