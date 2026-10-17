from pathlib import Path
import hashlib, json, re, shutil, subprocess
import xml.etree.ElementTree as ET

root = Path('/workspace/ParkWeave')
runtime = root/'.runtime/preparation-read'
target = root/'docs/F2/evidence/ordinary-preparation-entry-20261017'
assert not target.exists(), 'never overwrite an evidence export'
freeze = json.loads((runtime/'freeze.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip() == freeze['source_sha']
drift = [p for p,h in freeze['files'].items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
assert not drift, drift
xml = ET.parse(runtime/'final-v1.xml')
cases = xml.findall('.//testcase')
assert len(cases)==178 and len({(c.get('classname'),c.get('name')) for c in cases})==178
assert not xml.findall('.//failure') and not xml.findall('.//error') and not xml.findall('.//skipped')
collected = {x for x in (runtime/'selected-collection.txt').read_text().splitlines() if x.startswith('tests/') and '::' in x}
executed = {'tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases}
assert collected==executed, dict(missing=sorted(collected-executed),extra=sorted(executed-collected))
preflight = json.loads((runtime/'preflight.json').read_text())
old_drift = [p for p,h in preflight['inherited_evidence_files'].items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
assert not old_drift, old_drift
pattern = re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
public_literals = set()
for p in freeze['files']:
    try: public_literals.update(pattern.findall((root/p).read_text()))
    except UnicodeDecodeError: pass

target.mkdir(parents=True)
pairs = []

def export(source, name):
    data = source.read_bytes()
    count = 0
    try:
        text = data.decode('utf-8')
        def redact(match):
            nonlocal count
            if match[0] in public_literals: return match[0]
            count += 1
            return '[SYNTHETIC_SESSION_REDACTED]'
        safe = pattern.sub(redact, text).encode('utf-8')
        assert not (set(pattern.findall(safe.decode()))-public_literals)
    except UnicodeDecodeError:
        safe = data
    out = target/name
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(safe)
    if out.suffix=='.json': json.loads(safe)
    if out.suffix=='.xml': ET.fromstring(safe)
    pairs.append(dict(original=str(source.relative_to(root)) if source.is_relative_to(root) else str(source),
                      exported=str(out.relative_to(root)),original_bytes=len(data),exported_bytes=len(safe),
                      original_sha256=hashlib.sha256(data).hexdigest(),exported_sha256=hashlib.sha256(safe).hexdigest(),
                      synthetic_session_occurrences_redacted=count))

for name in ('dev-v1.log','dev-v1.xml','dev-v2.log','dev-v2.xml','browser-dev-v1.log','browser-dev-v1.xml',
             'browser-dev-v2.log','browser-dev-v2.xml','dev-v3.log','dev-v3.xml','final-v1.log','final-v1.xml',
             'freeze.json','failure-ledger.json','algorithm-preservation.json','selected-collection.txt','remote-before.txt','environment.json','ancestry.json','export-evidence.py'):
    export(runtime/name,name)
base = Path('/tmp/parkweave-preparation-entry-final-v1')
for p in sorted(base.rglob('*')):
    if p.is_file() and p.name in ('source-entry-proof.json','source-entry.png','ordinary-api.log','entry.log','setup.log','state.json'):
        export(p,'process-evidence/'+str(p.relative_to(base)))
by_module = {}
for c in cases: by_module[c.get('classname')] = by_module.get(c.get('classname'),0)+1
summary = dict(source_sha=freeze['source_sha'],base_sha=preflight['base'],branch='dev/f3-ordinary-preparation-entry-20261017',
               result='PASS_WITH_INDEPENDENT_REVIEW_NOT_RUN',tests=dict(passed=178,failed=0,errors=0,skipped=0,unique=178,complete_modules=9,by_module=by_module),
               junit_seconds=sum(float(s.get('time','0')) for s in xml.findall('.//testsuite')),
               new_tests=21,new_tests_included_in_total=True,development_results_not_added=True,
               frozen_files=len(freeze['files']),frozen_drift=drift,inherited_evidence_files=len(preflight['inherited_evidence_files']),inherited_evidence_drift=old_drift,
               independent_review='NOT_RUN; self-review only; parent review pending',
               actual_scope=['Linux','owned synthetic PostgreSQL','actual Chromium','ordinary configured_app factory subprocess','one explicit original ADOPT','original-key material GET recovery'],
               missing_real_runtime_inputs=['existing authorized identity and PREPARE/REVIEW_ASSIGNED','existing same-scope preparation and original Case/Run','exact trusted preparation_catalog and current reviewer','existing current source/plan proof for ADOPT','legal runtime executor/Run assignment and ordinary approval/catalog provider wiring'],
               not_run=['Windows/Win11 native','formal AT/AT35','real business sources and identities','real model','production deployment','remote CI','full repository regression'],
               real_product_model_calls=0,complete_project=False,unknown_locks_or_processes_removed=False,
               prior_lock_preserved=preflight['preserved_unknown_lock'],initial_other_development_writers_observed=preflight['initial_other_development_writers_observed'],
               redaction='43-character synthetic session candidates absent from frozen source literals are replaced; originals retained privately; exported JSON/XML parse checked',
               development_full_source_snapshots='NOT_CAPTURED; failure logs/XML retained; no development results counted as frozen passes')
(target/'gate.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(target/'public-pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('source_sha','result','tests','junit_seconds','frozen_files','inherited_evidence_files')},ensure_ascii=False))
print(json.dumps(dict(public_artifacts=len(pairs),redacted_occurrences=sum(p['synthetic_session_occurrences_redacted'] for p in pairs))))
