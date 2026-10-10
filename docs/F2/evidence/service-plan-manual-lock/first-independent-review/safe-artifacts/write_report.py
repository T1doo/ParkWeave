from pathlib import Path
import hashlib,json,subprocess,os,xml.etree.ElementTree as E
from datetime import datetime,timezone
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/independent-service-plan-manual-lock-review'
import sys
sys.path.insert(0,str(ROOT/'src'))
from parkweave.process_env import minimal_environment
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
 r=subprocess.run(['git',*args],cwd=ROOT,env=minimal_environment(os.environ),capture_output=True,text=True)
 assert r.returncode==0
 return r.stdout.strip()
frozen=json.loads((OUT/'frozen-source.json').read_text())
drift=[p for p,h in frozen.items() if sha(ROOT/p)!=h]
assert not drift
assert git('rev-parse','HEAD')=='0c2e5fa0e5f8276cb783aa5a7c37fd10051882bb'
windows=[]
for name,kind in [('complete','RELATED_MODULE_REGRESSION'),('probes','OBSERVER_SETUP_ERROR'),('browser-probe','OBSERVER_SETUP_ERROR'),('probes-fixture-corrected','INDEPENDENT_ORACLES'),('proof-probes','MANUAL_LOCK_PROOF_NEGATIVES'),('budget-observer-corrected','CORRECTED_OBSERVER_SELECTED')]:
 p=OUT/(name+'-junit.xml');tree=E.parse(p);s=next(tree.iter('testsuite'))
 failures=[{'nodeid':t.attrib['classname']+'::'+t.attrib['name'],'stage':'failure' if t.find('failure') is not None else 'error'} for t in tree.iter('testcase') if t.find('failure') is not None or t.find('error') is not None]
 cases=list(tree.iter('testcase'));passed=sum(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in cases)
 execute=json.loads((OUT/(name+'-execution.json')).read_text())
 windows.append(dict(name=name,kind=kind,tests=int(s.attrib['tests']),passed=passed,failures=int(s.attrib['failures']),errors=int(s.attrib['errors']),skipped=int(s.attrib['skipped']),junit_seconds=float(s.attrib['time']),controlled_seconds=execute['end']-execute['start'],module_paths=execute['modules'],minimal_environment=execute['minimal_environment'],failed_nodeids=failures,raw_junit_sha256=sha(p),raw_log_sha256=sha(OUT/(name+'-pytest.log')),raw_faults_private_only=True))
report=dict(decision='BLOCKED',reviewed_sha=git('rev-parse','HEAD'),reviewed_branch=git('branch','--show-current'),reviewed_at=datetime.now(timezone.utc).isoformat(),source_count=len(frozen),source_drift=drift,source_manifest_sha256=sha(OUT/'frozen-source.json'),root_manifest_sha256=sha(ROOT/'.runtime/service-plan-manual-lock/frozen-source.json'),worktree_status=git('status','--porcelain'),untracked_nonignored=git('ls-files','--others','--exclude-standard'),windows=windows,
 blockers=[dict(id='ML-GOAL-1',summary='Existing goal-results rejects legitimate LOCK and UNLOCK events with HTTP409; original current output evidence cannot be read after either owner operation.',source='src/parkweave/case_goal_results.py:structure',actual_product_failures=2),dict(id='ML-GOAL-2',summary='Goal-results returns HTTP200 LOCAL_OUTPUTS_VERIFIED for an unproven manual_lock with absent LOCK event, wrong owner or different step; original plan GET rejects each with HTTP409.',source='src/parkweave/case_goal_results.py:read',actual_product_failures=3)],
 observer_faults=[dict(windows=['probes','browser-probe'],description='Private probe directory initially did not load tests/conftest.py; 12 fixture-setup errors; corrected using explicit -p conftest, no product failure inferred.'),dict(windows=['probes-fixture-corrected'],description='Three-lock oracle attempted BEGIN on already VERIFIED P4; original contract correctly returns409. Corrected observer uses real receipt REOPEN and NEEDS_RECHECK before BEGIN; selected test PASS.')],
 independent_update_preserve=dict(scope='P1-P5 REGISTERED_CASE_CHAIN',source_change='actual P4 receipt REOPEN after original SUBMIT/ACKNOWLEDGE and P5 REVALIDATE',expected_preserve=['P1','P2','P3'],expected_update=['P4','P5'],both_locked_current_states='LOCK_CONFLICT',old_verified_snapshots_assignments_ids_lock_refs_and_events_preserved=True,readonly_recovery_no_observation_sql_write=True,explicit_unlock_does_not_revalidate=True),
 other_evidence=['Historical same-key LOCK after UNLOCK and new ADOPT does not relock current plan; original immutable event remains recoverable.', 'Three real active locks reserve all three unlock slots; fourth LOCK refused at revision60; actual source REOPEN and one ordinary command consume only unreserved slot; explicit three UNLOCKs end at revision64 with no orphan lock.', 'Six event tamper cases rejected with unchanged business/source snapshot.', 'Actual loopback HTTP/PostgreSQL/Chromium 390 and320 conflict-card screenshots viewed; no horizontal overflow; only UNLOCK action, old verification retained.'],
 remote_verification=json.loads((OUT/'remote-readonly.json').read_text()),
 private_artifacts=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('report.json','write_report.py')],
 limits=['No dev integration authorized by this BLOCKED review.','No full repository, full AT25-27 or general DAG acceptance.','No Windows acceptance or existing CI query.','No formal ServiceRelease/Approval, real fulfillment, real Case completion, notifications, deployment, model call or new grants.','Private raw failed XML and logs are not suitable for publication.'])
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(decision=report['decision'],reviewed_sha=report['reviewed_sha'],source_count=len(frozen),source_drift=drift,windows=[{k:w[k] for k in ('name','tests','passed','failures','errors','skipped','junit_seconds')} for w in windows],report_sha256=sha(OUT/'report.json'))))
