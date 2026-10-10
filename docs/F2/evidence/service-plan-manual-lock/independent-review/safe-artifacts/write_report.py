from pathlib import Path
import hashlib,json,subprocess,os,xml.etree.ElementTree as E
from datetime import datetime,timezone
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/independent-service-plan-manual-lock-final-review'
import sys
sys.path.insert(0,str(ROOT/'src'))
from parkweave.process_env import minimal_environment
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
 r=subprocess.run(['git',*args],cwd=ROOT,env=minimal_environment(os.environ),capture_output=True,text=True)
 assert r.returncode==0
 return r.stdout.strip()
frozen=json.loads((OUT/'frozen-source.json').read_text());drift=[p for p,h in frozen.items() if sha(ROOT/p)!=h];assert not drift
head=git('rev-parse','HEAD');assert head=='1a8d95e8cf532affc8e5b8c8503866c63b29d4c7'
old=ROOT/'.runtime/independent-service-plan-manual-lock-review/report.json';assert sha(old)=='f5bd6aeb6fceebac4996eca043610558448637253e8610f33393eb9f4671cb5d';first=json.loads(old.read_text())
windows=[]
for name in ('complete','original-blocker-probes','final-extra','managed-source-wait','managed-source-wait-strengthened'):
 p=OUT/(name+'-junit.xml');tree=E.parse(p);s=next(tree.iter('testsuite'));cases=list(tree.iter('testcase'))
 assert not any(t.find('failure') is not None or t.find('error') is not None or t.find('skipped') is not None for t in cases)
 execution=json.loads((OUT/(name+'-execution.json')).read_text())
 windows.append(dict(name=name,tests=int(s.attrib['tests']),passed=len(cases),failures=int(s.attrib['failures']),errors=int(s.attrib['errors']),skipped=int(s.attrib['skipped']),junit_seconds=float(s.attrib['time']),controlled_seconds=execution['end']-execution['start'],module_paths=execution['modules'],minimal_environment=execution['minimal_environment'],raw_junit_sha256=sha(p),raw_log_sha256=sha(OUT/(name+'-pytest.log'))))
original=E.parse(OUT/'original-blocker-probes-junit.xml')
retested=[dict(nodeid=t.attrib['classname']+'::'+t.attrib['name'],outcome='PASS',seconds=float(t.attrib['time'])) for t in original.iter('testcase') if t.attrib['name'].startswith(('test_original_goal_output_read_remains_available_after_owner_lock_events','test_goal_result_never_accepts_unproven_active_manual_lock'))];assert len(retested)==5
report=dict(decision='LIMITED_PASS',reviewed_sha=head,reviewed_branch=git('branch','--show-current'),reviewed_at_utc=datetime.now(timezone.utc).isoformat(),source_count=len(frozen),source_drift=drift,source_manifest_sha256=sha(OUT/'frozen-source.json'),worktree_status=git('status','--porcelain'),untracked_nonignored=git('ls-files','--others','--exclude-standard'),windows=windows,
 independent_extra_unique_test_count=27,managed_boundary_strengthened_repeat_not_additional_unique_test=True,
 original_five_product_failures_retested=retested,
 previous_blocked_review=dict(path=str(old.relative_to(ROOT)),sha256=sha(old),reviewed_sha=first['reviewed_sha'],decision=first['decision'],windows=first['windows'],blockers=first['blockers'],observer_faults=first['observer_faults'],original_failed_raw_logs_preserved_private=True),
 managed_boundary=json.loads((OUT/'managed-source-wait-observation.json').read_text()),
 independent_update_preserve=dict(scope='P1-P5 REGISTERED_CASE_CHAIN',actual_change='P4 receipt REOPEN after original SUBMIT/ACK and P5 REVALIDATE',expected_preserve=['P1','P2','P3'],expected_update=['P4','P5'],old_snapshots_step_ids_assignments_and_events_preserved=True,explicit_unlock_does_not_revalidate=True,read_only_recovery_and_goal_get_no_observation_write=True),
 additional_oracles=['Original LOCK/UNLOCK events remain readable through existing goal-results; original VERIFY retains identity and LOCK never substitutes for VERIFY.', 'Unproven/missing LOCK event, incorrect owner and step, wrong lock event reference, altered verified snapshot, missing VERIFY and duplicated actor/key all refused.', 'Resource deadline expires while actual goal/recovery GET waits on the last lifecycle row; LOCK_CONFLICT replaces current proof, history remains, no SQL observation write.', 'Current READ/PREPARE revocation precedes locked output proof; minimal denial leaks no private output.', 'Historical same-key LOCK after UNLOCK/new ADOPT does not relock the new plan.', 'Three active locks reserve three unlock slots; fourth LOCK refused; all three explicit UNLOCKs complete within real64-event boundary.', 'Late actual goal GET200/403 after successful LOCK does not replace the new context; explicit fresh GET returns current original proof.', 'Source-changed cold goal page uses only GET, retains historical proof, shows explicit unlock requirement and no current output.', 'Actual loopbackHTTP/PostgreSQL/Chromium390/320 conflict-card and goal-result screenshots inspected; no horizontal overflow or new business writes.'],
 remote_verification=json.loads((OUT/'remote-readonly.json').read_text()),
 private_artifacts=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('report.json','write_report.py')],
 limits=['Only bounded original registered Case chain, original synthetic roles/objects and source proofs reviewed; no general DAG.', 'Owner managed Run READ expiry is NOT_APPLICABLE: original lease target is service_executor. Actual owner goal read across executor-source READ expiry was tested; no owner lease or grant invented.', 'No formal ServiceRelease/Approval or real publication/fulfillment/Case completion/sharing/deployment/model invocation/new grants.', 'No full repository/full AT25-27/Windows acceptance or existing CI query; old a823a28 not migrated.', 'Previous BLOCKED windows and raw failures remain private and do not count as final acceptance.'])
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(decision=report['decision'],reviewed_sha=head,source_count=len(frozen),source_drift=drift,windows=[{k:w[k] for k in ('name','tests','passed','failures','errors','skipped','junit_seconds','controlled_seconds')} for w in windows],original_five_retested_pass=len(retested),report_sha256=sha(OUT/'report.json'))))
