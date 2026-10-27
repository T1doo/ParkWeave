"""Approved schema-2 global catalog: one complete AST/record scan per operation.

4096 total IDs replaces the old complete-list 3000 refusal. 3000 now bounds
retained full diagnostic-identity references; source AST nodes/raw bytes are
covered by their separate source-I/O limits, not a Python heap/RSS claim.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType

try:
    from .diagnostic_domains import DOMAINS, FILE_DOMAINS
except ImportError:
    from diagnostic_domains import DOMAINS, FILE_DOMAINS

MAX_IDS = 4096
MAX_FILES = 512
MAX_BYTES = 524288
MAX_INDEX_BYTES = 8192
MAX_LINE_BYTES = 512
MAX_ID_BYTES = 256
MAX_REFERENCES = 3000
MAX_REQUESTS = 832
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 32 * 1024 * 1024
PATTERN = r'tests/test_[a-z0-9_]+\.py::(?:[A-Za-z][A-Za-z0-9_]*::)?test_[A-Za-z0-9_]+'
FILE_PATTERN = r'tests/test_[a-z0-9_]+\.py'
CATALOG = 'scripts/windows_ci/diagnostic-test-ids.json'
DIRECTORY = 'scripts/windows_ci/diagnostic-catalog-v2'


class Refused(ValueError):
    def __init__(self,reason,*,expected=None,candidate_bytes=None):
        super().__init__(reason)
        self.expected=expected;self.candidate_bytes=candidate_bytes


def encode(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))+'\n').encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refused('CATALOG_REFUSED')
        result[key] = value
    return result


def decode(raw):
    def invalid(value):
        raise Refused('CATALOG_REFUSED')
    try:
        return json.loads(raw.decode('ascii'), object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Refused('CATALOG_REFUSED') from error


def decode_index(raw):
    # A valid index contains hashes/counters/domain names, never full test IDs.
    # Reject identity strings before JSON pairs/memo/object materialization can
    # exceed the caller's already reserved 3000-reference operation ledger.
    if len(raw)>MAX_INDEX_BYTES:raise Refused('INDEX_LIMIT')
    try:
        text=raw.decode('ascii');position=0
        while position<len(text):
            if text[position]!='"':position+=1;continue
            begin=position;position+=1
            while position<len(text):
                if text[position]=='\\':position+=2;continue
                if text[position]=='"':position+=1;break
                position+=1
            else:raise Refused('INDEX_REFUSED')
            value=json.loads(text[begin:position])
            if isinstance(value,str) and re.fullmatch(PATTERN,value):raise Refused('INDEX_REFUSED')
        return decode(raw)
    except (UnicodeError,ValueError,RecursionError) as error:
        raise Refused('INDEX_REFUSED') from error


def natural(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def fingerprint(path):
    # lstat before any read; intermediate symlinks/junctions are rejected too.
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.resolve() != path.absolute() or
            getattr(info, 'st_file_attributes', 0) & 1024):
        raise Refused('PATH_REFUSED')
    return stamp(info)


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def source_paths(root):
    directory = root/'tests'
    if directory.resolve() != directory.absolute():
        raise Refused('SOURCE_REFUSED')
    paths = sorted(directory.glob('test_*.py'))
    if not 0 < len(paths) <= MAX_FILES or any(p.is_symlink() for p in paths):
        raise Refused('SOURCE_REFUSED')
    names = [p.relative_to(root).as_posix() for p in paths]
    if (set(names) != set(FILE_DOMAINS) or
            any(not re.fullmatch(FILE_PATTERN, name) or FILE_DOMAINS[name] not in DOMAINS for name in names)):
        raise Refused('SOURCE_SET_MISMATCH')
    return names


def source_ids(root, name, snapshots, io):
    path = root/name
    if fingerprint(path) != snapshots[path]:
        raise Refused('INPUT_CHANGED')
    with path.open('rb') as stream:
        if stamp(os.fstat(stream.fileno())) != snapshots[path]:
            raise Refused('INPUT_CHANGED')
        raw = stream.read(min(MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES-io[0])+1)
        if stamp(os.fstat(stream.fileno())) != snapshots[path]:
            raise Refused('INPUT_CHANGED')
    io[0] += len(raw)
    if len(raw) > MAX_SOURCE_FILE_BYTES or io[0] > MAX_SOURCE_TOTAL_BYTES:
        raise Refused('SOURCE_REFUSED')
    try:
        tree = ast.parse(raw.decode('utf-8'))
    except (UnicodeError, SyntaxError, ValueError, RecursionError) as error:
        raise Refused('SOURCE_REFUSED') from error
    # Sort the existing bounded source AST in place. Never construct a full
    # diagnostic-ID list/set (a single source file may contain all 4096 IDs).
    tree.body.sort(key=lambda n: (getattr(n, 'name', ''), isinstance(n, ast.ClassDef)))

    def identities():
        previous = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes = [(None, node)] if node.name.startswith('test_') else ()
            elif isinstance(node, ast.ClassDef) and node.name and node.name[0].isalpha() and node.name.isascii():
                node.body.sort(key=lambda n: getattr(n, 'name', ''))
                nodes = ((node.name, method) for method in node.body
                         if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith('test_'))
            else:
                continue
            for cls, method in nodes:
                identity = name+'::'+(cls+'::' if cls else '')+method.name
                if (len(identity) > MAX_ID_BYTES or not re.fullmatch(PATTERN, identity) or
                        (previous is not None and identity <= previous)):
                    raise Refused('SOURCE_REFUSED')
                previous = identity
                yield identity
    return digest(raw), identities()


def mapping_digest():
    return digest(encode(FILE_DOMAINS))


def generation(index):
    return digest(encode({k: v for k, v in index.items() if k != 'generation'}))


class Membership:
    def __init__(self, root, snapshots, names, wanted, stats):
        self.root, self.snapshots, self.names = root, snapshots, names
        self.wanted, self.stats = MappingProxyType(wanted), MappingProxyType(stats)
        self.mapping = mapping_digest()

    def __contains__(self, value):
        return isinstance(value, str) and self.wanted.get(value, False)

    def assert_current(self):
        if getattr(self,'directory',None) is not None and {p.name for p in self.directory.iterdir()} != {d+'.jsonl' for d in DOMAINS}:
            raise Refused('INPUT_CHANGED')
        if source_paths(self.root) != self.names or mapping_digest() != self.mapping:
            raise Refused('INPUT_CHANGED')
        if any(fingerprint(path) != expected for path, expected in self.snapshots.items()):
            raise Refused('INPUT_CHANGED')


def scan(root, requests=(), *, retained_references=None, reserve=256, _index_input=None):
    """No membership escapes before every domain and exact source ID passes.

    Requests/results share one bounded dictionary; values are booleans. The
    caller supplies its live reference count and reserves projection scratch.
    There is no global cache and no per-domain/row/ID reset of this budget.
    """
    root = Path(root).absolute()
    if (retained_references is not None and not natural(retained_references, MAX_REFERENCES)) or not natural(reserve, MAX_REFERENCES):
        raise Refused('REFERENCE_LIMIT')
    wanted, occurrences = {}, 0
    for value in requests:
        occurrences += 1
        if occurrences > MAX_REQUESTS:
            raise Refused('REQUEST_LIMIT')
        if isinstance(value, str) and len(value) <= MAX_ID_BYTES and re.fullmatch(PATTERN, value):
            wanted[value] = False
        if (occurrences if retained_references is None else retained_references)+len(wanted)+reserve+8 > MAX_REFERENCES:
            raise Refused('REFERENCE_LIMIT')
    names = source_paths(root)
    snapshots = {root/name: fingerprint(root/name) for name in names}
    index_path = root/CATALOG
    if _index_input is None:
        snapshots[index_path] = fingerprint(index_path)
        with index_path.open('rb') as stream:
            if stamp(os.fstat(stream.fileno())) != snapshots[index_path]:
                raise Refused('INPUT_CHANGED')
            raw = stream.read(MAX_INDEX_BYTES+1)
    else:
        # Maintenance check transfers its already bounded index read, avoiding
        # a second input scan. The same final snapshot fences still apply.
        raw, snapshots[index_path] = _index_input
        if fingerprint(index_path) != snapshots[index_path]:raise Refused('INPUT_CHANGED')
    if len(raw) > MAX_INDEX_BYTES:
        raise Refused('INDEX_LIMIT')
    index = decode_index(raw)
    required = {'schema', 'generation', 'mapping_sha256', 'files', 'ids', 'domains'}
    if (not isinstance(index, dict) or set(index) != required or type(index['schema']) is not int or index['schema'] != 2 or
            index['mapping_sha256'] != mapping_digest() or index['files'] != len(names) or
            not natural(index['files'], MAX_FILES) or not natural(index['ids'], MAX_IDS) or index['ids'] == 0 or
            not isinstance(index['generation'], str) or not re.fullmatch('[0-9a-f]{64}', index['generation']) or
            index['generation'] != generation(index)):
        raise Refused('INDEX_REFUSED')
    domains = index['domains']
    if not isinstance(domains, list) or len(domains) != len(DOMAINS):
        raise Refused('INDEX_REFUSED')
    total_bytes, ids, files, io = len(raw), 0, 0, [0]
    for domain, record in zip(DOMAINS, domains):
        if (not isinstance(record, dict) or set(record) != {'domain', 'ids', 'files', 'bytes', 'sha256'} or
                record['domain'] != domain or not natural(record['ids'], MAX_IDS) or
                not natural(record['files'], MAX_FILES) or not natural(record['bytes'], MAX_BYTES) or
                not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise Refused('INDEX_REFUSED')
        total_bytes += record['bytes']
    if total_bytes > MAX_BYTES or sum(x['ids'] for x in domains) != index['ids'] or sum(x['files'] for x in domains) != index['files']:
        raise Refused('CATALOG_LIMIT')
    # Capture the entire generation before opening the first domain.
    paths = [root/DIRECTORY/index['generation']/(domain+'.jsonl') for domain in DOMAINS]
    if {p.name for p in paths[0].parent.iterdir()} != {d+'.jsonl' for d in DOMAINS}:
        raise Refused('GENERATION_REFUSED')
    snapshots.update((path, fingerprint(path)) for path in paths)
    for domain, record, path in zip(DOMAINS, domains, paths):
        expected_files = (name for name in names if FILE_DOMAINS[name] == domain)
        expected_ids = iter(())
        domain_ids = domain_files = size = 0
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            if stamp(os.fstat(stream.fileno())) != snapshots[path]:
                raise Refused('INPUT_CHANGED')
            while True:
                line = stream.readline(MAX_LINE_BYTES+1)
                if not line:
                    break
                size += len(line)
                if len(line) > MAX_LINE_BYTES or not line.endswith(b'\n') or size > record['bytes']:
                    raise Refused('LINE_LIMIT')
                hasher.update(line)
                row = decode(line)
                if isinstance(row, dict) and set(row) == {'file', 'sha256'}:
                    if next(expected_ids, None) is not None:
                        raise Refused('AST_MISMATCH')
                    name = next(expected_files, None)
                    if row['file'] != name or not isinstance(name, str):
                        raise Refused('FILE_ORDER_OR_OWNERSHIP')
                    source_hash, expected_ids = source_ids(root, name, snapshots, io)
                    if row['sha256'] != source_hash:
                        raise Refused('SOURCE_HASH_MISMATCH')
                    domain_files += 1
                    files += 1
                    if files > MAX_FILES:
                        raise Refused('FILE_LIMIT')
                elif isinstance(row, dict) and set(row) == {'id'}:
                    value = row['id']
                    if (not isinstance(value, str) or len(value) > MAX_ID_BYTES or not re.fullmatch(PATTERN, value) or
                            value != next(expected_ids, None)):
                        raise Refused('AST_MISMATCH')
                    domain_ids += 1
                    ids += 1
                    if ids > MAX_IDS:
                        raise Refused('ID_LIMIT')
                    if value in wanted:
                        wanted[value] = True
                else:
                    raise Refused('ROW_REFUSED')
            if stamp(os.fstat(stream.fileno())) != snapshots[path]:
                raise Refused('INPUT_CHANGED')
        if (next(expected_ids, None) is not None or next(expected_files, None) is not None or
                size != record['bytes'] or domain_ids != record['ids'] or domain_files != record['files'] or
                hasher.hexdigest() != record['sha256']):
            raise Refused('DOMAIN_MISMATCH')
    if ids != index['ids'] or files != len(names):
        raise Refused('COVERAGE_MISMATCH')
    stats = dict(catalog_scans=1, ids=ids, files=files, raw_bytes=total_bytes,
                 requests=occurrences, retained_reference_bound=(occurrences if retained_references is None else retained_references)+len(wanted)+reserve+8,
                 source_bytes=io[0])
    result = Membership(root, snapshots, names, wanted, stats)
    result.directory=paths[0].parent
    result.assert_current()
    return result


def generate(root):
    """Producer has the same ordered AST iterator; no all-ID collection."""
    root = Path(root).absolute()
    names = source_paths(root)
    snapshots = {root/name: fingerprint(root/name) for name in names}
    payloads, records, io, ids = {}, [], [0], 0
    for domain in DOMAINS:
        raw = bytearray()
        domain_ids = domain_files = 0
        for name in names:
            if FILE_DOMAINS[name] != domain:
                continue
            source_hash, identities = source_ids(root, name, snapshots, io)
            raw.extend(encode({'file': name, 'sha256': source_hash}))
            domain_files += 1
            for identity in identities:
                ids += 1
                domain_ids += 1
                if ids > MAX_IDS:
                    raise Refused('CAPACITY_EXCEEDED',expected=ids)
                line = encode({'id': identity})
                if len(line) > MAX_LINE_BYTES:
                    raise Refused('LINE_LIMIT')
                raw.extend(line)
                if sum(len(p) for p in payloads.values())+len(raw) > MAX_BYTES:
                    raise Refused('BYTE_CAPACITY_EXCEEDED',expected=ids,candidate_bytes=sum(map(len,payloads.values()))+len(raw))
        payloads[domain] = raw
        records.append(dict(domain=domain, ids=domain_ids, files=domain_files, bytes=len(raw), sha256=digest(raw)))
    index = dict(schema=2, mapping_sha256=mapping_digest(), files=len(names), ids=ids, domains=records)
    index['generation'] = generation(index)
    raw_index = encode(index)
    if not ids or len(raw_index) > MAX_INDEX_BYTES or len(raw_index)+sum(map(len, payloads.values())) > MAX_BYTES:
        raise Refused('BYTE_CAPACITY_EXCEEDED',expected=ids,candidate_bytes=len(raw_index)+sum(map(len,payloads.values())))
    if source_paths(root) != names or any(fingerprint(p) != value for p, value in snapshots.items()):
        raise Refused('INPUT_CHANGED')
    return raw_index, payloads, snapshots
