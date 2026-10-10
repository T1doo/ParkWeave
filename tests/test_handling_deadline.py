"""Synthetic working-time oracles and actual HTTP/PostgreSQL read-only checks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
import pytest
from psycopg.types.json import Jsonb
from parkweave import handling_deadline as hd
from parkweave.store import Store, Denied, digest
from parkweave.api import create_app
from test_preparation import preparation_fixture, filled, create, add, headers
from test_new_enterprise_local_chain import actual_http

TABLES=('principals','capability_grants','preparation_grants','field_grants','action_grants','run_assignments','preparation_catalog','preparations','preparation_events','preparation_evidence','runs','cases','operations','outbox')
def snapshot(f):
    with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in TABLES}

def definition(first='2026-10-09',last='2026-10-14',zone='Asia/Shanghai',target=3600,daily=None,org='org-a'):
    text='SYNTHETIC PRIVATE_DEADLINE_SOURCE <img src=x onerror=globalThis.DEADLINE_BAD=true> source example only'
    source=dict(kind='SYNTHETIC',id='synthetic-handling-source',revision=1,text=text,sha256=digest(text),valid_from='2026-01-01T00:00:00Z',valid_until='2027-01-01T00:00:00Z',service_id='synthetic-material-preparation',service_version=1,accepting_org_id=org)
    ref={k:source[k] for k in ('id','revision','sha256')};start,end=date.fromisoformat(first),date.fromisoformat(last);days=[]
    for i in range((end-start).days+1):
        d=start+timedelta(days=i)
        ranges=daily.get(d.isoformat(),[]) if daily is not None else [('09:00:00','12:00:00'),('13:00:00','17:00:00')] if d.isoformat() in ('2026-10-09','2026-10-12','2026-10-14') else []
        windows=[]
        for left,right in ranges:
            l=datetime.fromisoformat(d.isoformat()+'T'+left).replace(tzinfo=ZoneInfo(zone))
            r=(datetime.combine(d+timedelta(days=1),datetime.min.time()) if right=='24:00:00' else datetime.fromisoformat(d.isoformat()+'T'+right)).replace(tzinfo=ZoneInfo(zone))
            windows.append(dict(start=l.isoformat(),end=r.isoformat()))
        days.append(dict(date=d.isoformat(),kind='WORKING' if windows else 'CLOSED',windows=windows))
    calendar=dict(id='synthetic-working-calendar',revision=1,source_ref=ref,timezone=zone,first_date=first,last_date=last,days=days)
    policy=dict(source_ref=ref,calendar_ref=dict(id=calendar['id'],revision=1,sha256=hd.fingerprint(calendar)),timezone=zone,target_seconds=target,start_basis='SYNTHETIC_PREPARATION_CREATE')
    return dict(source=source,calendar=calendar,policy=policy,pauses=[])

def refresh_calendar_sha(raw):raw['policy']['calendar_ref']['sha256']=hd.fingerprint(raw['calendar'])
def compute(raw,start='2026-10-09T16:30:00+08:00',observed='2026-10-12T09:15:00+08:00'):
    return hd.calculate(raw,datetime.fromisoformat(start),datetime.fromisoformat(observed),service_id='synthetic-material-preparation',service_version=1,org_id='org-a')

@pytest.mark.parametrize('start,target,deadline,elapsed',[
 ('2026-10-09T16:30:00+08:00',3600,'2026-10-12T09:30:00+08:00',2700),
 ('2026-10-09T12:00:00+08:00',3600,'2026-10-09T14:00:00+08:00',15300),
 ('2026-10-09T17:00:00+08:00',3600,'2026-10-12T10:00:00+08:00',900),
 ('2026-10-11T08:00:00+08:00',1800,'2026-10-12T09:30:00+08:00',900),
 ('2026-10-12T09:00:00+08:00',10800,'2026-10-12T12:00:00+08:00',900)])
def test_manual_working_time_half_open_boundary_oracles(start,target,deadline,elapsed):
    r=compute(definition(target=target),start);assert r['state']=='SYNTHETIC_CALCULATED' and r['deadline_local']==deadline
    assert r['deadline_utc']==datetime.fromisoformat(deadline).astimezone(timezone.utc).isoformat() and r['elapsed_work_seconds']==elapsed

def test_explicit_synthetic_holiday_without_guessing_real_holidays():
    r=compute(definition(),'2026-10-12T16:30:00+08:00','2026-10-14T09:00:00+08:00')
    assert r['deadline_local']=='2026-10-14T09:30:00+08:00' and r['elapsed_work_seconds']==1800

@pytest.mark.parametrize('damage',['missing-source','missing-calendar','missing-timezone','missing-policy','missing-pauses','extra','source-hash','calendar-hash','source-ref','calendar-ref','service','version','org','expired','future-source','wrong-kind','zero-target','bool-target','float-target','oversize-target','naive-validity','invalid-time','timezone-unknown','timezone-ref','missing-day','duplicate-day','non-contiguous-day','closed-with-window','working-without-window','overlap','reverse-window','wrong-offset','wrong-date','fractional-window','too-short','pause','unsupported-pause'])
def test_invalid_missing_or_unauthorized_sources_never_get_deadline(damage):
    raw=definition()
    if damage.startswith('missing-') and damage!='missing-day':
        key=damage[8:]
        if key=='timezone':raw['calendar'].pop(key)
        else:raw.pop(key)
    elif damage=='extra':raw['policy']['invented_sla']=True
    elif damage=='source-hash':raw['source']['text']+=' changed'
    elif damage=='calendar-hash':raw['policy']['calendar_ref']['sha256']='0'*64
    elif damage=='source-ref':raw['calendar']['source_ref']=dict(raw['calendar']['source_ref'],revision=2)
    elif damage=='calendar-ref':raw['policy']['calendar_ref']['revision']=2
    elif damage in ('service','version','org'):raw['source'][{'service':'service_id','version':'service_version','org':'accepting_org_id'}[damage]]={'service':'other-service','version':2,'org':'org-b'}[damage]
    elif damage=='expired':raw['source']['valid_until']='2026-10-12T01:15:00Z'
    elif damage=='future-source':raw['source']['valid_from']='2026-10-10T00:00:00Z'
    elif damage=='wrong-kind':raw['source']['kind']='FORMAL_POLICY'
    elif damage.endswith('-target'):raw['policy']['target_seconds']={'zero-target':0,'bool-target':True,'float-target':1.5,'oversize-target':31536001}[damage]
    elif damage=='naive-validity':raw['source']['valid_until']='2027-01-01T00:00:00'
    elif damage=='invalid-time':raw['source']['valid_until']='2027-02-30T00:00:00Z'
    elif damage=='timezone-unknown':raw['calendar']['timezone']='UNKNOWN/Absent';raw['policy']['timezone']='UNKNOWN/Absent'
    elif damage=='timezone-ref':raw['policy']['timezone']='UTC'
    elif damage=='missing-day':raw['calendar']['days'].pop(1)
    elif damage=='duplicate-day':raw['calendar']['days'][1]['date']=raw['calendar']['days'][0]['date']
    elif damage=='non-contiguous-day':raw['calendar']['last_date']='2026-10-15'
    elif damage=='closed-with-window':raw['calendar']['days'][0]['kind']='CLOSED'
    elif damage=='working-without-window':raw['calendar']['days'][1]['kind']='WORKING'
    elif damage in ('overlap','reverse-window','wrong-offset','wrong-date','fractional-window'):
        w=raw['calendar']['days'][0]['windows']
        if damage=='overlap':w[1]['start']='2026-10-09T11:00:00+08:00'
        elif damage=='reverse-window':w[0]['end']=w[0]['start']
        else:w[0]['start']={'wrong-offset':'2026-10-09T09:00:00+09:00','wrong-date':'2026-10-08T09:00:00+08:00','fractional-window':'2026-10-09T09:00:00.1+08:00'}[damage]
    elif damage=='too-short':raw['policy']['target_seconds']=31536000
    elif damage in ('pause','unsupported-pause'):raw['pauses']=[dict(reason='AWAITING_USER' if damage=='pause' else 'IMPROVE_SLA',claimed_legal=True)]
    if 'calendar' in raw and 'policy' in raw and damage not in ('calendar-hash','calendar-ref'):refresh_calendar_sha(raw)
    r=compute(raw);assert r['state']=='UNKNOWN' and r['issues'] and all(r[k] is None for k in ('deadline_utc','deadline_local','elapsed_work_seconds','target_work_seconds'))
    assert 'PRIVATE_DEADLINE_SOURCE' not in json.dumps(r)

@pytest.mark.parametrize('day,left,right,issue',[
 ('2026-03-08','02:30:00','04:00:00','NONEXISTENT_LOCAL_TIME'),('2026-11-01','01:30:00','04:00:00','AMBIGUOUS_LOCAL_TIME')])
def test_dst_nonexistent_ambiguous_supplied_offset_unknown(day,left,right,issue):
    raw=definition(day,day,'America/New_York',daily={day:[(left,right)]})
    r=compute(raw,day+'T00:00:00'+('-05:00' if day.endswith('03-08') else '-04:00'),day+'T05:00:00-04:00')
    assert r['state']=='UNKNOWN' and r['issues']==[issue]

def test_dst_crossing_utc_elapsed_seconds_not_wall_clock_hours():
    raw=definition('2026-03-08','2026-03-08','America/New_York',daily={'2026-03-08':[('01:00:00','04:00:00')]})
    r=compute(raw,'2026-03-08T01:00:00-05:00','2026-03-08T04:00:00-04:00')
    assert r['deadline_local']=='2026-03-08T03:00:00-04:00' and r['elapsed_work_seconds']==7200

@pytest.mark.parametrize('which',['start-before','observation-outside','naive-start','reversed','deadline-outlives-source'])
def test_source_time_and_calendar_coverage_not_extrapolated(which):
    raw=definition();start=datetime.fromisoformat('2026-10-09T16:30:00+08:00');now=datetime.fromisoformat('2026-10-12T09:15:00+08:00')
    if which=='start-before':start-=timedelta(days=1)
    elif which=='observation-outside':now+=timedelta(days=5)
    elif which=='naive-start':start=start.replace(tzinfo=None)
    elif which=='reversed':now=start-timedelta(seconds=1)
    else:raw['source']['valid_until']='2026-10-12T01:20:00Z'
    r=hd.calculate(raw,start,now,service_id='synthetic-material-preparation',service_version=1,org_id='org-a');assert r['state']=='UNKNOWN' and r['deadline_utc'] is None

def runtime_definition(f,p,target=3600):
    with f[1].connect() as c:start=c.execute("SELECT created_at FROM preparation_events WHERE preparation_id=%s AND action='CREATE'",(p['preparation_id'],)).fetchone()['created_at']
    first=(start.astimezone(ZoneInfo('Asia/Shanghai')).date()-timedelta(days=1)).isoformat();last=(date.fromisoformat(first)+timedelta(days=8)).isoformat()
    days={(date.fromisoformat(first)+timedelta(days=i)).isoformat():[('00:00:00','24:00:00')] for i in range(9)}
    return definition(first,last,target=target,daily=days)

def attach(f,p,raw=None):
    x=hd.IsolatedDeadlineSources(f[1],f[1]._case_fact_fixture_receipt,definitions={p['preparation_id']:raw if raw is not None else runtime_definition(f,p)},enabled_for_isolated_tests=True);x.attach_store(f[0]);return x

def get(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2],user))

@pytest.fixture
def deadline_http(preparation_fixture):
    f=preparation_fixture
    with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,),requests

def test_actual_http_pg_exact_source_utc_readonly_concurrent_cold_store(deadline_http):
    f,requests=deadline_http;p=filled(f);raw=runtime_definition(f,p);before=snapshot(f)
    assert get(f,p).json()['issues']==['DEADLINE_SOURCE_DISABLED'];registry=attach(f,p,raw);assert snapshot(f)==before
    raw['source']['text']='CALLER MUTATION';r=get(f,p);assert r.status_code==200,r.text;x=r.json()
    assert x['state']=='SYNTHETIC_CALCULATED' and not x['formal_sla'] and not x['pause_write_enabled']
    assert datetime.fromisoformat(x['deadline_utc'])==datetime.fromisoformat(x['started_at'])+timedelta(hours=1)
    assert datetime.fromisoformat(x['deadline_local'])==datetime.fromisoformat(x['deadline_utc'])
    assert 'PRIVATE_DEADLINE_SOURCE' not in r.text and 'SYNTHETIC source text' not in r.text and 'request_text' not in r.text
    with ThreadPoolExecutor(4) as pool:rows=list(pool.map(lambda _:get(f,p).json(),range(8)))
    assert all(v['deadline_utc']==x['deadline_utc'] and v['definition_sha256']==x['definition_sha256'] for v in rows) and snapshot(f)==before
    assert hd.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))['issues']==['DEADLINE_SOURCE_DISABLED']
    with pytest.raises(TypeError):registry.entries[p['preparation_id']]=('bad','bad')
    assert all(z['method']=='GET' for z in requests if z['path'].endswith('handling-deadline'))

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b','prep-specialist-fixture-c'])
@pytest.mark.parametrize('enabled',[False,True])
def test_cross_org_park_refused_even_disabled(deadline_http,user,enabled):
    f,_=deadline_http;p=filled(f)
    if enabled:attach(f,p)
    before=snapshot(f);r=get(f,p,user);assert r.status_code==403 and 'synthetic-handling-source' not in r.text and snapshot(f)==before

@pytest.mark.parametrize('damage',['read','prepare','review','inactive','role','executor','unassigned'])
def test_current_authority_scope_withdrawal_no_new_grants(deadline_http,damage):
    f,_=deadline_http;p=filled(f);attach(f,p);assert get(f,p,'prep-specialist-fixture-a').json()['state']=='SYNTHETIC_CALCULATED';actor='fixture-a'
    with f[1].connect() as c:
        if damage=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif damage=='prepare':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        elif damage=='review':actor='prep-specialist-fixture-a';c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(actor,))
        elif damage=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif damage in ('role','executor'):c.execute('UPDATE principals SET role=%s WHERE id=%s',('resource_admin' if damage=='role' else 'service_executor','fixture-a'))
        else:actor='prep-specialist-fixture-a';c.execute("UPDATE preparations SET reviewer_id='prep-specialist-fixture-b' WHERE id=%s",(p['preparation_id'],))
    before=snapshot(f);assert get(f,p,actor).status_code==403 and snapshot(f)==before

@pytest.mark.parametrize('damage',['material','request','catalog','create-time','create-payload','create-actor','delete-start'])
def test_source_change_preserves_history_requires_explicit_rebind(deadline_http,damage):
    f,_=deadline_http;p=filled(f);old=attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED'
    if damage=='material':assert add(f,p,text='SYNTHETIC explicitly new material').status_code==200
    elif damage=='request':
        from parkweave import request_intents
        request_intents.save(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,request_intents.Save(expected_preparation_revision=p['revision'],request_text='SYNTHETIC new explicit request',required_goals=[]))
    else:
        with f[1].connect() as c:
            if damage=='catalog':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{source_version}','2') WHERE park_id='park-a'")
            elif damage=='create-time':c.execute("UPDATE preparation_events SET created_at=created_at+interval '1 second' WHERE preparation_id=%s AND action='CREATE'",(p['preparation_id'],))
            elif damage=='create-payload':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{case_id}',to_jsonb(%s::text)) WHERE preparation_id=%s AND action='CREATE'",(str(uuid4()),p['preparation_id']))
            elif damage=='create-actor':c.execute("UPDATE preparation_events SET actor_id='prep-specialist-fixture-a' WHERE preparation_id=%s AND action='CREATE'",(p['preparation_id'],))
            else:c.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND action='CREATE'",(p['preparation_id'],))
    before=snapshot(f);r=get(f,p);assert r.status_code==200,r.text
    assert r.json()['state']=='UNKNOWN' and r.json()['deadline_utc'] is None and snapshot(f)==before
    if damage in ('material','request','catalog'):attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED' and snapshot(f)==before and old.entries

def test_source_missing_invalid_and_pause_declarations_unknown(deadline_http):
    f,_=deadline_http;p=filled(f);other,_,_=create(f);attach(f,p);assert get(f,other).json()['issues']==['DEADLINE_SOURCE_MISSING']
    raw=runtime_definition(f,p);raw.pop('calendar');attach(f,p,raw);assert get(f,p).json()['state']=='UNKNOWN'
    raw=runtime_definition(f,p);raw['pauses']=[dict(reason='AWAITING_USER',claimed_approved=True)];attach(f,p,raw)
    before=snapshot(f);x=get(f,p).json();assert x['issues']==['PAUSE_AUTHORITY_UNAVAILABLE'] and snapshot(f)==before

def test_catalog_change_restore_cannot_revive_old_binding(deadline_http):
    f,_=deadline_http;p=filled(f);attach(f,p)
    with f[1].connect() as c:
        original=c.execute("SELECT source FROM preparation_catalog WHERE park_id='park-a'").fetchone()['source']
        c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{source_version}','2') WHERE park_id='park-a'")
    assert get(f,p).json()['state']=='UNKNOWN'
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a'",(Jsonb(original),))
    before=snapshot(f);assert get(f,p).json()['issues']==['DEADLINE_BINDING_CHANGED'] and snapshot(f)==before
    attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED' and snapshot(f)==before

@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE'])
def test_pause_clock_writes_have_no_interface_or_business_effect(deadline_http,method):
    f,_=deadline_http;p=filled(f);attach(f,p);before=snapshot(f)
    r=f[3].request(method,'/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2],key=uuid4().hex),json=dict(action='PAUSE',reason='AWAITING_USER',claimed_legal=True))
    assert r.status_code==405 and snapshot(f)==before
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/handling-deadline?as_of=2026-10-01',headers=headers(f[2])).status_code==422

def test_actual_row_lock_wait_rechecks_source_expiry(deadline_http):
    f,_=deadline_http;p=filled(f);raw=runtime_definition(f,p)
    with f[1].connect() as c:until=c.execute("SELECT clock_timestamp()+interval '1.2 seconds' until").fetchone()['until']
    raw['policy']['target_seconds']=1;raw['source']['valid_until']=until.isoformat();attach(f,p,raw);before=snapshot(f)
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        block.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(get,f,p);limit=time.monotonic()+1
        while time.monotonic()<limit:
            block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM preparations%%') waiting").fetchone()['waiting']
            if waiting:break
            time.sleep(.01)
        assert waiting;block.execute('SELECT pg_sleep(greatest(0,extract(epoch FROM (%s::timestamptz-clock_timestamp())))+.03)',(until,));block.commit();r=pending.result(5)
    assert r.status_code==200,r.text
    assert r.json()['issues']==['SOURCE_NOT_CURRENT_OR_TIME_INVALID'] and r.json()['deadline_utc'] is None and snapshot(f)==before

@pytest.mark.parametrize('damage',['unissued','disabled','pid','wrong-store','wrong-db'])
def test_only_issued_same_process_temporary_scope_setup(preparation_fixture,damage):
    f=preparation_fixture;p=filled(f);before=snapshot(f)
    if damage=='unissued':
        from dataclasses import replace
        proof=replace(f[1]._case_fact_fixture_receipt,nonce=uuid4())
        with pytest.raises(Denied):hd.IsolatedDeadlineSources(f[1],proof,definitions={p['preparation_id']:runtime_definition(f,p)},enabled_for_isolated_tests=True)
    elif damage=='disabled':
        x=hd.IsolatedDeadlineSources();assert not x.enabled
        with pytest.raises(Denied):x.attach_store(f[0])
    else:
        x=attach(f,p)
        if damage=='pid':x.pid-=1
        elif damage=='wrong-store':x.endpoint=('127.0.0.1',1)
        else:
            from dataclasses import replace
            x.proof=replace(x.proof,database_oid=x.proof.database_oid+1)
        with pytest.raises(Denied):hd.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']))
    assert snapshot(f)==before

def test_real_new_api_process_defaults_unknown_without_original_source_configuration(deadline_http,tmp_path):
    import os, socket, subprocess, sys
    import httpx
    from parkweave.process_env import minimal_environment
    f,_=deadline_http;p=filled(f);attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED';before=snapshot(f)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=tmp_path/'cold-api.log';log.touch(mode=0o600)
    with log.open('w') as output:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',PYTHONDONTWRITEBYTECODE='1'),stdout=output,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url='http://127.0.0.1:'+str(port),timeout=5) as api:
                limit=time.monotonic()+10
                while time.monotonic()<limit:
                    try:
                        health=api.get('/health')
                        if health.status_code==200:break
                    except httpx.HTTPError:pass
                    assert proc.poll() is None;time.sleep(.02)
                else:pytest.fail('owned new API readiness deadline')
                assert health.json()['process_id']==proc.pid and proc.pid!=os.getpid()
                r=api.get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2]));assert r.status_code==200
                assert r.json()['issues']==['DEADLINE_SOURCE_DISABLED'] and r.json()['deadline_utc'] is None
                assert api.get('/api/preparations/'+p['preparation_id']+'/handling-deadline',headers=headers(f[2],'fixture-b')).status_code==403
        finally:
            proc.terminate()
            try:proc.wait(10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(5);raise
    assert snapshot(f)==before

def test_waiting_on_authority_lock_observes_actual_revocation(deadline_http):
    f,_=deadline_http;p=filled(f);attach(f,p)
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        f[1].lock_principal(block,'fixture-a',exclusive=True);pending=pool.submit(get,f,p);limit=time.monotonic()+1
        while time.monotonic()<limit:
            block.execute('SELECT pg_stat_clear_snapshot()')
            waiting=block.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%pg_advisory_xact_lock_shared%%') waiting").fetchone()['waiting']
            if waiting:break
            time.sleep(.01)
        assert waiting;block.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'");block.commit();r=pending.result(5)
    before=snapshot(f);assert r.status_code==403 and snapshot(f)==before

def test_original_changes_request_and_technical_pause_cannot_stop_clock(deadline_http):
    from test_preparation import command
    f,_=deadline_http;p=filled(f);attach(f,p);initial=get(f,p).json()
    assert f[3].post('/api/runs/'+p['run_id']+'/pause',headers=headers(f[2])).status_code==409
    r=command(f,p,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC awaiting explicit user materials');assert r.status_code==200
    assert get(f,p).json()['state']=='UNKNOWN';attach(f,p);before=snapshot(f);current=get(f,p).json()
    assert current['deadline_utc']==initial['deadline_utc'] and current['legal_pause_decision']=='NOT_EVALUATED' and snapshot(f)==before

@pytest.mark.parametrize('damage',['calendar-overflow','instant-overflow','source-surrogate'])
def test_extreme_dates_and_invalid_source_encoding_unknown(damage):
    raw=definition()
    if damage=='calendar-overflow':
        raw['calendar'].update(first_date='9999-12-31',last_date='9999-12-31',days=[dict(date='9999-12-31',kind='CLOSED',windows=[])]);refresh_calendar_sha(raw)
    elif damage=='instant-overflow':raw['source']['valid_until']='9999-12-31T23:59:59-23:00'
    else:raw['source']['text']='SYNTHETIC invalid surrogate '+chr(0xd800)
    r=compute(raw);assert r['state']=='UNKNOWN' and r['deadline_utc'] is None and r['issues']

@pytest.mark.parametrize('size',[0,17])
def test_registry_bounded_original_cases_only(preparation_fixture,size):
    f=preparation_fixture;before=snapshot(f)
    with pytest.raises(Denied):hd.IsolatedDeadlineSources(f[1],f[1]._case_fact_fixture_receipt,definitions={str(uuid4()):{} for _ in range(size)},enabled_for_isolated_tests=True)
    assert snapshot(f)==before
