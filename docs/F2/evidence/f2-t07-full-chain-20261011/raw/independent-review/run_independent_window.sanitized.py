"""Capture owned independent T07 windows without changing product or old evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = 'b5ea90ac9b366b015b43c426ad94b72faf7c8b72'
FROZEN = ROOT / '.runtime/f2-t07-full-chain/final-frozen-source-manifest.json'
FROZEN_SHA = 'fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths):
    return {p: sha(ROOT / p) for p in sorted(paths)}


def head_without_git_command():
    head = (ROOT / '.git/HEAD').read_text().strip()
    if not head.startswith('ref: '):
        return head
    ref = ROOT / '.git' / head[5:]
    if ref.exists():
        return ref.read_text().strip()
    for line in (ROOT / '.git/packed-refs').read_text().splitlines():
        if line.endswith(' ' + head[5:]):
            return line.split()[0]
    raise AssertionError('current source ref not found')


name, *modules = sys.argv[1:]
assert name and modules
assert not (OUT / (name + '-run.json')).exists()
assert not (OUT / (name + '.log')).exists()
assert sha(FROZEN) == FROZEN_SHA
frozen = json.loads(FROZEN.read_text())
assert len(frozen) == 406
before = snapshot(frozen)
assert before == frozen
assert head_without_git_command() == SOURCE
before_path = OUT / (name + '-before-source-manifest.json')
before_path.write_text(json.dumps(before, indent=2, sort_keys=True) + '\n')
evidence = OUT / 'windows' / name
evidence.mkdir(parents=True)
xml = OUT / (name + '.xml')
log = OUT / (name + '.log')
argv = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', *modules,
        '-q', '--tb=short', '--junitxml=' + str(xml)]
record = dict(operator='INDEPENDENT_REVIEWER', source_sha=SOURCE,
              source_file_count=len(frozen), frozen_source_manifest_sha256=FROZEN_SHA,
              source_pre_manifest_sha256=sha(before_path), argv=argv,
              started_at_utc=datetime.now(timezone.utc).isoformat(),
              browser_attempts=0, synthetic=True, formal_AT35=False,
              permissions='Original owned UUID PG fixture and fixed synthetic assignment precondition only',
              capture_program_sha256=sha(Path(__file__)))
run = OUT / (name + '-run.json')
run.write_text(json.dumps(record, indent=2) + '\n')
env = dict(os.environ, PARKWEAVE_T07_EVIDENCE_DIR=str(evidence))
started = time.monotonic()
with log.open('wb') as stream:
    child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record['pytest_pid'] = child.pid
    run.write_text(json.dumps(record, indent=2) + '\n')
    code = child.wait()
after = snapshot(frozen)
after_path = OUT / (name + '-after-source-manifest.json')
after_path.write_text(json.dumps(after, indent=2, sort_keys=True) + '\n')
record.update(exit_code=code, ended_at_utc=datetime.now(timezone.utc).isoformat(),
              elapsed_seconds=round(time.monotonic() - started, 3),
              source_post_manifest_sha256=sha(after_path),
              source_drift=[p for p in before if before[p] != after[p]],
              head_after=head_without_git_command(), log_sha256=sha(log))
if xml.exists():
    cases = ET.parse(xml).getroot().findall('.//testcase')
    identity = lambda c: c.attrib.get('classname', '') + '::' + c.attrib['name']
    state = lambda c: 'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
    counts = Counter(state(c) for c in cases)
    record.update({k: counts.get(k, 0) for k in ('PASS', 'FAIL', 'ERROR', 'SKIP')})
    record.update(tests=len(cases), unique_test_id_count=len({identity(c) for c in cases}),
                  xml_sha256=sha(xml), junit_seconds=sum(float(s.attrib['time']) for s in ET.parse(xml).getroot().findall('.//testsuite')),
                  failed_ids=[identity(c) for c in cases if state(c) in ('FAIL', 'ERROR')])
record['atexit_cleanup_diagnostic'] = 'Exception ignored in atexit' in log.read_text(errors='replace')
record['trace_file_count'] = len(list(evidence.glob('*.json')))
run.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2), flush=True)
sys.exit(code or (1 if record['source_drift'] or record['head_after'] != SOURCE else 0))
