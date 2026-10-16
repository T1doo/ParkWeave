"""Export task evidence without changing private originals; preserve structured files."""
from pathlib import Path
from fast_known_redaction import KnownTokenRedactor
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = next(p for p in Path(__file__).resolve().parents if p.name == '.runtime').parent
OUT = ROOT / 'docs/F2/evidence/plan-source-reapproval-20261016'
DIRS = ['plan-reapproval-'+name for name in ('root','oracle','backend','independent','review','final')]
EXTENSIONS = {'.log', '.xml', '.json', '.jsonl', '.txt', '.exit', '.py', '.js', '.md', '.patch', '.diff', '.html'}
EXCLUDED = {'archive-index.json', 'archive-audit.json', 'archive-independent-audit.json', 'delivery-draft.md', 'delivery-report-template.md', 'critical-path-draft.md', 'archive-readme-draft.md'}
PRIVATE_SETS = [ROOT / '.runtime/template-migration-tests-20261014/redaction-values.private.json', ROOT / '.runtime/template-structure-tests-20261015/redaction-values.private.json'] + [p for name in DIRS for p in (ROOT / '.runtime' / name).rglob('*redaction*.private.json')]


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
            values.update(x for x in data if len(x) >= 16)
    return sorted(values, key=lambda value: (-len(value), value))


def export_bytes(raw, suffix, values):
    counts = {'exact_private_value': 0, 'fixture_repr_line': 0}
    known_redactor=KnownTokenRedactor(values)

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


# Six changed product files plus original/new candidate aliases only. Never
# export an inherited clone's docs/evidence, unrelated tests, or dependencies.
CANDIDATE_SOURCES = {
 'src/parkweave/api.py','src/parkweave/case_resource_delivery.py',
 'src/parkweave/case_resources.py','src/parkweave/resource_plan_binding.py',
 'src/parkweave/service_plan_approval.py','src/parkweave/web.html',
 'tests/test_plan_reapproval_client.py','tests/test_plan_source_reapproval.py',
 'tests/test_plan_source_reapproval_candidate.py',
 'tests/test_plan_source_reapproval_chromium.py','tests/test_plan_source_reapproval_independent.py',
 'tests/plan_reapproval_client_probes.js','tests/plan_source_reapproval_real_html.js',
 'tests/test_case_resource_delivery_browser.py','tests/test_new_enterprise_local_chain_browser.py',
}
DENIED_PARTS = {'__pycache__','.pytest_cache','pytest-cache','node_modules','.git',
 '.venv','venv','xdg-cache','tmp','temp','data','pgdata','postgres','screenshots'}


def eligible(path):
    if not path.is_file() or path.is_symlink() or path.suffix not in EXTENSIONS:return False
    relative=path.relative_to(ROOT/'.runtime');parts=relative.parts
    if path.name in EXCLUDED or '.private.' in path.name or path.name.endswith('private.json'):return False
    if any(x in DENIED_PARTS or x.startswith(('parkweave-pg','pgsql_tmp')) or 'screenshot' in x.lower() for x in parts):return False
    if any(x.startswith('pytest-') for x in parts) and 'unredirected-legacy-artifacts' not in parts:return False
    # project/candidate trees are allowed only by exact changed source names,
    # or by an internal runtime subtree that belongs to THIS six-root task.
    clone_positions=[i for i,x in enumerate(parts[:-1]) if x=='project' or x=='candidate' or x.startswith(('candidate-','private-tree','private-worktree','source-wip','worktree'))]
    for pos in clone_positions:
        tail=parts[pos+1:]
        if '/'.join(tail) in CANDIDATE_SOURCES:continue
        if parts[pos]=='candidate' and pos>0 and parts[pos-1]=='browser-repair' and len(tail)==1 and tail[0] in {'test_case_resource_delivery_browser.py','test_new_enterprise_local_chain_browser.py'}:continue
        if len(tail)>=3 and tail[0]=='.runtime' and tail[1] in DIRS:continue
        return False
    return True


def sources():
    paths=[p for name in DIRS for p in (ROOT/'.runtime'/name).rglob('*')]
    return sorted(p for p in paths if eligible(p))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '.gitattributes').write_text('* -text -whitespace\n')
    values = private_values()
    entries = []
    for path in sources():
        raw = path.read_bytes()
        exported, counts = export_bytes(raw, path.suffix, values)
        relative = path.relative_to(ROOT / '.runtime')
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(exported)
        assert path.read_bytes() == raw, 'private original changed'
        entries.append(dict(raw_path=str(path.relative_to(ROOT)), export_path=str(target.relative_to(ROOT)),
                            raw_sha256=digest(raw), raw_bytes=len(raw), export_sha256=digest(exported),
                            export_bytes=len(exported), redactions=counts))
    index = dict(scope='EXPLICIT_SOURCE_REAPPROVAL_ENGINEERING_EVIDENCE', source_sha=json.loads((ROOT / '.runtime/plan-reapproval-root/v2/freeze.json').read_text())['source_sha'],
                 historical_windows='Includes isolated a794a180-based WIP, source929 completed/interrupted first formal windows, original a794 browser failures and private test-prerequisite repairs, plus fresh final V2 frozen executions. No first-phase or WIP score is migrated. Final source_sha does not claim every historical entry was rerun or passed at that SHA. Only actual final window receipts determine formal results.',
                 method='Exact known synthetic session values; fixture repr text lines only. XML parsed before text redaction; JSON recursively redacted. Private originals unchanged.',
                 excluded='Private session-value sets, PostgreSQL/cache/tmp/screenshot files, inherited clone docs/evidence/unrelated source and runtime. Inside clones retain only explicit six changed source files, four tests/two JS plus candidate test alias, and this task six-root runtime business traces. Shared template registries are redaction inputs only.',
                 entries=entries)
    (OUT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'exports': len(entries), 'bytes': sum(e['export_bytes'] for e in entries), 'redactions': {key: sum(e['redactions'][key] for e in entries) for key in ['exact_private_value','fixture_repr_line']}}))


if __name__ == '__main__':
    main()
