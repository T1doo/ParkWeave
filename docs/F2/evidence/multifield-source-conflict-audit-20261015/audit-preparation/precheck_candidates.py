"""Read-only, nonfinal format precheck; no root producer imports or export writes."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

from audit_archive import ROOT, HERE, source_inventory, read_json


def main():
    config = read_json(HERE / 'audit-config.json')
    producer = ROOT / '.runtime/multifield-source-root/export_archive.py'
    literal_policy = {}
    for node in ast.parse(producer.read_bytes()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {'DIRS', 'EXTENSIONS', 'EXCLUDED'}:
                literal_policy[node.targets[0].id] = ast.literal_eval(node.value)
    assert literal_policy['DIRS'] == config['dirs']
    assert literal_policy['EXTENSIONS'] == set(config['extensions'])
    assert literal_policy['EXCLUDED'] == set(config['excluded_names'])
    inventory = source_inventory(config, set())
    records, failures = [], []
    for relative in sorted(inventory):
        path = ROOT / relative
        try:
            raw = path.read_bytes()
            text = raw.decode('utf-8', errors='strict')
            if path.suffix == '.json':
                json.loads(text)
            elif path.suffix == '.jsonl':
                for line_number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        json.loads(line)
            elif path.suffix == '.xml':
                ET.fromstring(raw)
            elif path.suffix == '.py':
                ast.parse(text, filename=relative)
            changed = path.read_bytes() != raw
            records.append(dict(path=relative, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                changed_during_read=changed, structure='PASS'))
        except (UnicodeDecodeError, json.JSONDecodeError, ET.ParseError, SyntaxError, OSError) as exc:
            # Locations and exception classes only: never print fixture text or private values.
            failure = dict(path=relative, exception=type(exc).__name__,
                           line=getattr(exc, 'lineno', None), column=getattr(exc, 'colno', None),
                           changed_during_read=(path.read_bytes() != raw) if path.is_file() else True)
            if isinstance(exc, ET.ParseError):
                failure['line'], failure['column'] = exc.position
            failures.append(failure)
    result = dict(status='PRECHECK_FORMAT_ERRORS_FOUND' if failures else 'PRECHECK_ONLY_PASS_NOT_ARCHIVE_GATE',
                  utc=datetime.now(timezone.utc).isoformat(), source_sha=config['source_sha'],
                  producer_sha256=hashlib.sha256(producer.read_bytes()).hexdigest(),
                  source_inventory_files=len(inventory), checked_files=len(records),
                  extensions=dict(Counter(Path(row['path']).suffix for row in records)),
                  failures=failures, records=records, source_inventory_is_not_final=True,
                  active_executions_may_still_write=True, root_modules_imported=False,
                  actual_export_or_archive_gate_run=False)
    target = HERE / 'candidate-format-precheck-v1.json'
    assert not target.exists(), 'preserve earlier attempt'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ['status', 'source_inventory_files', 'checked_files', 'extensions', 'failures']}))


if __name__ == '__main__':
    main()
