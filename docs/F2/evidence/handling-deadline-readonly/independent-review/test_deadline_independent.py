"""Independent oracles: no imports from handling-deadline developer tests."""
from datetime import datetime,timedelta,date,timezone
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import hashlib,json,os,sys,socket,subprocess,time
import pytest,httpx
from psycopg.types.json import Jsonb
from playwright.sync_api import sync_playwright
from conftest import fixture,pg
from test_preparation import preparation_fixture,filled,create,add,headers
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import handling_deadline as hd
from parkweave.process_env import minimal_environment

OUT=Path('/workspace/ParkWeave/.runtime/independent-handling-deadline-review/oracles')
UTC=timezone.utc
TABLES=('principals','capability_grants','preparation_grants','field_grants','action_grants','run_assignments','preparation_catalog','preparations','preparation_events','preparation_evidence','runs','cases','operations','outbox')
def sha(v):return hashlib.sha256(v.encode()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def calendar_hash(raw):raw['policy']['calendar_ref']['sha256']=sha(canonical(raw['calendar']))
def definition(first='2026-10-10',length=4,target=7,ranges=None,zone='UTC'):
    start=date.fromisoformat(first)
    text='SYNTHETIC Independent source PRIVATE_ORACLE_CLOCK <svg onload=globalThis.BAD_CLOCK=true>'
    source=dict(kind='SYNTHETIC',id='independent-source',revision=4,text=text,sha256=sha(text),valid_from='2026-01-01T00:00:00Z',valid_until='2027-01-01T00:00:00Z',service_id='synthetic-material-preparation',service_version=1,accepting_org_id='org-a')
    ref={k:source[k] for k in ('id','revision','sha256')};days=[]
    for i in range(length):
        d=(start+timedelta(days=i)).isoformat()
        windows=([] if i==1 else [('09:00:00+00:00','09:00:05+00:00'),('09:00:10+00:00','09:00:16+00:00')]) if ranges is None else ranges[i]
        days.append(dict(date=d,kind='WORKING' if windows else 'CLOSED',windows=[dict(start=d+'T'+a,end=d+'T'+b) for a,b in windows]))
    cal=dict(id='independent-calendar',revision=3,source_ref=ref,timezone=zone,first_date=first,last_date=(start+timedelta(days=length-1)).isoformat(),days=days)
    raw=dict(source=source,calendar=cal,policy=dict(source_ref=ref,calendar_ref=dict(id=cal['id'],revision=cal['revision'],sha256=sha(canonical(cal))),timezone=zone,target_seconds=target,start_basis='SYNTHETIC_PREPARATION_CREATE'),pauses=[])
    return raw

def compute(raw,start,observed):return hd.calculate(raw,start,observed,service_id='synthetic-material-preparation',service_version=1,org_id='org-a')
@pytest.mark.parametrize('offset,target',[(x,y) for x in (-1,0,3,5,9,10,15,16) for y in (1,7,12)])
def test_independent_per_second_clock(offset,target):
    raw=definition(target=target);base=datetime(2026,10,10,9,tzinfo=UTC);start=base+timedelta(seconds=offset);observed=base+timedelta(days=2,seconds=12)
    # Hard-coded independent expected ticks, not parsed implementation calendar or algorithm.
    ticks=[base+timedelta(days=d,seconds=s) for d in (0,2,3) for s in [0,1,2,3,4,10,11,12,13,14,15]]
    future=[t for t in ticks if t>=start];expected=future[target-1]+timedelta(seconds=1)
    elapsed=sum(start<=t<observed for t in ticks)
    result=compute(raw,start,observed)
    assert result['state']=='SYNTHETIC_CALCULATED' and datetime.fromisoformat(result['deadline_utc'])==expected
    assert result['deadline_local']==result['deadline_utc'] and result['elapsed_work_seconds']==elapsed
    assert result['legal_pause_decision']=='NOT_EVALUATED' and 'PRIVATE_ORACLE_CLOCK' not in json.dumps(result)

def test_fractional_start_elapsed_and_target_use_real_seconds():
    start=datetime(2026,10,10,9,tzinfo=UTC)+timedelta(microseconds=250000)
    result=compute(definition(target=4),start,start+timedelta(seconds=2,microseconds=125000))
    assert result['state']=='SYNTHETIC_CALCULATED' and result['deadline_utc']=='2026-10-10T09:00:04.250000+00:00' and result['elapsed_work_seconds']==2.125

@pytest.mark.parametrize('damage',['missing-source','missing-day','unknown-zone','pause','unauthorized-org','false-target','wrong-offset','missing-applicability','missing-validity','source-hash'])
def test_own_missing_or_inapplicable_inputs_never_invent_deadline(damage):
    raw=definition()
    if damage=='missing-source':raw.pop('source')
    elif damage=='missing-day':raw['calendar']['days'].pop(1);calendar_hash(raw)
    elif damage=='unknown-zone':raw['calendar']['timezone']=raw['policy']['timezone']='UNKNOWN/Unavailable';calendar_hash(raw)
    elif damage=='pause':raw['pauses']=[{'reason':'AWAITING_USER','claimed_authority':'RunPause'}]
    elif damage=='unauthorized-org':raw['source']['accepting_org_id']='org-b'
    elif damage=='false-target':raw['policy']['target_seconds']=True
    elif damage=='wrong-offset':raw['calendar']['days'][0]['windows'][0]['start']='2026-10-10T09:00:00+01:00';calendar_hash(raw)
    elif damage=='missing-applicability':raw['source'].pop('service_id')
    elif damage=='missing-validity':raw['source'].pop('valid_until')
    else:raw['source']['sha256']='0'*64
    result=compute(raw,datetime(2026,10,10,9,tzinfo=UTC),datetime(2026,10,10,10,tzinfo=UTC))
    assert result['state']=='UNKNOWN' and result['issues'] and result['deadline_utc'] is None and result['elapsed_work_seconds'] is None
    assert 'PRIVATE_ORACLE_CLOCK' not in json.dumps(result)

@pytest.mark.parametrize('day,offset,issue',[('2026-03-08','-05:00','NONEXISTENT_LOCAL_TIME'),('2026-11-01','-04:00','AMBIGUOUS_LOCAL_TIME')])
def test_explicit_dst_offsets_still_cannot_authorize_fold_or_gap(day,offset,issue):
    left='02:15:00' if day.endswith('03-08') else '01:15:00'
    raw=definition(day,1,ranges=[[(left+offset,'04:00:00-04:00' if offset=='-05:00' else '04:00:00-05:00')]],zone='America/New_York')
    start=datetime.fromisoformat(day+'T00:00:00'+offset);result=compute(raw,start,start+timedelta(minutes=5))
    assert result['state']=='UNKNOWN' and result['issues']==[issue]

def snapshot(f):
    with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in TABLES}

def source_for(f,p):
    with f[1].connect() as c:started=c.execute("SELECT created_at FROM preparation_events WHERE preparation_id=%s AND action='CREATE'",(p['preparation_id'],)).fetchone()['created_at']
    raw=definition((started.date()-timedelta(days=1)).isoformat(),4,target=30,ranges=[[('00:00:00+00:00','23:59:59+00:00')]]*4)
    return raw

def attach(f,p,raw=None):
    x=hd.IsolatedDeadlineSources(f[1],f[1]._case_fact_fixture_receipt,definitions={p['preparation_id']:raw or source_for(f,p)},enabled_for_isolated_tests=True);x.attach_store(f[0]);return x

@pytest.fixture
def own_http(preparation_fixture):
    f=preparation_fixture
    with actual_http(create_app(f[0])) as (client,requests):yield (f[0],f[1],f[2],client),requests

def get(f,p,actor='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2],actor))

def test_actual_repeated_read_role_boundaries_copy_and_aba(own_http):
    f,requests=own_http;p=filled(f);raw=source_for(f,p);registry=attach(f,p,raw);before=snapshot(f)
    raw['source']['text']='mutated caller';raw['policy']['target_seconds']=300
    with ThreadPoolExecutor(4) as pool:responses=list(pool.map(lambda _:get(f,p),range(12)))
    assert all(r.status_code==200 and r.json()['target_work_seconds']==30 for r in responses)
    assert get(f,p,'prep-specialist-fixture-a').json()['state']=='SYNTHETIC_CALCULATED'
    for actor in ('fixture-b','fixture-c','prep-specialist-fixture-b'):
        r=get(f,p,actor);assert r.status_code==403 and 'independent-source' not in r.text and 'PRIVATE_ORACLE_CLOCK' not in r.text
    assert snapshot(f)==before
    with f[1].connect() as c:
        old=c.execute("SELECT source FROM preparation_catalog WHERE park_id='park-a'").fetchone()['source'];c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{source_version}','901') WHERE park_id='park-a'")
    assert get(f,p).json()['issues']==['DEADLINE_BINDING_CHANGED']
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a'",(Jsonb(old),))
    after=snapshot(f);assert get(f,p).json()['issues']==['DEADLINE_BINDING_CHANGED'] and snapshot(f)==after
    assert registry.entries and all(r['method']=='GET' for r in requests if r['path'].endswith('/handling-deadline'))

def test_actual_material_change_and_pause_claim_get_never_write(own_http):
    f,_=own_http;p=filled(f);attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED'
    assert add(f,p,text='SYNTHETIC independent new current source').status_code==200
    before=snapshot(f);assert get(f,p).json()['issues']==['DEADLINE_BINDING_CHANGED'] and snapshot(f)==before
    raw=source_for(f,p);raw['pauses']=[dict(reason='CHANGES_REQUESTED',claimed_authority=True)];attach(f,p,raw)
    assert get(f,p).json()['issues']==['PAUSE_AUTHORITY_UNAVAILABLE'] and snapshot(f)==before
    for method in ('POST','PUT','DELETE'):
        assert f[3].request(method,'/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2]),json={'action':'PAUSE'}).status_code==405
    assert snapshot(f)==before

def test_actual_revocation_after_success_hides_source_without_business_write(own_http):
    f,_=own_http;p=filled(f);attach(f,p);assert get(f,p).status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
    before=snapshot(f);r=get(f,p);assert r.status_code==403 and 'independent-source' not in r.text and snapshot(f)==before

def test_actual_new_api_pid_does_not_inherit_host_clock(own_http,tmp_path):
    f,_=own_http;p=filled(f);attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED';before=snapshot(f)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    log=tmp_path/'independent-new-pid.log'
    with log.open('w') as output:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',PYTHONDONTWRITEBYTECODE='1'),stdout=output,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url='http://127.0.0.1:'+str(port),timeout=5) as api:
                end=time.monotonic()+10
                while time.monotonic()<end:
                    try:
                        h=api.get('/health')
                        if h.status_code==200:break
                    except httpx.HTTPError:pass
                    assert proc.poll() is None;time.sleep(.02)
                else:pytest.fail('owned new API failed bounded readiness')
                assert h.json()['process_id']==proc.pid and proc.pid!=os.getpid()
                r=api.get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2]));assert r.status_code==200 and r.json()['issues']==['DEADLINE_SOURCE_DISABLED'] and r.json()['deadline_utc'] is None
                assert api.get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2],'fixture-b')).status_code==403
        finally:
            proc.terminate()
            try:proc.wait(10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(5);raise
    assert snapshot(f)==before

def open_page(browser,f,p):
    ctx=browser.new_context(viewport={'width':320,'height':1000});page=ctx.new_page();page.goto(str(f[3].base_url));page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('change');page.locator('[data-tab="collaboration"]').click();page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id']);page.wait_for_function('()=>preparationView!==null');return ctx,page

@pytest.mark.parametrize('switch',['same-case-refresh','identity','other-case'])
def test_old_success_cannot_survive_refresh_or_new_context(own_http,switch):
    f,_=own_http;p=filled(f);other,_,_=create(f);attach(f,p);before=snapshot(f)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=open_page(browser,f,p)
        try:
            page.evaluate('''()=>{const original=fetch;window.oldClockReady=false;window.releaseClock=null;fetch=async(...args)=>{const r=await original(...args);if(String(args[0]).endsWith('/handling-deadline')){window.oldClockReady=true;await new Promise(resolve=>releaseClock=resolve);}return r;};}''')
            page.locator('#handling-deadline-read').click();page.wait_for_function('()=>oldClockReady')
            if switch=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('change')
            else:
                selected=other if switch=='other-case' else p
                page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',selected['preparation_id']);page.wait_for_function('()=>preparationView!==null')
            page.evaluate('()=>releaseClock()');page.wait_for_timeout(100)
            assert page.evaluate('deadlineView===null') and page.locator('#handling-deadline-result').inner_text()=='' and page.evaluate('localStorage.length===0')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and 'PRIVATE_ORACLE_CLOCK' not in page.content() and page.evaluate('globalThis.BAD_CLOCK!==true')
            OUT.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(OUT/('late-'+switch+'.png')),full_page=True)
        finally:ctx.close();browser.close()
    assert snapshot(f)==before
