"""Three pre-frozen-oracle probes; only original owned isolated template fixture."""
from contextlib import contextmanager
from pathlib import Path
from hashlib import sha256
import copy,inspect,json,os,sqlite3,subprocess,sys,threading,time
import pytest
from psycopg.types.json import Jsonb
from parkweave.template_consumer import Consume
from test_template_consumer import template_consumption,headers,body,products,consume,resume
from test_ordinary_template_inputs import serving
from template_candidate_support import ENTERPRISES,PARK,grant_snapshot
from ordinary_case_step_support import worker_once


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def fp(x):return sha256(canonical(dict(action='CONSUME',**x)).encode()).hexdigest()
def evidence(name,value):
 p=Path(os.environ['PARKWEAVE_INDEPENDENT_DEMO_EVIDENCE']);p.mkdir(parents=True,exist_ok=True)
 (p/(name+'.json')).write_text(json.dumps(value,sort_keys=True,indent=2,default=str)+'\n')
def pin(f):
 response=f['client'].get('/api/template-consumer/catalog',headers=headers(f));assert response.status_code==200
 item=response.json()['templates'][0];data=body(f);data['expected_catalog_sha256']=item['catalog_binding']['sha256'];return data

def journal(f):
 with f['repository'].connect() as c:return {t:[dict(x) for x in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ('consumer_instances','consumer_requests','consumer_stages')}


def test_literal_fingerprints_and_creation_get_never_send_or_change_journal(template_consumption,monkeypatch):
 f=template_consumption
 literals=json.loads(Path(os.environ['PARKWEAVE_INDEPENDENT_LITERAL_INPUTS']).read_text())
 for name in ('omitted_catalog_pin','explicit_pin'):
  value=literals[name];normalized=Consume.model_validate(value['normalized_body']).model_dump(mode='json',exclude_none=True)
  assert normalized==value['normalized_body'] and fp(normalized)==value['sha256']
 data=pin(f);bad=copy.deepcopy(data);bad['expected_catalog_sha256']=None
 before=products(f['owner']);j=journal(f)
 assert consume(f,key='independent-null',data=bad).status_code==422
 assert products(f['owner'])==before and journal(f)==j
 key='independent-consume';row=consume(f,key=key,data=data).json()
 assert resume(f,row,key='independent-non-consume-resume').status_code==200
 before=products(f['owner']);j=journal(f);authority=grant_snapshot(f['owner']);journal_bytes=sha256(f['repository'].path.read_bytes()).hexdigest()
 original=f['repository'].connect
 @contextmanager
 def readonly(write=False):
  assert write is False,'recovery attempted a consumer journal write transaction'
  with original(write=False) as c:yield c
 def no_send(*a,**kw):raise AssertionError('creation GET attempted product send/resume/consume')
 with monkeypatch.context() as patch:
  patch.setattr(f['repository'],'connect',readonly)
  for name in ('consume','resume','_perform'):patch.setattr(f['consumer'],name,no_send)
  patch.setattr(f['store'],'submit',no_send)
  path='/api/template-consumer/creation-recovery';observations=[]
  for request_key,expected,index,status in [(key,fp(data),0,200),(key,'0'*64,0,409),('independent-non-consume-resume',fp(data),0,409),(key,fp(data),1,200),('own-absent-key',fp(data),0,200)]:
   r=f['client'].get(path,params=dict(request_key=request_key,expected_fingerprint_sha256=expected),headers=headers(f,index))
   assert r.status_code==status,r.text
   result=r.json();observations.append(dict(key=request_key,index=index,status=status,response=result))
   if index or request_key=='own-absent-key':assert result['status']=='NOT_OBSERVED' and result['instance'] is None
  first=observations[0]['response'];assert first['status']=='RECORDED_INSTANCE' and first['instance']['instance_id']==row['instance_id']
 assert products(f['owner'])==before and journal(f)==j and grant_snapshot(f['owner'])==authority
 assert sha256(f['repository'].path.read_bytes()).hexdigest()==journal_bytes
 evidence('literal-and-readonly-creation',dict(literal_SHA256={k:literals[k]['sha256'] for k in ('omitted_catalog_pin','explicit_pin')},observations=observations,journal_before_after_sha256=journal_bytes,readonly_transactions_only=True,product_and_authority_unchanged=True,original_worker_not_selected=True))


def test_actual_journal_wait_must_recheck_catalog_before_preparation_send(template_consumption,tmp_path,monkeypatch):
 f=template_consumption;data=pin(f);row=consume(f,key='independent-before-journal-wait',data=data).json()
 worker_once((f['store'],),tmp_path/'worker')
 assert f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f)).json()['run_state']=='SUCCEEDED'
 before=products(f['owner']);authority=grant_snapshot(f['owner'])
 ready=threading.Event();proceed=threading.Event();counter=[0];worker_ident=[None];responses=[];errors=[];original=f['consumer']._available
 def observed(*args,**kwargs):
  result=original(*args,**kwargs);counter[0]+=1
  # Resume entry, confirmed CREATE_RUN, then first CREATE_PREPARATION.
  if counter[0]==3:
   worker_ident[0]=threading.get_ident();ready.set();assert proceed.wait(3),'observer did not release pin-check gate'
  return result
 def request():
  try:
   t=time.monotonic();r=resume(f,row,key='independent-explicit-materials');responses.append(dict(status=r.status_code,response=r.json(),start_monotonic=t,end_monotonic=time.monotonic()))
  except BaseException as e:errors.append(dict(type=type(e).__name__,message=str(e)))
 holder=sqlite3.connect(f['repository'].path,timeout=3);thread=threading.Thread(target=request);wait_frame=None;source_after=None
 with monkeypatch.context() as patch:
  patch.setattr(f['consumer'],'_available',observed)
  thread.start()
  try:
   assert ready.wait(3),'original preparation stage pin check not reached'
   holder.execute('BEGIN IMMEDIATE');proceed.set();deadline=time.monotonic()+2
   while time.monotonic()<deadline:
    frame=sys._current_frames().get(worker_ident[0])
    while frame:
     if frame.f_code.co_filename.endswith('template_consumer.py') and frame.f_code.co_name=='connect':
      lines=Path(frame.f_code.co_filename).read_text().splitlines();source=lines[frame.f_lineno-1]
      if 'BEGIN IMMEDIATE' in source:
       wait_frame=dict(function='connect',line=frame.f_lineno,source=source.strip(),observed_monotonic=time.monotonic());break
     frame=frame.f_back
    if wait_frame:break
    time.sleep(.01)
   assert wait_frame,'actual original SQLite BEGIN IMMEDIATE wait was not observed'
   with f['owner'].connect() as c:
    source=c.execute('SELECT source FROM preparation_catalog WHERE park_id=%s',(PARK,)).fetchone()['source']
    source_after={**source,'revision':'2','statement':'SYNTHETIC independent current directory advanced during original journal lock wait'}
    c.execute('UPDATE preparation_catalog SET source=%s WHERE park_id=%s',(Jsonb(source_after),PARK))
  finally:
   holder.commit();holder.close();proceed.set();thread.join(10)
 assert not thread.is_alive() and not errors,errors
 after=products(f['owner']);assert grant_snapshot(f['owner'])==authority
 proof=dict(wait_frame=wait_frame,actual_sqlite_journal_wait=True,catalog_source_after=source_after,responses=responses,errors=errors,available_check_count=counter[0],before_counts={k:len(v) for k,v in before.items()},after_counts={k:len(v) for k,v in after.items()},authority_unchanged=True,original_deadlines_or_timeouts_modified=False,original_human_resume=True,source_pin=data['expected_catalog_sha256'])
 evidence('actual-journal-wait-catalog-recheck',proof)
 assert responses[0]['status'] in (403,409),responses
 assert after==before,'a newly stale catalog pin was used to send a preparation stage after actual journal wait'


def test_original_full_html_late_actual_403_after_identity_aba_does_not_clear_new_input(template_consumption,tmp_path):
 f=template_consumption;before=products(f['owner']);script=Path(os.environ['PARKWEAVE_INDEPENDENT_HTML_SCRIPT'])
 with serving(f['client'].app) as base:
  config=dict(base=base,token=f['tokens'][ENTERPRISES[0]],other_token=f['tokens'][ENTERPRISES[1]],mode='independent-late403')
  with (tmp_path/'html.stdout').open('w') as out,(tmp_path/'html.stderr').open('w') as err:
   child=subprocess.Popen(['node',str(script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True);timer=threading.Timer(45,child.terminate);timer.start()
   try:
    child.stdin.write(json.dumps(config)+'\n');child.stdin.flush()
    for line in child.stdout:
     out.write(line);out.flush();item=json.loads(line)
     if item.get('control')=='independent_revoke':
      with f['owner'].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='PREPARE'",(ENTERPRISES[0],))
      child.stdin.write('{}\n');child.stdin.flush()
    code=child.wait(timeout=5)
   finally:
    timer.cancel()
    if child.poll() is None:child.terminate();child.wait(timeout=5)
 assert code==0,(tmp_path/'html.stderr').read_text()
 result=json.loads((tmp_path/'html.stdout').read_text().splitlines()[-1]);assert result['checks']==5
 assert products(f['owner'])==before
 evidence('original-full-html-late403',dict(result=result,body_never_stored=True,real_browser=False,owned_fixture_revocation_only=True,business_unchanged=True))
