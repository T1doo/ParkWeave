"""Canonical plaintext envelope only: no encryption, paths, OS identity or authority.

References must ultimately come from held native capabilities. A caller's SID,
UUID or file-ID tuple here is data, not proof that such a capability exists.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
import re
import struct
from uuid import UUID

from .endpoint_plan import EndpointRefused, validate_record as validate_endpoints


MAX_PLAINTEXT = 16384
MAX_CIPHERTEXT = 65536
PRODUCT = 'ParkWeave'
SCHEMA = 'parkweave-private-envelope/1'


class EnvelopeRefused(ValueError):
    def __init__(self):
        super().__init__('PRIVATE_ENVELOPE_REFUSED')


class Purpose(Enum):
    DATABASE = 'DATABASE'
    SESSION = 'SESSION'
    CONFIG = 'CONFIG'


class ConfigFormat(Enum):
    SCHEMA2 = 2
    INSTANCE_SCHEMA3 = 3
    PGDATA_SCHEMA4 = 4


def need(condition):
    if not condition:
        raise EnvelopeRefused()


def integer(value, maximum):
    need(type(value) is int and 0 < value <= maximum)


def identity(value):
    need(type(value) is tuple and len(value) == 2)
    need(all(type(n) is int and 0 <= n < 2**64 for n in value))
    return value


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys))


def digest(value, length=64):
    need(type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is not None)


def text(value):
    need(type(value) is str and 0 < len(value) <= 512)
    need(not any(ord(c) < 32 or ord(c) == 127 for c in value))
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        raise EnvelopeRefused() from None


@dataclass(frozen=True, repr=False)
class InstanceBinding:
    instance_id: str
    sid: str
    root: tuple
    lock: tuple
    journal: tuple
    product: str = PRODUCT
    version: int = 1

    def record(self):
        need(type(self) is InstanceBinding and type(self.version) is int and self.version == 1)
        need(type(self.product) is str and self.product == PRODUCT)
        need(type(self.instance_id) is str and len(self.instance_id) == 36)
        try:
            need(str(UUID(self.instance_id)) == self.instance_id)
        except (ValueError, AttributeError):
            raise EnvelopeRefused() from None
        need(type(self.sid) is str and len(self.sid) <= 184 and re.fullmatch(r'S-1-(0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}', self.sid) is not None)
        parts = self.sid.split('-')
        need(int(parts[2]) < 2**48 and all(int(n) < 2**32 for n in parts[3:]))
        ids = [identity(v) for v in (self.root, self.lock, self.journal)]
        need(len(set(ids)) == 3 and len({v[0] for v in ids}) == 1)
        return dict(product=self.product, version=self.version, instance_id=self.instance_id,
                    sid=self.sid, root=list(self.root), lock=list(self.lock), journal=list(self.journal))


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    except (TypeError, ValueError, RecursionError):
        raise EnvelopeRefused() from None


def validate_payload(binding, purpose, payload, *, config_format=ConfigFormat.SCHEMA2):
    need(type(binding) is InstanceBinding and type(purpose) is Purpose and type(config_format) is ConfigFormat)
    binding.record()
    if purpose is Purpose.DATABASE:
        exact(payload, ('postgres', 'parkweave_app'))
        for value in payload.values():
            text(value)
    elif purpose is Purpose.SESSION:
        exact(payload, ('fixture-a', 'fixture-b', 'fixture-c'))
        for value in payload.values():
            text(value)
        need(len(set(payload.values())) == 3)
    else:
        # Final CONFIG references DATABASE and SESSION, never its own ciphertext.
        keys=('schema', 'files', 'database', 'runtime')
        if config_format in (ConfigFormat.INSTANCE_SCHEMA3, ConfigFormat.PGDATA_SCHEMA4): keys=keys+('endpoints',)
        if config_format is ConfigFormat.PGDATA_SCHEMA4: keys=keys+('pgdata',)
        exact(payload,keys)
        need(type(payload['schema']) is int and payload['schema'] == config_format.value)
        if config_format in (ConfigFormat.INSTANCE_SCHEMA3, ConfigFormat.PGDATA_SCHEMA4):
            try: validate_endpoints(payload['endpoints'])
            except EndpointRefused: raise EnvelopeRefused() from None
        refs = payload['files']; exact(refs, ('DATABASE', 'SESSION'))
        seen = {binding.root, binding.lock, binding.journal}
        for ref in refs.values():
            exact(ref, ('identity', 'ciphertext_sha256'))
            need(type(ref['identity']) is list)
            file_id = identity(tuple(ref['identity']))
            need(file_id[0] == binding.root[0] and file_id not in seen)
            seen.add(file_id); digest(ref['ciphertext_sha256'])
        db = payload['database']
        exact(db, ('system_identifier', 'database_oid', 'database_name', 'owner', 'data_identity', 'schema_version'))
        need(type(db['system_identifier']) is str and re.fullmatch('[1-9][0-9]{0,19}', db['system_identifier']) is not None)
        need(int(db['system_identifier']) < 2**64)
        integer(db['database_oid'], 2**32-1)
        need(type(db['database_name']) is str and db['database_name'] == 'parkweave')
        need(type(db['owner']) is str and db['owner'] == 'postgres')
        need(type(db['schema_version']) is int and db['schema_version'] == 32)
        need(type(db['data_identity']) is list)
        data_id = identity(tuple(db['data_identity']))
        need(data_id[0] == binding.root[0] and data_id not in seen)
        runtime = payload['runtime']; exact(runtime, ('source_commit', 'manifest_sha256'))
        digest(runtime['source_commit'], 40); digest(runtime['manifest_sha256'])
        if config_format is ConfigFormat.PGDATA_SCHEMA4:
            profile = payload['pgdata']
            exact(profile, ('profile','instance_id','sid','parent_identity','root_identity',
                            'root_control','root_security_sha256'))
            from .pgdata_candidate import PROFILE, root_descriptor, check_descriptor, descriptor_digest
            need(type(profile['profile']) is str and profile['profile'] == PROFILE and
                 type(profile['instance_id']) is str and profile['instance_id'] == binding.instance_id and
                 type(profile['sid']) is str and profile['sid'] == binding.sid)
            for field in ('parent_identity','root_identity'):
                need(type(profile[field]) is list)
                identity(tuple(profile[field]))
            parent = tuple(profile['parent_identity'])
            need(parent[0] == binding.root[0] and parent[1] > 0 and data_id[1] > 0
                 and parent not in seen and parent != data_id
                 and profile['root_identity'] == db['data_identity'])
            # The format pins this one concrete ACL policy, not caller-chosen
            # principals/permissions or a generic 'verified' JSON flag.
            parts = binding.sid.split('-')
            sid = bytes((1, len(parts)-3)) + int(parts[2]).to_bytes(6,'big') + b''.join(
                struct.pack('<I', int(x)) for x in parts[3:])
            descriptor = root_descriptor(sid)
            descriptor = (binding.sid, profile['root_control'], descriptor[20+len(sid):])
            try: check_descriptor(descriptor, sid, root=True, directory=True)
            except RuntimeError: raise EnvelopeRefused() from None
            digest(profile['root_security_sha256'])
            need(profile['root_security_sha256'] == descriptor_digest(descriptor))


def entropy_bytes(binding, purpose):
    need(type(binding) is InstanceBinding and type(purpose) is Purpose)
    return hashlib.sha256(b'ParkWeave/current-user/1\0'+canonical(dict(binding=binding.record(), purpose=purpose.value))).digest()


def encode_plaintext(binding, purpose, payload, *, config_format=ConfigFormat.SCHEMA2):
    """Sensitive return bytes must never be logged or stored as a plaintext file."""
    validate_payload(binding, purpose, payload, config_format=config_format)
    raw = canonical(dict(schema=SCHEMA, binding=binding.record(), purpose=purpose.value,
                         payload=payload, payload_sha256=hashlib.sha256(canonical(payload)).hexdigest()))
    need(0 < len(raw) <= MAX_PLAINTEXT)
    return raw


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result)
        result[key] = value
    return result


def decode_plaintext(binding, purpose, raw, *, config_format=ConfigFormat.SCHEMA2):
    need(type(binding) is InstanceBinding and type(purpose) is Purpose and type(config_format) is ConfigFormat)
    expected = binding.record()
    need(type(raw) is bytes and 0 < len(raw) <= MAX_PLAINTEXT)
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise EnvelopeRefused() from None
    exact(value, ('schema', 'binding', 'purpose', 'payload', 'payload_sha256'))
    need(type(value['schema']) is str and value['schema'] == SCHEMA)
    # Canonical bytes enforce nested exact types as well (True is not integer 1).
    need(canonical(value['binding']) == canonical(expected))
    need(type(value['purpose']) is str and value['purpose'] == purpose.value)
    digest(value['payload_sha256'])
    validate_payload(binding, purpose, value['payload'], config_format=config_format)
    need(hmac.compare_digest(value['payload_sha256'], hashlib.sha256(canonical(value['payload'])).hexdigest()))
    need(canonical(value) == raw)
    return value['payload']
