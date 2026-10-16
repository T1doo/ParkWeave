"""Export task evidence without changing private originals; preserve structured files."""
from pathlib import Path
from fast_known_redaction import KnownTokenRedactor
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = next(p for p in Path(__file__).resolve().parents if p.name == '.runtime').parent
OUT = ROOT / 'docs/F2/evidence/p3-never-accepted-closure-20261016'
DIRS = ['p3-closure-'+name for name in ('root','backend','ui','oracle','review')]
PRIOR_PRIVATE_DIRS = ['frontier-'+name for name in ('root','oracle','backend','ui','review')] + ['frontier-repair-ui','frontier-review-v2','frontier-oracle-v2','frontier-repair-ui2','frontier-review-v3']
TRACE_DIRS = set(DIRS)
EXTENSIONS = {'.log', '.xml', '.json', '.jsonl', '.txt', '.exit', '.py', '.js', '.md', '.patch', '.diff', '.html'}
EXCLUDED = {'archive-index.json', 'archive-audit.json', 'archive-independent-audit.json', 'delivery-draft.md', 'delivery-report-template.md', 'critical-path-draft.md', 'archive-readme-draft.md'}
PRIVATE_SETS = [ROOT / '.runtime/template-migration-tests-20261014/redaction-values.private.json', ROOT / '.runtime/template-structure-tests-20261015/redaction-values.private.json'] + [p for name in [*DIRS,*PRIOR_PRIVATE_DIRS] for p in (ROOT / '.runtime' / name).rglob('*.private.json')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def private_values():
    values = set()
    for path in PRIVATE_SETS:
        if path.is_file():
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                assert set(data) <= {'synthetic_private_values', 'provenance'} and 'synthetic_private_values' in data, 'unknown private registry schema'
                if 'provenance' in data:
                    assert isinstance(data['provenance'], str)
                data = data['synthetic_private_values']
            assert isinstance(data, list) and all(isinstance(x, str) for x in data)
            values.update(x for x in data if x)
    return sorted(values, key=lambda value: (-len(value), value))


def export_bytes(raw, suffix, values, known_redactor=None):
    counts = {'exact_private_value': 0, 'fixture_repr_line': 0}
    if known_redactor is None: known_redactor=KnownTokenRedactor(values)

    def redact(text):
        text, count = known_redactor.replace(text)
        counts['exact_private_value'] += count
        lines = []
        for line in text.splitlines(keepends=True):
            # Pytest fixture repr can contain truncated session strings that cannot
            # be replaced by exact full-token lookup. Mask only that repr line.
            if suffix not in {'.py', '.js'} and (re.match(r'^\s*\w+\s*=\s*[({].*Store object at 0x', line) or re.match(r'^\s*(?:tokens|session_tokens)\s*=\s*\{', line)):
                counts['fixture_repr_line'] += 1
                line = '[REDACTED_SYNTHETIC_FIXTURE_REPR]' + ('\n' if line.endswith('\n') else '')
            lines.append(line)
        return ''.join(lines)

    def walk(value):
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    text = raw.decode('utf-8')
    if suffix == '.xml':
        doc = ET.fromstring(text)
        for node in doc.iter():
            if node.text:
                node.text = redact(node.text)
            if node.tail:
                node.tail = redact(node.tail)
            for key, value in list(node.attrib.items()):
                node.set(key, redact(value))
        result = ET.tostring(doc, encoding='utf-8', xml_declaration=True)
        ET.fromstring(result)
    elif suffix == '.json':
        result = (json.dumps(walk(json.loads(text)), ensure_ascii=True, indent=2) + '\n').encode()
        json.loads(result)
    elif suffix == '.jsonl':
        result = ''.join(json.dumps(walk(json.loads(line)), ensure_ascii=True) + '\n' for line in text.splitlines() if line.strip()).encode()
        for line in result.splitlines():
            json.loads(line)
    else:
        result = redact(text).encode()
    if not any(counts.values()):
        result = raw
    assert not known_redactor.has_residual(result.decode()), 'known synthetic token residual'
    return result, counts


# Exact changed source/test/script whitelist plus fixed candidate aliases. Never
# export an inherited clone's docs/evidence, unrelated tests, or dependencies.
CANDIDATE_SOURCES = set(json.loads((ROOT / '.runtime/p3-closure-root/candidate-export-whitelist.json').read_text()))

DENIED_PARTS = {'__pycache__','.pytest_cache','pytest-cache','node_modules','.git',
 '.venv','venv','xdg-cache','tmp','temp','data','pgdata','postgres','screenshots'}


def eligible(path):
    if not path.is_file() or path.is_symlink() or path.suffix not in EXTENSIONS:return False
    parts=path.relative_to(ROOT/'.runtime').parts
    if path.name in EXCLUDED or '.private.' in path.name or path.name.endswith('private.json'):return False
    if any(x in DENIED_PARTS or x.startswith(('parkweave-pg','pgsql_tmp')) or 'screenshot' in x.lower() for x in parts):return False
    if any(x.startswith('pytest-') for x in parts):return False
    # Every inherited source/test/script subtree is an exact whitelist. Mixed
    # attempt directories also contain actual raw logs; keep those outside code.
    for i,part in enumerate(parts):
        if part in {'src','tests','scripts'}:
            return '/'.join(parts[i:]) in CANDIDATE_SOURCES
    if 'docs' in parts:return False
    for i,part in enumerate(parts[:-1]):
        if part=='.runtime' and parts[i+1] not in TRACE_DIRS:return False
    if path.name in {'README.md','LICENSE','LICENSE.md'}:return False
    # Flat candidate source snapshots and raw per-attempt metadata are retained;
    # no inherited clone docs/dependencies or private state is admitted above.
    return True


def sources():
    paths=[p for name in DIRS for p in (ROOT/'.runtime'/name).rglob('*')]
    return sorted(p for p in paths if eligible(p))


def main():
    frozen=json.loads((ROOT/'.runtime/p3-closure-root/v1/freeze.json').read_text())
    seal=json.loads((ROOT/'.runtime/p3-closure-root/seal.json').read_text())
    assert seal['source_sha']==frozen['source_sha'] and seal['status']=='SEALED_NO_FURTHER_PRIMARY_WRITES'
    assert set(seal['primary_roots'])==set(DIRS)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / '.gitattributes').write_text('* -text -whitespace\n')
    values = private_values()
    entries = []
    known_redactor=KnownTokenRedactor(values)
    for path in sources():
        raw = path.read_bytes()
        exported, counts = export_bytes(raw, path.suffix, values, known_redactor)
        relative = path.relative_to(ROOT / '.runtime')
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(exported)
        assert path.read_bytes() == raw, 'private original changed'
        entries.append(dict(raw_path=str(path.relative_to(ROOT)), export_path=str(target.relative_to(ROOT)),
                            raw_sha256=digest(raw), raw_bytes=len(raw), export_sha256=digest(exported),
                            export_bytes=len(exported), redactions=counts))
    index = dict(scope='EXPLICIT_P3_NEVER_ACCEPTED_CLOSED_ENGINEERING_EVIDENCE', source_sha=json.loads((ROOT / '.runtime/p3-closure-root/v1/freeze.json').read_text())['source_sha'],
                 historical_windows='All new frontier development attempts, original failures, immutable candidate snapshots and final frozen complete windows remain distinct. Final counts come only from the actual uniform source SHA and declared final selection. No prior task or earlier source scores are migrated.',
                 method='Exact known synthetic session values; fixture repr text lines only. XML parsed before text redaction; JSON recursively redacted. Private originals unchanged.',
                 excluded='Private session registries, PostgreSQL/cache/tmp/screenshots and inherited clone docs/dependencies are excluded. Inherited src/tests/scripts require the exact CANDIDATE_SOURCES whitelist; flat candidate snapshots and raw attempts are retained. Only five explicit P3 closure task roots supply public evidence; exact original synthetic fixture registries supplement redaction values.',
                 entries=entries)
    (OUT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'exports': len(entries), 'bytes': sum(e['export_bytes'] for e in entries), 'redactions': {key: sum(e['redactions'][key] for e in entries) for key in ['exact_private_value','fixture_repr_line']}}))


if __name__ == '__main__':
    main()
