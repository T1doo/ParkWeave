"""Export task evidence without changing private originals; preserve structured files."""
from pathlib import Path
from fast_known_redaction import KnownTokenRedactor
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/F2/evidence/note-template-carry-20261015'
DIRS = ['note-template-carry-root', 'note-template-carry-backend', 'note-template-carry-independent', 'note-template-carry-review', 'note-template-carry-final', 'note-template-carry-backend-formal', 'note-template-carry-independent-formal', 'note-template-carry-review-formal', 'note-template-carry-backend-formal-v2', 'note-template-carry-independent-formal-v2', 'note-template-carry-review-formal-v2']
EXTENSIONS = {'.log', '.xml', '.json', '.jsonl', '.txt', '.exit', '.py', '.js', '.md', '.patch', '.html'}
EXCLUDED = {'archive-index.json', 'archive-audit.json', 'archive-independent-audit.json', 'delivery-draft.md', 'delivery-report-template.md', 'critical-path-draft.md', 'archive-readme-draft.md'}
PRIVATE_SETS = [ROOT / '.runtime/template-migration-tests-20261014/redaction-values.private.json', ROOT / '.runtime/template-structure-tests-20261015/redaction-values.private.json'] + [p for name in DIRS for p in (ROOT / '.runtime' / name).rglob('*redaction*.private.json')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def private_values():
    values = set()
    for path in PRIVATE_SETS:
        if path.is_file():
            data = json.loads(path.read_text())
            assert isinstance(data, list) and all(isinstance(x, str) for x in data)
            values.update(x for x in data if len(x) >= 16)
    return sorted(values, key=len, reverse=True)


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
        result = (json.dumps(walk(json.loads(text)), ensure_ascii=False, indent=2) + '\n').encode()
        json.loads(result)
    elif suffix == '.jsonl':
        result = ''.join(json.dumps(walk(json.loads(line)), ensure_ascii=False) + '\n' for line in text.splitlines() if line.strip()).encode()
        for line in result.splitlines():
            json.loads(line)
    else:
        result = redact(text).encode()
    if not any(counts.values()):
        result = raw
    assert not known_redactor.has_residual(result.decode()), 'known synthetic token residual'
    return result, counts


def sources():
    paths = [p for name in DIRS for p in (ROOT / '.runtime' / name).rglob('*')]
    return sorted(p for p in paths if p.is_file() and p.suffix in EXTENSIONS
                  and p.name not in EXCLUDED and '.private.' not in p.name
                  and not any(x in p.parts for x in ('__pycache__','worktree','source-v1','private-worktree','source-wip-v1','source-wip-v2','xdg-cache','pytest-cache','.pytest_cache')) and (not any(x.startswith('pytest-') for x in p.parts) or 'unredirected-legacy-artifacts' in p.parts))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
    index = dict(scope='NOTE_TEMPLATE_CARRY_BOUNDED_ENGINEERING_EVIDENCE', source_sha=json.loads((ROOT / '.runtime/note-template-carry-root/freeze-v3.json').read_text())['source_sha'],
                 historical_windows='Entries include development WIP at baseline HEAD, failed setup/postcheck windows, and formal frozen executions. source_sha is the final reference, not a claim that every entry was rerun at that SHA.',
                 method='Exact known synthetic session values; fixture repr text lines only. XML parsed before text redaction; JSON recursively redacted. Private originals unchanged.',
                 excluded='Private session-value sets, PostgreSQL files, caches, unrelated runtime. Shared template private redaction sets are not exclusive test evidence.',
                 entries=entries)
    (OUT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'exports': len(entries), 'bytes': sum(e['export_bytes'] for e in entries), 'redactions': {key: sum(e['redactions'][key] for e in entries) for key in ['exact_private_value','fixture_repr_line']}}))


if __name__ == '__main__':
    main()
