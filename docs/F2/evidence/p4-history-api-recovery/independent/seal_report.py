from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, xml.etree.ElementTree as E
ROOT=Path('/workspace/ParkWeave')
OUT=ROOT/'.runtime/independent-p4-history-api-recovery-rereview'
SHA='ab0ece79710068d6a776e5281a09e01ed2c0c536'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def artifact(p): return dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size)
manifest=ROOT/'.runtime/p4-history-api-recovery-fixed/frozen-source.json'
assert sha(manifest)=='88a41baa8c071be950e67387d17ab0192c3c4092528fed9c8f6386920b2bd4e3'
paths=json.loads(manifest.read_text())
drift=[name for name,h in paths.items() if sha(ROOT/name)!=h]
assert len(paths)==363 and not drift
roles=sha(ROOT/'src/parkweave/roles.sql')
assert roles=='604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3'
assert (OUT/'head-final.raw').read_text().strip()==SHA
assert (OUT/'git-status-final.raw').read_text()==''
source=dict(exact_sha=SHA,source_paths=len(paths),manifest_sha256=sha(manifest),roles_sha256=roles,drift=drift)
(OUT/'source-after.json').write_text(json.dumps(source,indent=2)+'\n')
remote={line.split()[1]:line.split()[0] for line in (OUT/'remote-after.raw').read_text().splitlines()}
assert remote=={'refs/heads/candidate/p4-history-api-recovery-20261010':SHA,'refs/heads/dev/f1-foundation':'28f7a4f659626c4e2d2c0736bd7827b1ffe41381','refs/heads/main':'31e7acb7e53bb1ab6465b9daae59de28757f7583'}
assert not (OUT/'remote-after.stderr').read_text()
windows=[]
for name,expected in [('independent-api',9),('independent-browser',8),('related-twenty-four',600)]:
    m=json.loads((OUT/(name+'-execution.json')).read_text())
    s=E.parse(OUT/(name+'-junit.xml')).getroot().find('testsuite')
    n={k:int(s.attrib.get(k,'0')) for k in ['tests','failures','errors','skipped']}
    assert n==dict(tests=expected,failures=0,errors=0,skipped=0) and m['returncode']==0
    windows.append(dict(name=name,natural_exit=True,returncode=0,pass_count=expected,fail_count=0,error_count=0,skip_count=0,junit_seconds=float(s.attrib['time']),controlled_seconds=m['end']-m['start'],start_utc=datetime.fromtimestamp(m['start'],timezone.utc).isoformat(),end_utc=datetime.fromtimestamp(m['end'],timezone.utc).isoformat(),modules=m['modules'],minimal_environment=m['minimal_environment'],artifacts=[artifact(OUT/(name+x)) for x in ['-pytest.log','-junit.xml','-execution.json','-progress.json']]))
owned=json.loads((OUT/'owned-basetemp-safe.json').read_text())
pids={v['pid'] for v in owned}
bases={base for v in owned for base in v['basetemp']}
def collect(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if k.endswith('_pid') and type(x) is int: pids.add(x)
            collect(x)
    elif isinstance(v,list):
        for x in v: collect(x)
oracles=sorted(OUT.glob('independent-cases/**/*-safe.json'))
for p in oracles: collect(json.loads(p.read_text()))
remaining=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        args=p.joinpath('cmdline').read_bytes().decode(errors='replace').split('\0')
    except (FileNotFoundError,PermissionError,ProcessLookupError): continue
    if int(p.name) in pids or any(a in [str(OUT/'wrapper.py'),str(OUT/'run.py')] or any(a==b or a.startswith(b+'/') for b in bases) for a in args):
        remaining.append(int(p.name))
assert not remaining, remaining
resources=dict(all_windows_naturally_closed=True,remaining_owned_pids=remaining,known_owned_pids=sorted(pids),owned_basetemps=sorted(bases),checked_utc=datetime.now(timezone.utc).isoformat(),closed_scope=['pytest wrappers','owned temporary PostgreSQL','original issuer authorities','old and new API clients','Chromium'])
(OUT/'resources-after-safe.json').write_text(json.dumps(resources,indent=2)+'\n')
observation=next(OUT.glob('independent-cases/**/wrong-key-response-observation-safe.json'))
o=json.loads(observation.read_text())
assert o['server_unknown_key']=='NOT_OBSERVED' and not o['other_saved_report_rendered'] and o['safe_error_present'] and not o['body_or_proof_fabrication']
prior=ROOT/'.runtime/independent-p4-history-api-recovery-review/report.json'
assert sha(prior)=='9a7606b3933c9f88f2459a1ab701ff999999ba674b973c3de5e1ba6b5ff5d962'
report=dict(decision='LIMITED_PASS',exact_sha=SHA,branch='candidate/p4-history-api-recovery-20261010',reviewer='independent_service_plan_manual_lock_review',source_writer='root',created_utc=datetime.now(timezone.utc).isoformat(),windows=windows,separate_windows_not_aggregated_as_single_run=True,independent_product_failures=0,independent_observer_failures=0,prior_product_blocker=dict(exact_sha='2c964296488e42f2b162589b12e919647c96c13f',decision='BLOCKED',failed_window_preserved=True,report=artifact(prior),current_actual_retests=['Genuine original issuer response for another saved key rejected HTTP503 without result/history.','Genuine loopback response for another saved key rejected by original page; private result empty and correlation error shown.'],observation=artifact(observation)),source=dict(**source,before=artifact(OUT/'source-before.json'),after=artifact(OUT/'source-after.json')),git=dict(final_clean=True,clean_throughout_not_claimed=True,actual_remote=remote,verification_artifacts=[artifact(OUT/n) for n in ['head-final.raw','git-status-final.raw','remote-before.raw','remote-before.stderr','remote-after.raw','remote-after.stderr']]),owned_resources=dict(all_windows_naturally_closed=True,remaining_owned_pids=[],verification=artifact(OUT/'resources-after-safe.json')),permission_to_unfreeze=True,permission_scope='Only the reviewed product tree and root-authorized evidence/documentation integration; no approval for broader features or proof lifecycle recovery.',probes=[artifact(OUT/n) for n in ['test_independent_api.py','test_independent_browser.py','run.py','wrapper.py','seal_report.py']],safe_oracles=[artifact(p) for p in oracles],visual_evidence=[artifact(OUT/n) for n in ['changes-stale-320.png','changes-stale-390.png','changes-stale-1200.png','wrong-key-response-320.png']],visual_inspection='Actual 320px positive history retains original REQUEST_CHANGES and STALE, all goals and P5 limitation. Actual wrong-key page retains unknown input, shows correlation error and no private result.',independent_api_scope=['Two different API client PIDs, old confirmed exited before new; continuously live third original issuer. Exact original ACKNOWLEDGE and REQUEST_CHANGES documents survive explicit source version change as STALE.','Six concurrent repeated GET, unknown original key NOT_OBSERVED, history POST405, original P4 GET/POST403, no automatic replay.','Malformed closed IPC fields and bounded frame cases rejected403; valid read still200.','Original socket missing503 and replacement inode403; exact original listener restoration200, no authority restart.','Current original lease expiry or missing original proof403 without exposing history or reissuing authority.','Single body/report/text/hash mutation retaining independent original proof rejected409; no repair.','Original issuer exit503; original real generate call count remains exactly one over issuer lifetime.','Original issuer reply for another real saved key rejected503; no document, hash or proof fabrication.'],independent_browser_scope=['Wrong-key genuine HTTP response regression rejects, empty result and error.','Cold original page under new API PID reads exact original stale history via GET only; no token persistence or write replay.','Late actual response discarded after original key or preparation changes.','Canonical comparison accepts legitimate object-key reorder, preserves value types and array order.','Duplicate same history document, unknown status, and NOT_OBSERVED with result rejected without automatic replay.','320/390/1200 widths and original complete goals preserved.'],qualification_and_write_scope=dict(original_synthetic_fixtures_only=True,process_proof_never_serialized_or_reissued=True,no_formal_grants_or_assignment_repair=True,public_business_snapshot_excludes=['authorization_audit'],public_schema_index_privileges_unchanged_by_reads=True,five_log_bytes_include=['P1 preview','P2 preview','P3 preview','P4 preview','original RunAccess journal'],original_generate_calls_per_issuer_lifetime=1,child_generation_monitor_asserted=True,explicit_fixture_setup_or_source_actions_precede_snapshot_baselines=True),limits=['Only API client process replacement under a continuously live original fixture issuer is accepted; original issuing authority restart/proof lifecycle recovery NOT_IMPLEMENTED.','Metadata receipt preview history only; no actual materials fulfillment or human approval.','source_atomicity=false; SNAPSHOT_MATCH/STALE are snapshot comparisons, no CURRENT or atomic-source guarantee.','P5, Case completion, new formal Grants, resource effects, notifications, external effects and model calls are outside scope.','PG restart/WAL, complete AT14, full repository and Windows NOT_RUN in this review.'],root_results_not_borrowed=True,all_previous_review_directories_unmodified=True)
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
OUT.chmod(0o700)
for p in OUT.rglob('*'):
    if p.is_file(): p.chmod(0o600)
    elif p.is_dir(): p.chmod(0o700)
print(json.dumps(dict(decision=report['decision'],exact_sha=SHA,report_sha256=sha(OUT/'report.json'),windows=[{k:v for k,v in w.items() if k in ['name','pass_count','junit_seconds','controlled_seconds']} for w in windows],source_drift=0,remaining_owned_pids=[])))
