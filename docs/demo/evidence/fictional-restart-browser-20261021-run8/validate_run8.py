"""Read-only original artifact/log audit; never rerun browser or business flow."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import zipfile
from scripts.fictional_park_restart_browser_once import unpack_font_diagnostics,charset_coverage
p=Path(__file__).parent
load=lambda n:json.loads((p/n).read_text())
r,run,job,check,meta=map(load,['result.json','run.json','job.json','check-run.json','artifact-metadata.json'])
source='fd7e36a98c080049c3d4f944174c0b8ad7c28b78'
assert r['source_sha']==run['head_sha']==source and run['run_number']==8 and run['run_attempt']==1
assert run['conclusion']==job['conclusion']==check['conclusion']=='success'
assert r['status']=='PASS' and r['stage']=='COLD_RECOVERY_CONFIRMED_STOP' and r['cold_restart']
assert 'error' not in r and 'finalization_errors' not in r
steps={s['name']:s for s in job['steps']}
assert steps['Actual fictional flow and same-instance cold recovery']['conclusion']=='success'
assert 'sha256:'+sha256((p/'artifact.zip').read_bytes()).hexdigest()==meta['digest']
with zipfile.ZipFile(p/'artifact.zip') as z:
 assert len(z.infolist())==9 and sum(i.file_size for i in z.infolist())<=8388608
 for i in z.infolist():assert z.read(i)==(p/i.filename).read_bytes()
 members=z.namelist();artifact_bytes=sum(i.file_size for i in z.infolist())
log=(p/'ci-job-original.log').read_text(encoding='utf-8')
assert 'Process completed with exit code 1' not in log
pending=[json.loads(s[s.index('{'):]) for s in log.splitlines() if 'PENDING_FINALIZATION' in s and 'observation_outcome' in s]
assert len(pending)==1 and pending[0]['observation_outcome']=='PASS'
a=dict(pending[0]);a['status']=a.pop('observation_outcome');a.pop('terminal_result');b=dict(r)
for d in [a,b]:
 for key in ['seconds','seconds_scope']:d.pop(key,None)
assert a==b
stage=[json.loads(s[s.index('{'):]) for s in log.splitlines() if 'STAGED_VERIFIED' in s]
assert len(stage)==1;stage=stage[0]
(p/'font-staging-report.json').write_text(json.dumps(stage,indent=2)+'\n')
assert stage['assets']==r['approved_official_font']['receipt']['assets']
font=stage['assets']['NotoSansCJKsc-Regular.otf'];license=stage['assets']['LICENSE']
assert font['size']==16437364 and font['git_blob_sha1']=='dc15562470b4f842321894787a0d066879ccff8b'
assert font['sha256']=='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
f=r['installed_CJK_font'];d=unpack_font_diagnostics(f)
(p/'font-diagnostics.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
points=set(d['required_codepoints']);assert len(points)==683
for name in ['inventory','system-ui','sans-serif']:
 command=d['commands'][name];assert command['returncode']==0 and command['raw_public_complete']
 for stream in ['stdout','stderr']:
  raw=command[stream].encode();assert len(raw)==command[stream+'_bytes'] and sha256(raw).hexdigest()==command[stream+'_sha256']
  (p/(name+'.'+stream)).write_bytes(raw)
 union=set().union(*(charset_coverage(s.split('\t')[4],points) for s in command['stdout'].splitlines()))
 assert union==points
assert f['union_covered_count']==683 and f['rendering_observed'] and len(f['visible_node_font_usage'])==26
for node in f['visible_node_font_usage']:
 assert not node['missing_codepoints'] and not node['invalid_sources']
 assert any(face['postscript_name']=='NotoSansCJKsc-Regular' and face['sha256']==font['sha256'] for face in node['matched_faces'])
for shot in r['screenshots']:assert sha256((p/shot['file']).read_bytes()).hexdigest()==shot['sha256']
assert len(r['screenshots'])==6
initial,cold=r['processes'],r['cold_processes']
assert initial['state_dir']==cold['state_dir'] and initial['url']==cold['url']
assert all(initial[k]!=cold[k] for k in ['api_pid','worker_pid','postgres_pid'])
assert initial['models']==cold['models']=='DISABLED'
reads=[x for x in r['responses'] if x.get('stage')=='COLD_READ_ONLY'];assert len(reads)==44 and all(x['method']=='GET' for x in reads)
posts=[x for x in r['responses'] if x['method']=='POST'];assert len(posts)==34 and all(200<=x['status']<300 for x in posts)
refused=[x for x in r['responses'] if x['status']==403];assert len(refused)==20 and all(x['method']=='GET' and x['path'].endswith('/fact-clarifications') for x in refused)
rr=r['restart_read_only'];assert rr['extra_business_POSTs']==0 and rr['new_context'] and rr['input_files_unchanged'] and rr['first_goalResultView_equal'] and rr['first_TXT_bytes_equal']
assert (p/'first-case-record-pack.txt').read_bytes()==(p/'restarted-case-record-pack.txt').read_bytes()
for key in ['preparation_id','case_id','run_id','plan_id']:assert r['first'][key] in (p/'first-case-record-pack.txt').read_text()
assert r['first_history_unchanged'] and r['authority_unchanged'] and r['run_assignments']==0 and r['owned_services_stopped']
assert not r['violations'] and not r['page_errors'] and r['receipt']['step']['state']=='LOCAL_ACKNOWLEDGED'
assert r['first_stage_seconds']<180 and r['seconds']<360 and r['cold_start_seconds']<50 and r['cold_read_seconds']<60
assert check['output'].get('summary') is None
seconds=(datetime.fromisoformat(job['completed_at'].replace('Z','+00:00'))-datetime.fromisoformat(job['started_at'].replace('Z','+00:00'))).total_seconds()
validation=dict(status='PASS_LIMITED_FICTIONAL_BROWSER_AND_SAME_INSTANCE_COLD_RECOVERY',source_sha=source,
 run_id=run['id'],job_id=job['id'],run_url=run['html_url'],run_number=8,run_attempt=1,
 job_seconds=seconds,browser_seconds=r['seconds'],browser_seconds_scope=r['seconds_scope'],
 browser_step_seconds=(datetime.fromisoformat(steps['Actual fictional flow and same-instance cold recovery']['completed_at'].replace('Z','+00:00'))-datetime.fromisoformat(steps['Actual fictional flow and same-instance cold recovery']['started_at'].replace('Z','+00:00'))).total_seconds(),first_stage_seconds=r['first_stage_seconds'],
 cold_start_seconds=r['cold_start_seconds'],cold_read_seconds=r['cold_read_seconds'],cold_context_and_stop_seconds=r['cold_context_and_stop_seconds'],
 terminal=dict(result='PASS',browser_step='success',process_exit_zero_inferred_from_step_success=True,job='success',
  stdout='PENDING_FINALIZATION observation,not terminal PASS',normalized_log_observation_equals_result=True,
  step_summary_body_verified=False,check_run_summary=None,public_job_HTML='sign-in/loading;no summary body status;not used as proof'),
 actual_scope=['First fictional DOM flow:review/confirm/NO_MODEL ADOPT/resources/dispatch/accept/manual receipt/ACK/P1-P5/TXT',
  'Second explicit material reuse,independent REVIEW-CONFIRM and pre-ADOPT/pre-dispatch cancellation;390px first history retained',
  'Same state/port real API-worker-PostgreSQL stop/restart with changed owned PIDs;no recovery setup/seed',
  'Fresh empty browser context UI login;44 GET responses,zero recovery POST;original deadline not renewed',
  'Source assertions compared complete same-role enterprise/executor dispatchView/receiptView,goalResultView and declared two Case-history projections',
  'Reexported TXT byte-identical;retained authority/input files;owned final stop checks completed'],
 view_proof_limit='Completed original source assertions;raw before/after full view pairs were not separately serialized as new artifacts;not whole-DB invariance',
 runtime_processes=dict(initial={k:initial[k] for k in ['api_pid','worker_pid','postgres_pid','url','state_dir']},cold={k:cold[k] for k in ['api_pid','worker_pid','postgres_pid','url','state_dir']}),
 actual_business_status={k:r['results'][k] for k in ['case_goal_completed','qualification','external_acceptance','offline_fulfillment']},
 business_POSTs=34,cold_GET_responses=44,refused_fact_clarification_GET403=20,cancel_scope=r['cancel_scope'],
 font=dict(size=font['size'],git_blob=font['git_blob_sha1'],sha256=font['sha256'],license_sha256=license['sha256'],
  codepoints=683,actual_resolved_chains=[683,683],guide_nodes=26,scope=f['rendering_observation_scope'],system_install=False,binary_in_public_archive=False),
 screenshot_captions={'01':'Guide CJK visible and legible;identity file input masked','03':'Notices/progress/local run viewport;no ACK body/status visible,ACK verified by JSON',
  '06':'Initial second cancellation banner visible','07':'390px first result viewport legible','08':'Restarted first TXT export viewport with exact Case/Run/preparation/plan IDs visible',
  '09':'Restarted preparation/Case list viewport,not cancellation banner;cancelled=true was asserted from UI view'},
 original_artifact=dict(files=members,uncompressed_bytes=artifact_bytes,zip_bytes=(p/'artifact.zip').stat().st_size,zip_sha256=sha256((p/'artifact.zip').read_bytes()).hexdigest()),
 limits=dict(job_seconds=600,browser_seconds=360,dependency_seconds=180,attempt=1,new_runs=1,reruns=0,files=10,bytes=8388608),
 tests=dict(new_product_pytest_runs=0,prior_targeted21_not_recounted=True,collection9386_retained_not_reexecuted=True),
 remaining=['Step summary body not independently retrieved;API null/public page sign-in boundary retained',
  'Not all683 per-glyph pixel acceptance;actual CDP proof only26 visible guide nodes plus inspected original viewports',
  'Run7 exact failed errno historically unknown;run8 success does not retroactively prove its root cause',
  'No cancellation after actual acceptance/receipt;only declared second pre-ADOPT cancellation scope',
  'Formal source/AT35/Windows owner-DACL/native installation/real models/actual business fulfillment remain unverified'])
(p/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:validation[k] for k in ['status','source_sha','job_seconds','browser_seconds','cold_start_seconds','cold_read_seconds','terminal','original_artifact']},indent=2))
