"""Maintain approved schema-2 active catalog generations; publish index last.

The total logical ID limit intentionally migrates from 3000 to 4096. All active
index/domain input bytes together remain <=512KiB; no runtime membership is
returned by this developer command. Old generations and failed new outputs are
preserved, never repaired, deleted or silently adopted when incomplete.
"""
import argparse
import bisect
import json
import os
from pathlib import Path
import re
import uuid
try:
    from . import catalog_v2 as cv
except ImportError:
    import catalog_v2 as cv

MAX_ALLOWLIST_IDS = cv.MAX_IDS
MAX_ALLOWLIST_BYTES = cv.MAX_BYTES
CATALOG = cv.CATALOG
CatalogRefused = cv.Refused


def _current(root, *, check=False):
    path = root/CATALOG
    snapshots = {path: cv.fingerprint(path)}
    with path.open('rb') as stream:
        raw = stream.read(MAX_ALLOWLIST_BYTES+1)
    if len(raw) > MAX_ALLOWLIST_BYTES:
        raise cv.Refused('CATALOG_REFUSED')
    # Only the known legacy schema is streamed. Reserve scratch references
    # before each decode/append; a full 3000-entry legacy input is refused.
    prefix=re.match(rb'\s*\{\s*"schema"\s*:\s*1\s*,\s*"test_ids"\s*:\s*\[',raw)
    if prefix:
        text=raw.decode('ascii');position=prefix.end();ids=[];decoder=json.JSONDecoder()
        while True:
            while position<len(text) and text[position].isspace():position+=1
            if position<len(text) and text[position]==']':position+=1;break
            if len(ids)+33>cv.MAX_REFERENCES:raise cv.Refused('REFERENCE_LIMIT')
            if position>=len(text) or text[position]!='"':raise cv.Refused('CATALOG_REFUSED')
            identity,position=decoder.raw_decode(text,position)
            if (not isinstance(identity,str) or len(identity)>256 or not re.fullmatch(cv.PATTERN,identity) or
                    (ids and identity<=ids[-1])):raise cv.Refused('CATALOG_REFUSED')
            ids.append(identity)
            while position<len(text) and text[position].isspace():position+=1
            if position<len(text) and text[position]==',':
                position+=1
                if re.match(r'\s*\]',text[position:]):raise cv.Refused('CATALOG_REFUSED')
                continue
            if position<len(text) and text[position]==']':position+=1;break
            raise cv.Refused('CATALOG_REFUSED')
        if not ids or not re.fullmatch(r'\s*\}\s*',text[position:]):raise cv.Refused('CATALOG_REFUSED')
        return raw,snapshots,ids,len(ids)
    if len(raw)>cv.MAX_INDEX_BYTES:raise cv.Refused('CATALOG_REFUSED')
    value=cv.decode_index(raw)
    if not isinstance(value,dict):raise cv.Refused('CATALOG_REFUSED')
    if (set(value) != {'schema','generation','mapping_sha256','files','ids','domains'} or type(value['schema']) is not int or value['schema'] != 2 or
            len(raw) > cv.MAX_INDEX_BYTES or not cv.natural(value['ids'], cv.MAX_IDS) or not value['ids'] or
            not cv.natural(value['files'], cv.MAX_FILES) or
            not isinstance(value['mapping_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['mapping_sha256']) or
            value['generation'] != cv.generation(value) or not isinstance(value['domains'], list) or len(value['domains']) != len(cv.DOMAINS)):
        raise cv.Refused('CATALOG_REFUSED')
    if check:return raw,snapshots,None,value['ids']
    # Maintenance accepts structurally valid *stale* source hashes so an explicit
    # source edit can be refreshed. Consumers always use cv.scan with exact AST.
    seen, total_bytes, total_ids = set(), len(raw), 0
    for domain, row in zip(cv.DOMAINS, value['domains']):
        if (not isinstance(row, dict) or set(row) != {'domain','ids','files','bytes','sha256'} or row['domain'] != domain or
                not cv.natural(row['ids'], cv.MAX_IDS) or not cv.natural(row['files'], cv.MAX_FILES) or
                not cv.natural(row['bytes'], cv.MAX_BYTES) or not isinstance(row['sha256'], str) or
                not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise cv.Refused('CATALOG_REFUSED')
        total_bytes += row['bytes']
        if total_bytes > MAX_ALLOWLIST_BYTES:
            raise cv.Refused('CATALOG_REFUSED')
        source = root/cv.DIRECTORY/value['generation']/(domain+'.jsonl')
        snapshots[source] = cv.fingerprint(source)
        h = cv.hashlib.sha256(); size = count = files = 0; name = previous = None
        with source.open('rb') as stream:
            while True:
                line = stream.readline(cv.MAX_LINE_BYTES+1)
                if not line:
                    break
                size += len(line)
                if len(line) > cv.MAX_LINE_BYTES or not line.endswith(b'\n') or size > row['bytes']:
                    raise cv.Refused('CATALOG_REFUSED')
                h.update(line); item = cv.decode(line)
                if isinstance(item, dict) and set(item) == {'file','sha256'}:
                    new = item['file']
                    if (not isinstance(new, str) or not re.fullmatch(cv.FILE_PATTERN, new) or new in seen or
                            (name is not None and new <= name) or not isinstance(item['sha256'], str) or
                            not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
                        raise cv.Refused('CATALOG_REFUSED')
                    seen.add(new); name = new; previous = None; files += 1
                    if len(seen) > cv.MAX_FILES:
                        raise cv.Refused('CATALOG_REFUSED')
                elif isinstance(item, dict) and set(item) == {'id'}:
                    identity = item['id']
                    if (name is None or not isinstance(identity, str) or len(identity) > 256 or
                            not re.fullmatch(cv.PATTERN, identity) or not identity.startswith(name+'::') or
                            (previous is not None and identity <= previous)):
                        raise cv.Refused('CATALOG_REFUSED')
                    previous = identity; count += 1; total_ids += 1
                    if total_ids > cv.MAX_IDS:
                        raise cv.Refused('CATALOG_REFUSED')
                else:
                    raise cv.Refused('CATALOG_REFUSED')
        if (size != row['bytes'] or count != row['ids'] or files != row['files'] or h.hexdigest() != row['sha256']):
            raise cv.Refused('CATALOG_REFUSED')
    if total_ids != value['ids'] or len(seen) != value['files']:
        raise cv.Refused('CATALOG_REFUSED')
    return raw, snapshots, None, total_ids


def inspect(root, *, write=False):
    result = dict(schema=2, scope='GLOBAL_AST_CATALOG_MAINTENANCE', status='INPUT_REFUSED',
                  expected=None, current=None, missing=None, extra=None,
                  limit_ids=MAX_ALLOWLIST_IDS, limit_bytes=cv.MAX_BYTES,
                  candidate_bytes=None, write_state='NOT_ATTEMPTED')
    temporary = None
    try:
        root = Path(root).absolute()
        original, old_snapshots, legacy, current = _current(root,check=not write)
        result['current'] = current
        if not write and legacy is None:
            scan = cv.scan(root,_index_input=(original,old_snapshots[root/CATALOG]))
            return dict(result, status='VALID', expected=scan.stats['ids'], missing=0, extra=0,
                        candidate_bytes=scan.stats['raw_bytes'])
        raw_index, payloads, snapshots = cv.generate(root)
        index = cv.decode_index(raw_index)
        result.update(expected=index['ids'], candidate_bytes=len(raw_index)+sum(map(len,payloads.values())))
        if legacy is not None:
            # No second identity set; legacy input reserves 32 scratch references.
            found = bytearray(len(legacy)); missing = 0
            for data in payloads.values():
                # Iterating lines, not splitlines() retaining the complete IDs.
                import io
                for line in io.BytesIO(data):
                    item = cv.decode(line)
                    if 'id' in item:
                        identity = item['id']; pos = bisect.bisect_left(legacy, identity)
                        if pos < len(legacy) and legacy[pos] == identity:found[pos] = 1
                        else:missing += 1
            result.update(missing=missing, extra=len(legacy)-sum(found))
        if not write:
            return dict(result, status='MISMATCH')
        if (any(cv.fingerprint(p) != s for p,s in {**old_snapshots,**snapshots}.items()) or
                cv.source_paths(root) != sorted(cv.FILE_DOMAINS)):
            return dict(result, status='INPUT_CHANGED')
        directory = root/cv.DIRECTORY
        if directory.exists() and directory.resolve() != directory.absolute():
            raise cv.Refused('PATH_REFUSED')
        directory.mkdir(exist_ok=True)
        target = directory/index['generation']
        if target.exists():
            if target.resolve() != target.absolute() or {p.name for p in target.iterdir()} != {d+'.jsonl' for d in cv.DOMAINS}:
                raise cv.Refused('GENERATION_REFUSED')
            for domain, data in payloads.items():
                path = target/(domain+'.jsonl'); cv.fingerprint(path)
                with path.open('rb') as stream:existing = stream.read(len(data)+1)
                if existing != data:raise cv.Refused('GENERATION_REFUSED')
        else:
            result['write_state'] = 'UNCONFIRMED'
            target.mkdir()  # Exclusive generation; incomplete output stays preserved.
            for domain, data in payloads.items():
                with (target/(domain+'.jsonl')).open('xb') as stream:
                    if stream.write(data) != len(data):raise OSError('short generation write')
        # Index is the only commit point. Never repoint it after input drift.
        if any(cv.fingerprint(p) != s for p,s in {**old_snapshots,**snapshots}.items()) or cv.source_paths(root) != sorted(cv.FILE_DOMAINS):
            return dict(result, status='INPUT_CHANGED')
        temporary = (root/CATALOG).with_name('.diagnostic-catalog-'+uuid.uuid4().hex+'.tmp')
        result['write_state'] = 'UNCONFIRMED'
        with temporary.open('xb') as stream:
            if stream.write(raw_index) != len(raw_index):raise OSError('short index write')
        os.replace(temporary, root/CATALOG)
        return dict(result, status='UPDATED', write_state='CONFIRMED', missing=0, extra=0)
    except cv.Refused as error:
        result['status'] = str(error)
        if error.expected is not None:result['expected']=error.expected
        if error.candidate_bytes is not None:result['candidate_bytes']=error.candidate_bytes
    except (OSError, ValueError, TypeError, UnicodeError, SyntaxError, RecursionError):
        pass
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true'); modes.add_argument('--write', action='store_true')
    args = parser.parse_args(); report = inspect(Path(__file__).resolve().parents[2], write=args.write)
    print(json.dumps(report,separators=(',',':')))
    return 0 if report['status'] in ('VALID','UPDATED') else 2


if __name__ == '__main__':raise SystemExit(main())
