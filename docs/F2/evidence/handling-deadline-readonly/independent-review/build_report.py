from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/independent-handling-deadline-review';SHA='9e0d7cf5f76ba768f98c77121f7bc0f7923ecb97'
EXPECTED={'refs/heads/candidate/handling-deadline-readonly-20261010':SHA,'refs/heads/dev/f1-foundation':'799419cee674ebe0bab215cce2a977c5450c3677','refs/heads/main':'31e7acb7e53bb1ab6465b9daae59de28757f7583'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def artifact(p):return dict(path=str(p),sha256=digest(p),bytes=p.stat().st_size)
def utc(x):return datetime.fromtimestamp(x,timezone.utc).isoformat()
def read(n):return json.loads((OUT/n).read_text())
manifest=read('frozen-source.json');before=read('source-before.json');after=read('source-after.json');remote=lambda n:{l.split()[1]:l.split()[0] for l in (OUT/n).read_text().splitlines()}
assert len(manifest)==340 and before['drift']==after['drift']==[] and before['sha']==after['sha']==SHA
assert all((ROOT/p).is_file() and digest(ROOT/p)==h for p,h in manifest.items())
assert digest(OUT/'frozen-source.json')==digest(ROOT/'.runtime/handling-deadline/frozen-source.json')=='9c3f360e2cbd36a62f7bea822db9e742388474ebedfeef445a1ded8a3490600f'
assert remote('remote-before.raw')==remote('remote-final.raw')==EXPECTED and not (OUT/'git-status-final.txt').read_text()
assert (OUT/'branch-final.txt').read_text().strip()=='candidate/handling-deadline-readonly-20261010'
assert OUT.stat().st_mode&0o777==0o700 and (OUT/'ignored-directory-check.txt').read_text().strip().endswith('/report.json')
windows=[]
for name in ['related13','independent-oracles','owned-restart','independent-waits']:
 ex=read(name+'-execution.json');xml=ET.parse(OUT/(name+'-junit.xml')).getroot();tc=xml.findall('.//testcase')
 counts={k:sum(c.find(k) is not None for c in tc) for k in ('failure','error','skipped')};counts['passed']=len(tc)-sum(counts.values());counts['tests']=len(tc)
 ids=[c.attrib.get('classname','')+'::'+c.attrib.get('name','') for c in tc]
 assert ex['returncode']==0 and counts['failure']==counts['error']==counts['skipped']==0
 windows.append(dict(name=name,modules=ex['modules'],module_count=len(ex['modules']),counts=counts,returncode=0,natural_exit=True,minimal_environment=ex['minimal_environment'],start_utc=utc(ex['start']),end_utc=utc(ex['end']),junit_seconds=sum(float(s.get('time','0')) for s in xml.findall('.//testsuite')),controlled_seconds=ex['end']-ex['start'],test_ids_sha256=hashlib.sha256('\n'.join(ids).encode()).hexdigest(),artifacts=[artifact(OUT/(name+s)) for s in ['-execution.json','-junit.xml','-pytest.log','-progress.json']]))
assert [w['counts']['passed'] for w in windows]==[458,44,1,2]
report={
 'decision':'LIMITED_PASS','exact_sha':SHA,'branch':'candidate/handling-deadline-readonly-20261010','generated_utc':datetime.now(timezone.utc).isoformat(),
 'scope':'F2-T03/AT29 bounded source-explicit synthetic read-only working-time calculation on the original material page. No legal pause authority or formal SLA accepted.',
 'windows':windows,'all_windows_naturally_exited':True,'related_modules':13,'related_complete_module_passed':458,'extra_oracles_passed_in_three_separate_windows':[44,1,2],'total_passed_across_four_windows':505,'product_failures':0,'observer_failures':0,
 'source':dict(before=before,after=after,source_paths=340,initial_and_final_zero_drift=True,final_manifest_recomputed=True,source_writes_by_reviewer=False,artifacts=[artifact(OUT/n) for n in ['source-before.json','source-after.json','frozen-source.json']]),
 'git':dict(actual_remote_before=remote('remote-before.raw'),actual_remote_after=remote('remote-final.raw'),candidate_exact=True,dev_unmerged_at_final_read=True,main_unchanged=True,initial_and_final_status_clean=True,no_reviewer_git_writes=True,unpublished_files='Only ignored private probes/logs/XML/browser evidence/report in this0700 directory; no unpushed tracked files at final status.',artifacts=[artifact(OUT/n) for n in ['remote-before.raw','remote-before.stderr','remote-final.raw','remote-final.stderr','head-final.txt','branch-final.txt','git-status-final.txt','ignored-directory-check.txt']]),
 'original_requirements_reviewed':['Product6.2: handling_policy calendar/target/applicable source; absent formal source cannot invent commitment or policy-derived authority.','Product12.2: explicit business timezone/calendar, authorized recorded pause; no artificial SLA improvement and UNKNOWN missing timestamps.','Original AT29 requires legal and illegal stop-clock coverage. This feature has no legal stop-clock contract and does not satisfy allAT29.','Frozen PR0 distinguishes engineering UTC/half-open/hold/lease checks from formal calendar/SLA and authorized pause.'],
 'independent_oracles':[
  dict(count=24,description='Independent expected working-second tick list across four explicitly declared days including CLOSED holiday;8 starts at/before/inside/after half-open boundaries times3 targets. Expected deadline is target-th eligible second end; elapsed is eligible tick count, independent of implementation calendar parsing/loop.'),
  dict(count=1,description='Fractional starting instant preserves actual2.125 elapsed seconds and4-second target without wall-clock rounding.'),
  dict(count=10,description='Own definitions: missing source/day/timezone/applicability/validity, invalid source hash/offset/boolean target, different enterprise and unauthorized pause never receive deadline/elapsed; private text not exposed.'),
  dict(count=2,description='Independently specified America/New_York spring nonexistent02:15 and fall ambiguous01:15 rejected even with supplied offsets.'),
  dict(count=1,description='Actual HTTP/PG12 concurrent repeatGETs and original assigned specialist read preserve all watched business/permission rows, cross enterprise/park reads403 hide source, host copied caller bytes remain unchanged, directory change-and-restore xminABA cannot revive old binding.'),
  dict(count=1,description='Actual original new material invalidates old deadline; explicit host rebind with unsupported pause remainsUNKNOWN. POST/PUT/DELETE405 with no business write.'),
  dict(count=1,description='Actual original PREPARE grant withdrawn after successfulGET yields403 with no source disclosure or read-side business writes.'),
  dict(count=1,description='Actual newly launched configured API distinctPID has no host source, returns defaultUNKNOWN to original owner and403 across enterprise; original business/history/permission rows unchanged.'),
  dict(count=3,description='Actual delayed successful HTTP response across same-Case refresh, identity change or otherCase does not publish into new context. Chromium320 has no old source text/XSS/storage or horizontal overflow.'),
  dict(count=1,window='owned-restart',description='Dedicated reviewer-owned temporaryPG actually stopped/started. PG PID/postmaster_start changed; system_identifier/databaseOID/data identity retained. Original enabled registry HTTP403; no proof capability reissued. Actual new configured APIPID returns defaultUNKNOWN and cross enterprise403;320 cold Chromium GETonly, no private text/storage, all watched business/permission rows identical.'),
  dict(count=1,window='independent-waits',description='Actual pg_stat_activity Lock observed on preparation row. Successful source before waiting expires during wait; lock released only afterDB expiry. GET200 UNKNOWN source-not-current; observed_at later than expiry and deadline unset; all business/permission rows unchanged.'),
  dict(count=1,window='independent-waits',description='Actual advisory identityLock wait observed. Original PREPARE grant revoked while authorized owner holdsX; release yields403, no source reference or business writes.')
 ],
 'fixture_and_environment':{'own_uuid_databases':True,'loopback_http_and_chromium':True,'controlled_subprocesses_minimal_environment':True,'own_restart_did_not_restart_other_fixtures':True,'new_api_and_postgres_processes_naturally_owned_and_cleaned':True,'issued_nonce_or_capability_not_copied_forged_or_reissued':True,'original_fixture_seed_only_no_new_grants_roles_or_source_DDL':True,'watched_tables':['principals','capability_grants','preparation_grants','field_grants','action_grants','run_assignments','preparation_catalog','preparations','preparation_events','preparation_evidence','runs','cases','operations','outbox']},
 'output_isolation':{'old_material_objections_imported_and_OUT_redirected_before_pytest':True,'all_collected_modules_Path_OUT_redirected_before_test_calls':True,'explicit_modules':['test_material_objections_browser','test_new_enterprise_local_chain','test_new_enterprise_local_chain_browser','test_handling_deadline_browser'],'root_or_tracked_evidence_overwritten_by_reviewer':False,'wrapper_and_probe_hashes_recorded':True},
 'limitations':['No legal stop-clock authority, independent pause approval/end/immutable journal/CAS contract; all nonempty pause declarationsUNKNOWN.','No real policy calendar/holiday/time limit/agency acceptance/formal SLA/violation conclusion/Case completion or full originalAT29 accepted.','Source starts at original synthetic preparationCREATE only, not real agency acceptance.','Host source mapping is same-process ephemeral configuration; newStore/newconfigured API defaultsUNKNOWN, old enabled registry rejects403 afterPGrestart; no durable formal clock or transferable fixture proof.','Catalog binding hash/xmin is read-time observation; no serial guarantee against arbitrary trusted owner noncooperative catalog writes.','No full-repository/fullAT/Windows/F1 acceptance, new permission or production activation, external notification, model call, deployment, main change or forcepush.','No root developer or prior unrelated candidate pass counts used as this independent acceptance.','Only exact9e0d runtime accepted; source-bearing changes require new review.'],
 'supporting_artifacts':[artifact(OUT/n) for n in ['run.py','wrapper.py','test_deadline_independent.py','test_owned_restart.py','test_waiting_independent.py','build_report.py','related-modules.json']],
 'private_browser_and_safe_probe_evidence':[artifact(p) for p in sorted((OUT/'browser').rglob('*')) if p.is_file()],
 'report_visibility':'Safe classes/counts/node IDs/hashes; raw failure/token-bearing logs/XML remain private. No actual failures in these four windows.'
}
assert sum(o['count'] for o in report['independent_oracles'])==47
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');h=digest(OUT/'report.json');(OUT/'report.sha256').write_text(h+'  report.json\n')
print(json.dumps({'decision':'LIMITED_PASS','exact_sha':SHA,'report':str(OUT/'report.json'),'sha256':h,'windows':[dict(name=w['name'],passed=w['counts']['passed'],junit_seconds=w['junit_seconds'],controlled_seconds=w['controlled_seconds']) for w in windows],'source_paths':340,'drift':0,'git_clean':True,'actual_remote_exact':True}))
