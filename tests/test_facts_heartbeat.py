from datetime import datetime,timedelta,timezone
import json
import subprocess
import sys
import time
import uuid
import pytest
import psycopg
from test_worker_gateway import runtime,auth,worker,read,oracle
from parkweave.store import Conflict,Store


def fact(value,source='fixture-doc-1',field='region',expired=False):
    now=datetime.now(timezone.utc)
    return {'schema_version':'parkweave-domain/1.0-draft','field':field,'value':value,
            'unit':'people' if field=='employees' else 'text',
            'source_ref':{'id':source,'kind':'SYNTHETIC','revision':'1'},'source_excerpt':str(value),
            'validity':{'valid_from':(now-timedelta(days=2)).isoformat(),
                        'valid_until':(now+timedelta(days=-1 if expired else 2)).isoformat(),'timezone':'UTC'}}


def submit_facts(runtime,fields=['region','employees']):
    api,owner,tokens,env=runtime
    r=api.post('/api/runs',headers=auth(tokens),json={'action':'facts.assess','goal':'合成：核对事实证据','fact_fields':fields})
    assert r.status_code==202,r.text
    return r.json()['run_id']


def wait_running(runtime,run):
    for _ in range(100):
        row=oracle(runtime[1],run)
        if row['state']=='RUNNING':return row
        time.sleep(.03)
    raise AssertionError('worker did not claim')


def long_worker(runtime,seconds=3.3):
    return subprocess.Popen([sys.executable,'-m','parkweave.worker','--once','--lease-seconds','1',
                             '--mock-model-wait-seconds',str(seconds)],env=runtime[3],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def revoke_field(runtime,field,capability='READ'):
    result=subprocess.run([sys.executable,'-m','parkweave.cli','revoke-field','--principal','fixture-a',
                           '--field',field,'--capability',capability],
                          env=dict(runtime[3],PARKWEAVE_DSN=runtime[1].dsn),capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_api_facts_conflict_missing_and_independent_source_preservation(runtime):
    api,owner,tokens,env=runtime
    ids=[]
    for value,source in [('甲地区','source-a'),('乙地区','source-b')]:
        r=api.post('/api/facts',headers=auth(tokens),json=fact(value,source));assert r.status_code==201,r.text
        ids.append(r.json()['fact_id'])
    run=submit_facts(runtime);worker(runtime)
    receipt=read(runtime,run)['operation']['receipt'];results={r['field']:r for r in receipt['results']}
    assert results['region']['state']=='UNKNOWN' and results['region']['reason']=='CONFLICTING_EVIDENCE'
    assert {e['fact_id'] for e in results['region']['evidence']}==set(ids)
    assert {e['source_ref']['id'] for e in results['region']['evidence']}=={'source-a','source-b'}
    assert results['employees']['state']=='UNKNOWN' and results['employees']['reason']=='MISSING_EVIDENCE'
    assert receipt['qualification_decision']=='NOT_EVALUATED'
    assert read(runtime,run)['case'] is None and read(runtime,run)['success_scope']=='FACT_EVIDENCE_ASSESSED'


def test_expired_fact_never_becomes_known_and_idempotency(runtime):
    api,owner,tokens,env=runtime;headers=auth(tokens,key='same-fact');body=fact('旧地区',expired=True)
    r=api.post('/api/facts',headers=headers,json=body);assert r.status_code==201
    assert api.post('/api/facts',headers=headers,json=body).json()==r.json()
    assert api.post('/api/facts',headers=headers,json=body|{'value':'新地区'}).status_code==409
    run=submit_facts(runtime,['region']);worker(runtime)
    result=read(runtime,run)['operation']['receipt']['results'][0]
    assert result['state']=='UNKNOWN' and result['reason']=='EXPIRED_OR_NOT_YET_VALID'
    assert result['evidence'][0]['applicable_at_assessment'] is False
    assert result['evidence'][0]['valid_until'] < read(runtime,run)['operation']['receipt']['assessed_at']


@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_actual_http_fact_and_assessment_cross_scope_denial(runtime,user):
    api,owner,tokens,env=runtime
    r=api.post('/api/facts',headers=auth(tokens),json=fact('授权地区'));fact_id=r.json()['fact_id']
    assert api.get('/api/facts/'+fact_id,headers=auth(tokens,user)).status_code==403
    # Tenant-scoped list is independently empty, without exposing another organization's facts.
    assert api.get('/api/facts',params={'fields':'region'},headers=auth(tokens,user)).json()=={'facts':[]}
    run=submit_facts(runtime,['region']);worker(runtime)
    assert api.get('/api/runs/'+run,headers=auth(tokens,user)).status_code==403
    assert api.post('/api/facts',headers=auth(tokens,user),json=fact('x')|{'org_id':'org-a'}).status_code==422


def test_grant_revoke_blocks_cached_receipt_new_read_and_write_and_seed_does_not_restore(runtime):
    api,owner,tokens,env=runtime
    r=api.post('/api/facts',headers=auth(tokens),json=fact('授权地区'));fact_id=r.json()['fact_id']
    run=submit_facts(runtime,['region']);worker(runtime)
    assert read(runtime,run)['operation']['receipt']['results'][0]['state']=='KNOWN'
    revoke_field(runtime,'region')
    assert api.get('/api/runs/'+run,headers=auth(tokens)).status_code==403
    assert api.get('/api/facts/'+fact_id,headers=auth(tokens)).status_code==403
    assert api.get('/api/facts',params={'fields':'region'},headers=auth(tokens)).status_code==403
    assert api.post('/api/runs',headers=auth(tokens),json={'goal':'x','action':'facts.assess','fact_fields':['region']}).status_code==403
    # READ withdrawal does not invent a WRITE withdrawal; then withdraw WRITE independently.
    assert api.post('/api/facts',headers=auth(tokens),json=fact('补充资料')).status_code==201
    revoke_field(runtime,'region','WRITE')
    assert api.post('/api/facts',headers=auth(tokens),json=fact('x')).status_code==403
    owner.seed(tokens)
    assert api.get('/api/facts/'+fact_id,headers=auth(tokens)).status_code==403
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with Store(env['PARKWEAVE_DSN']).connect() as c:c.execute('UPDATE field_grants SET active=true')


def test_heartbeat_renews_independently_during_mock_wait_and_competing_worker_cannot_steal(runtime):
    api,owner,tokens,env=runtime;run=submit_facts(runtime,['region'])
    proc=long_worker(runtime)
    try:
        before=wait_running(runtime,run)['fence'];time.sleep(1.5)
        with owner.connect() as c:
            row=c.execute('SELECT heartbeat_count,lease_until>clock_timestamp() valid FROM runs WHERE id=%s',(run,)).fetchone()
        assert row['heartbeat_count']>=2 and row['valid']
        worker(runtime)  # a second real worker cannot reclaim the renewed lease
        assert oracle(owner,run)['fence']==before
        assert proc.wait(timeout=10)==0
        assert read(runtime,run)['state']=='SUCCEEDED'
        with owner.connect() as c:assert c.execute('SELECT count(*) n FROM operations WHERE run_id=%s',(run,)).fetchone()['n']==1
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=10)


@pytest.mark.parametrize('reason',['field-revoke','cancel'])
def test_wait_revocation_or_cancel_aborts_without_assessment_or_deadlock(runtime,reason):
    api,owner,tokens,env=runtime;run=submit_facts(runtime,['region']);proc=long_worker(runtime,5)
    try:
        wait_running(runtime,run);started=time.monotonic()
        if reason=='field-revoke':revoke_field(runtime,'region')
        else:assert api.post('/api/runs/'+run+'/cancel',headers=auth(tokens)).status_code==200
        assert time.monotonic()-started<2  # model wait holds no long DB lock
        assert proc.wait(timeout=5)==0
        row=oracle(owner,run)
        assert row['state']==('FAILED' if reason=='field-revoke' else 'CANCELLED')
        assert not row['receipt'] or row['receipt'].get('source')!='LOCAL_FACT_ASSESSMENT'
        with owner.connect() as c:assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=10)


def test_killed_waiting_worker_lease_expires_and_old_heartbeat_cannot_resurrect(runtime):
    api,owner,tokens,env=runtime;run=submit_facts(runtime,['region']);proc=long_worker(runtime,5)
    row=wait_running(runtime,run);old={'id':uuid.UUID(run),'fence':row['fence']}
    proc.kill();proc.wait(timeout=10);time.sleep(1.15)
    with pytest.raises(Conflict):Store(env['PARKWEAVE_DSN']).heartbeat(old,1)
    worker(runtime)
    assert oracle(owner,run)['fence']>old['fence'] and read(runtime,run)['state']=='SUCCEEDED'
    with pytest.raises(Conflict):Store(env['PARKWEAVE_DSN']).heartbeat(old,1)


def test_worker_checks_current_field_grant_after_acceptance(runtime):
    api,owner,tokens,env=runtime;run=submit_facts(runtime,['region']);revoke_field(runtime,'region');worker(runtime)
    assert oracle(owner,run)['state']=='FAILED'
    assert oracle(owner,run)['receipt']['reason']=='AUTHORIZATION_REVOKED'


@pytest.mark.parametrize('change',[{'value':True,'field':'employees','unit':'people'},
                                   {'source_ref':{'id':'fake-real','kind':'AUTHORIZED_REAL','revision':'1'}},
                                   {'field':'secret_token'},{'value':-1,'field':'employees','unit':'people'}])
def test_fact_contract_rejects_false_sources_bad_types_unknown_fields(runtime,change):
    api,owner,tokens,env=runtime
    assert api.post('/api/facts',headers=auth(tokens),json=fact('x')|change).status_code==422
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM fact_assertions').fetchone()['n']==0
