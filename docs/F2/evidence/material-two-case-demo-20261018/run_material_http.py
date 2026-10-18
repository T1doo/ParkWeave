from pathlib import Path
from contextlib import contextmanager
import hashlib,json,os,signal,subprocess,sys,time,traceback,uuid
import httpx,psycopg
from psycopg.rows import dict_row
from scripts import material_only_demo as demo
os.umask(0o077)
R=Path.cwd();D=R/'.runtime/material-two-case-demo-20261018';P=Path('/tmp/parkweave-material-demo-fsnwe42i')
PY=R/'.venv/bin/python';SOURCE='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765';PORT=8765
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==SOURCE
tokens=json.loads((P/'sessions.json').read_text());marker=json.loads((P/'state.json').read_text())
assert marker['source_commit']==SOURCE
traffic=[];settlements=[];exports=[];cases=[]
def emit(name,value):
 (D/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
def request(client,actor,method,path,body=None,status=200):
 headers={'Authorization':'Bearer '+tokens[actor]}
 if method=='POST':headers['Idempotency-Key']='material-'+uuid.uuid4().hex
 response=client.request(method,path,json=body,headers=headers)
 traffic.append(dict(actor=actor,method=method,path=path,status=response.status_code))
 if response.status_code!=status:
  (P/'logs/http-refusal.log').open('a').write(json.dumps(dict(path=path,status=response.status_code,body=response.text))+'\n')
 assert response.status_code==status,(method,path,response.status_code)
 return response.json()
@contextmanager
def running(label):
 log=(D/(label+'.stdout')).open('x');err=(D/(label+'.stderr')).open('x')
 env=demo.minimal_environment(os.environ,PYTHONDONTWRITEBYTECODE='1')
 child=subprocess.Popen([str(PY),'-B','-m','scripts.material_only_demo','serve','--state-dir',str(P),'--port',str(PORT)],cwd=R,env=env,stdout=log,stderr=err)
 ready=None;start=time.monotonic()
 try:
  deadline=start+25
  while time.monotonic()<deadline:
   if child.poll() is not None:raise RuntimeError('owned launcher exited')
   for line in (D/(label+'.stdout')).read_text().splitlines():
    try:ready=json.loads(line)
    except ValueError:pass
   if ready and ready.get('api_pid'):break
   time.sleep(.1)
  assert ready and ready.get('api_pid'),'owned launcher not ready'
  with httpx.Client(base_url=ready['url'],timeout=10,trust_env=False) as client:
   health=client.get('/health').json();assert health['process_id']==ready['api_pid'] and health['schema']==32
   assert ready['local_synthetic_demo_profile'] is False
   yield client,ready
 finally:
  if child.poll() is None:child.send_signal(signal.SIGTERM)
  child.wait(timeout=35);log.close();err.close()
  settlement=dict(label=label,launcher_pid=child.pid,launcher_exit=child.returncode,ready=ready,elapsed_seconds=time.monotonic()-start,postmaster_marker_absent=not(P/'data/postmaster.pid').exists(),stop_unconfirmed_marker= (P/'stop-unconfirmed').exists())
  settlements.append(settlement);emit(label+'-settlement.json',settlement)
  assert child.returncode==0 and settlement['postmaster_marker_absent'] and not settlement['stop_unconfirmed_marker']
def snapshot():
 with psycopg.connect(demo.dsn(P),row_factory=dict_row) as c:
  c.execute('SET TRANSACTION READ ONLY')
  auth=demo.authority(c)
  tables=('runs','cases','preparations','preparation_evidence','preparation_events','model_steps','model_plans','run_assignments','controlled_plans')
  counts={name:c.execute('SELECT count(*) n FROM '+name).fetchone()['n'] for name in tables}
  states=[dict(row) for row in c.execute('SELECT p.id preparation_id,p.run_id,p.case_id,p.state,p.revision,p.review_sha256,r.state run_state,c.state case_state FROM preparations p JOIN runs r ON r.id=p.run_id JOIN cases c ON c.id=p.case_id ORDER BY p.id').fetchall()]
  restrictions=dict(c.execute("SELECT has_table_privilege('parkweave_app','principals','INSERT') principal_insert,has_table_privilege('parkweave_app','principals','UPDATE') principal_update,has_table_privilege('parkweave_app','capability_grants','UPDATE') grant_update,has_table_privilege('parkweave_app','preparation_catalog','INSERT') catalog_insert,has_table_privilege('parkweave_app','controlled_plans','INSERT') plan_insert").fetchone())
  assert not any(restrictions.values())
  return dict(authority=auth,counts=counts,states=states,restrictions=restrictions)
html=(R/'src/parkweave/web.html').read_text()
a=html.index('function materialPackText(x)');b=html.index('async function materialPackAction',a)
parts=[next(line for line in html.splitlines() if line.startswith('const '+name+'=')) for name in ('readinessTruth','readinessReasons')]+[html[a:b]]
js='\n'.join(parts)
def export(client,case,label):
 readiness=request(client,'enterprise','GET','/api/preparations/'+case['preparation_id']+'/readiness')
 program="const fs=require('fs'),vm=require('vm');const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(vm.runInNewContext(x.source+'\\nmaterialPackText('+JSON.stringify(x.readiness)+')',{}, {timeout:1000}));"
 p=subprocess.run(['node','-e',program],input=json.dumps(dict(source=js,readiness=readiness)),text=True,capture_output=True,timeout=10)
 assert p.returncode==0,('NodeVM original pure material text generator',p.returncode)
 raw=p.stdout.encode();assert case['case_id'] in p.stdout and case['preparation_id'] in p.stdout
 assert case['need'] in p.stdout and case['outline'] in p.stdout
 assert 'SYNTHETIC' in p.stdout and 'Case目标未完成' in p.stdout and 'NOT_SUBMITTED' in p.stdout
 path=P/'downloads'/('material-'+label+'.txt');path.write_bytes(raw)
 item=dict(label=label,file=path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),case_id=case['case_id'],preparation_id=case['preparation_id'],source_js_sha256=hashlib.sha256(js.encode()).hexdigest(),mechanism='ORIGINAL_PURE_JS_TEXT_GENERATOR_IN_NODE_VM_FROM_REAL_HTTP_READINESS',browser_download=False)
 exports.append(item);emit('export-'+label+'.json',item)
 emit('readiness-'+label+'.json',readiness)
 return raw
def main():
 before=None;final=None
 with running('first-start') as (client,ready):
  before=snapshot();assert all(n==0 for n in before['counts'].values());assert before['authority']==marker['authority']
  emit('initial-business-snapshot.json',before)
  directory=request(client,'enterprise','GET','/api/preparation-catalog')
  assert len(directory['services'])==len(directory['reviewers'])==1
  assert directory['reviewers'][0]['id']==marker['ids']['specialist']
  for label,need,outline in [('A','SYNTHETIC A：整理厂房设备维护材料，核对三台设备的维护记录。','SYNTHETIC A：设备清单 3 项；维护记录 2 份。'),('B','SYNTHETIC B：整理员工培训材料，核对十二人的安全培训记录。','SYNTHETIC B：培训名单 12 人；签到记录 1 份；课程提纲 4 项。')]:
   run=request(client,'enterprise','POST','/api/runs',dict(goal=need,source='SYNTHETIC',action='case.create'),202)['run_id']
   deadline=time.monotonic()+20
   while True:
    value=request(client,'enterprise','GET','/api/runs/'+run)
    if value.get('state')=='SUCCEEDED':break
    assert time.monotonic()<deadline,'ordinary worker did not finish original case.create'
    time.sleep(.15)
   created=request(client,'enterprise','POST','/api/preparations',dict(run_id=run,service_id='synthetic-material-preparation',service_version=1,reviewer_id=marker['ids']['specialist']),201)
   id=created['preparation_id'];current=created
   for slot,text in [('need_summary',need),('material_outline',outline)]:
    current=request(client,'enterprise','POST','/api/preparations/'+id+'/commands',dict(action='ADD_EVIDENCE',expected_revision=current['revision'],slot=slot,text=text,source_kind='USER_STATEMENT' if slot=='need_summary' else 'DOCUMENT_EXCERPT',source_label='SYNTHETIC '+label+' v1'))
   request(client,'enterprise','POST','/api/preparations/'+id+'/commands',dict(action='REVIEW',expected_revision=current['revision'],reason='SYNTHETIC forbidden owner self-review'),403)
   current=request(client,'specialist','POST','/api/preparations/'+id+'/commands',dict(action='REVIEW',expected_revision=current['revision'],reason='SYNTHETIC '+label+' 专员独立核对双槽材料'))
   assert current['state']=='REVIEWED'
   request(client,'specialist','POST','/api/preparations/'+id+'/commands',dict(action='CONFIRM',expected_revision=current['revision'],reason='SYNTHETIC forbidden specialist owner confirmation'),403)
   current=request(client,'enterprise','POST','/api/preparations/'+id+'/commands',dict(action='CONFIRM',expected_revision=current['revision'],reason='SYNTHETIC '+label+' 企业确认本次资料'))
   assert current['state']=='LOCAL_CONFIRMED'
   case=dict(label=label,run_id=run,case_id=current['case_id'],preparation_id=id,revision=current['revision'],need=need,outline=outline)
   view=request(client,'enterprise','GET','/api/preparations/'+id);assert view['preparation']['state']=='LOCAL_CONFIRMED'
   case['view']=view;cases.append(case);export(client,case,label)
  assert len({x['case_id'] for x in cases})==len({x['run_id'] for x in cases})==len({x['preparation_id'] for x in cases})==2
  for case in cases:
   raw=(P/'downloads'/('material-'+case['label']+'.txt')).read_text()
   other=next(x for x in cases if x is not case);assert other['need'] not in raw and other['outline'] not in raw
  final=snapshot();assert final['authority']==before['authority'] and final['counts']==dict(runs=2,cases=2,preparations=2,preparation_evidence=4,preparation_events=10,model_steps=0,model_plans=0,run_assignments=0,controlled_plans=0)
  emit('before-restart-business-snapshot.json',final)
 with running('restart') as (client,ready):
  restart_before=snapshot();assert restart_before==final
  for case in cases:
   view=request(client,'enterprise','GET','/api/preparations/'+case['preparation_id']);assert view==case['view']
   reviewer=request(client,'specialist','GET','/api/preparations/'+case['preparation_id']);assert reviewer['preparation']['state']=='LOCAL_CONFIRMED'
   raw=export(client,case,case['label']+'-restart');assert raw==(P/'downloads'/('material-'+case['label']+'.txt')).read_bytes()
  assert snapshot()==restart_before
  emit('after-restart-business-snapshot.json',snapshot())
 result=dict(setup_source_commit=marker['setup_source_commit'],tested_source_commit=SOURCE,scenario_count=2,scenario_labels=['A','B'],both_actual_http_case_material_review_confirmation=True,negative_role_requests_403=4,original_pure_js_text_exports=4,browser_download='NOT_RUN_SANDBOX_REFUSED',real_browser='REFUSED_ONCE_NO_RETRY',full_database_api_worker_restart=True,unchanged_readback_and_export_bytes=True,authority_unchanged=True,counts=final['counts'],settlements=settlements,exports=exports,traffic=traffic,private_state_retained=True,new_setup_count=1,principals=2,business_grants=6,preparation_catalog_rows=1,local_synthetic_demo_profile=False,real_model_calls=0,windows='NOT_RUN',formal_at='NOT_RUN')
 emit('http-material-final-result.json',result);emit('cases.json',cases)
 print(json.dumps({k:v for k,v in result.items() if k not in ('traffic','settlements','exports')},indent=2))
try:main()
except BaseException as error:
 (P/'logs/http-driver-failure.log').open('a').write(traceback.format_exc())
 emit('http-partial-failure.json',dict(error_type=type(error).__name__,traffic=traffic,settlements=settlements,cases_created=len(cases)))
 print('HTTP_MATERIAL_VALIDATION_FAILED: '+type(error).__name__+'; private trace retained',file=sys.stderr)
 raise SystemExit(1)
