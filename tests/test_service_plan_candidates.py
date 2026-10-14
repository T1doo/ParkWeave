"""Nontrusted synthetic candidate IDs consumed only after current deterministic verification."""
from uuid import uuid4
from copy import deepcopy
import pytest
from psycopg.types.json import Jsonb
from test_preparation import preparation_fixture,headers
from test_bounded_planning import setup
from test_plan_preview import digest
from parkweave import controlled_plans as cp

GOAL='LOCAL_CASE_RECORD_RECHECK'
def path(p):return '/api/preparations/'+p['preparation_id']+'/service-plan-candidates'
def generate(f,p,key=None,data=None,user='fixture-a'):
    if data is None:
        x=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current']
        data=dict(expected_preparation_revision=x['preparation_revision'],expected_source_sha256=x['source_sha256'])
    return f[3].post(path(p),headers=headers(f[2],user,key or uuid4().hex),json=data)
def preview(f,p,id,user='fixture-a'):return f[3].get(path(p)+'/'+id+'/preview',headers=headers(f[2],user))
def adoption(f,p,v):
    x=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).json()
    return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_preview']['source_sha256'],expected_plan_revision=x['revision'],required_goals=x['current_preview']['required_goals'],reason='SYNTHETIC explicit candidate preview confirmation',candidate_id=v['candidate_id'],expected_candidate_sha256=v['candidate_sha256'],expected_verification_sha256=v['verification_sha256'],**({'partial_adoption':True} if v['can_adopt_partial'] else {}))
def adopt(f,p,v,key=None,data=None):return f[3].post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key=key or uuid4().hex),json=data or adoption(f,p,v))

def test_candidate_identity_verification_and_original_adoption(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);r=generate(f,p);assert r.status_code==201,r.text
    candidate=r.json();v=preview(f,p,candidate['candidate_id']).json();assert v['state']=='VERIFIED_STRUCTURE_ONLY' and v['can_adopt'] and not v['execution_enabled'] and not v['provider_enabled']
    assert len(v['steps'])==5 and v['required_goals']==[GOAL] and v['origin']=='SYNTHETIC_UNTRUSTED_CANDIDATE'
    r=adopt(f,p,v);assert r.status_code==201,r.text;x=r.json();assert len(x['steps'])==5 and x['case_goal_completed'] is False
    assert x['candidate_consumption']['candidate_id']==candidate['candidate_id']

def test_candidate_preserves_all_unsupported_goals_and_hard_conditions(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL,'UNSUPPORTED_EXTERNAL_ACCEPTANCE']);r=generate(f,p);assert r.status_code==201,r.text
    v=preview(f,p,r.json()['candidate_id']).json();assert v['state']=='VERIFIED_STRUCTURE_ONLY' and not v['can_adopt'] and v['can_adopt_partial']
    r=adopt(f,p,v);assert r.status_code==201,r.text;assert r.json()['required_goals']==[GOAL,'UNSUPPORTED_EXTERNAL_ACCEPTANCE'] and r.json()['overall_goal_state']=='PARTIAL'

@pytest.mark.parametrize('change',['drop_goal','dependency','action','service_version','role','extra','cycle'])
def test_untrusted_candidate_cannot_self_certify_even_with_recomputed_hashes(preparation_fixture,change):
    f=preparation_fixture;p=setup(f,[GOAL,'UNSUPPORTED_REQUIRED']);v=generate(f,p).json();id=v['candidate_id']
    with f[1].connect() as c:
        row=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();records=row['planning_previews'];h=records[0];doc=h['document']
        if change=='drop_goal':doc['required_goals'].pop();doc['goal_coverage'].pop()
        elif change=='dependency':doc['steps'][-1]['depends_on']=[]
        elif change=='cycle':doc['steps'][0]['depends_on']=['P5']
        elif change=='action':doc['steps'][0]['actions'][0]['path']='/api/arbitrary/unregistered'
        elif change=='service_version':doc['steps'][0]['adapter_revision']=99
        elif change=='role':doc['steps'][0]['actions'][0]['role']='service_executor'
        else:doc['steps'][0]['approved']=True
        from parkweave.service_plan_candidates import document
        h['candidate']=document(doc);h['candidate_sha256']=cp._hash(h['candidate']);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    before=digest(f);r=preview(f,p,id);assert r.status_code==200,r.text;assert r.json()['state']=='REJECTED' and not r.json()['can_adopt'] and not r.json()['can_adopt_partial'];assert adopt(f,p,r.json()).status_code==409;assert digest(f)==before

@pytest.mark.parametrize('field',['candidate_id','expected_candidate_sha256','expected_verification_sha256'])
def test_candidate_selection_rejects_wrong_identity_or_digest(preparation_fixture,field):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v);data[field]=str(uuid4()) if field=='candidate_id' else '0'*64;before=digest(f);assert adopt(f,p,v,data=data).status_code==409;assert digest(f)==before

@pytest.mark.parametrize('change',['material','request','catalog','registry','read','execute','prepare','cancel'])
def test_current_candidate_sources_and_authority_rechecked(preparation_fixture,change,monkeypatch):
    from test_preparation import add
    from test_request_intents import save
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v)
    if change=='material':add(f,p)
    elif change=='request':save(f,p,text='SYNTHETIC changed exact request',goals=[GOAL,'UNSUPPORTED_NEW'])
    elif change=='catalog':
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"2\"}'::jsonb")
    elif change=='registry':
        from parkweave import bounded_planning as bp
        registry=deepcopy(bp.REGISTRY);registry[0]['acceptance']='SYNTHETIC registry version changed';monkeypatch.setattr(bp,'REGISTRY',registry)
    elif change=='cancel':
        from test_case_cancellation import post as cancel_post,body as cancel_body
        # Reuse original Case cancellation APIs; confirmed result is required.
        from test_preparation import command
        p=add(f,p).json();p=add(f,p,slot='material_outline').json();p=command(f,p,'REVIEW',user='prep-specialist-fixture-a',reason='SYNTHETIC original review').json();p=command(f,p,'CONFIRM',reason='SYNTHETIC original confirm').json();assert cancel_post(f,p,cancel_body(f,p)).status_code==200
    else:
        with f[1].connect() as c:c.execute('UPDATE '+('preparation_grants' if change=='prepare' else 'capability_grants')+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',change.upper()))
    before=digest(f);r=adopt(f,p,v,data=data);assert r.status_code in (403,409),r.text;assert digest(f)==before
    r=preview(f,p,v['candidate_id']);assert r.status_code==403 if change in ('read','prepare') else r.status_code==200
    if r.status_code==200 and change not in ('execute',):assert not r.json()['can_adopt']

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_candidate_not_authority_or_cross_subject_locator(preparation_fixture,user):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();before=digest(f);assert preview(f,p,v['candidate_id'],user).status_code==403;assert generate(f,p,user=user).status_code==403;assert digest(f)==before


def test_original_key_candidate_and_adoption_recovery_after_material_change(preparation_fixture):
    from test_preparation import add
    f=preparation_fixture;p=setup(f,[GOAL]);key=uuid4().hex;x=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];body=dict(expected_preparation_revision=x['preparation_revision'],expected_source_sha256=x['source_sha256']);v=generate(f,p,key,body).json();data=adoption(f,p,v);ak=uuid4().hex;r=adopt(f,p,v,ak,data);assert r.status_code==201,r.text;plan=r.json()['plan_id'];add(f,p);before=digest(f)
    recovered=f[3].get(path(p)+'/recovery',headers=headers(f[2],key=key));assert recovered.status_code==200 and recovered.json()['status']=='COMMITTED' and recovered.json()['items'][0]['state']=='STALE'
    assert generate(f,p,key,body).json()['candidate_id']==v['candidate_id'];assert adopt(f,p,v,ak,data).status_code==201
    r=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=ak));assert r.status_code==200,r.text;assert r.json()['status']=='COMMITTED' and r.json()['event']['plan_id']==plan;assert digest(f)==before
    assert generate(f,p,key).status_code==409 and adopt(f,p,v,ak,{**data,'reason':'different'}).status_code==409


def test_unknown_or_global_constraint_never_becomes_candidate_satisfaction(preparation_fixture):
    from test_request_intents import save
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json()
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb")
    v=generate(f,p).json();assert v['state']=='UNKNOWN' and not v['can_adopt'] and not v['can_adopt_partial'];assert adopt(f,p,v).status_code==409


def test_candidate_generation_and_adoption_roll_back_metadata_on_write_failure(preparation_fixture,monkeypatch):
    from parkweave import service_case_steps as steps,service_plan_candidates as candidates
    f=preparation_fixture;p=setup(f,[GOAL]);before=digest(f);original=candidates.verify
    def broken(*a,**k):raise RuntimeError('SYNTHETIC candidate result failure')
    monkeypatch.setattr(candidates,'verify',broken)
    with pytest.raises(RuntimeError):generate(f,p)
    assert digest(f)==before;monkeypatch.setattr(candidates,'verify',original);v=generate(f,p).json();before=digest(f)
    def no_save(*a,**k):raise RuntimeError('SYNTHETIC original adoption event failure')
    monkeypatch.setattr(steps,'_save',no_save)
    with pytest.raises(RuntimeError):adopt(f,p,v)
    assert digest(f)==before

@pytest.mark.parametrize('mode',['normal','partial','lost_generate','cold_generate','lost_adopt','cold_adopt','late','late_newcase','late_plan','source_change','pending_adopt','opaque_wrongname','revoke'])
def test_original_page_candidate_consumer_never_hand_fills_candidate_json(preparation_fixture,mode):
    import os,json,selectors,subprocess
    from pathlib import Path
    from test_isolated_run_access import permission_snapshot
    f=preparation_fixture;p=setup(f,[GOAL]+(['UNSUPPORTED_EXTERNAL_ACCEPTANCE'] if mode=='partial' else []));permissions=permission_snapshot(f[1]);messages=[];summary=None;stderr='';dropped=False
    proc=subprocess.Popen(['node','tests/service_plan_candidates_actual.js',p['preparation_id'],'fixture-a',mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert selector.select(timeout=15),'candidate page bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('change_context'):
                if msg['change_context']=='late_newcase':new=setup(f,[GOAL]);reply={'preparation_id':new['preparation_id']}
                else:
                    from test_request_intents import save
                    r=save(f,p,goals=[GOAL,'UNSUPPORTED_ADDED_GOAL']);assert r.status_code==200;reply={'preparation_id':p['preparation_id']}
                permissions=permission_snapshot(f[1]);proc.stdin.write((json.dumps(reply)+'\n').encode());proc.stdin.flush();continue
            if msg.get('change_source'):
                from test_preparation import add
                assert add(f,p).status_code==200;proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if msg.get('revoke_read'):
                with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                permissions=permission_snapshot(f[1]);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'result' in msg:summary=msg;break
            q=msg['request'];options=q['options'];method=options.get('method','GET');body=__import__('json').loads(options['body']) if options.get('body') else None;before=digest(f)
            r=f[3].request(method,q['path'],headers=headers(f[2],key=options['headers'].get('Idempotency-Key')),json=body);assert r.status_code in (200,201,403),r.text
            if method=='GET':assert digest(f)==before
            assert permission_snapshot(f[1])==permissions
            lost=not dropped and method=='POST' and ((mode in ('lost_generate','cold_generate','opaque_wrongname') and q['path'].endswith('/service-plan-candidates')) or (mode in ('lost_adopt','cold_adopt') and q['path'].endswith('/service-case-plan')))
            dropped=dropped or lost;messages.append(dict(method=method,path=q['path'],status=r.status_code,lost=lost,body=body));proc.stdin.write((json.dumps(dict(status=r.status_code,body=r.json(),lost=lost))+'\n').encode());proc.stdin.flush()
        code=proc.wait(timeout=15);stderr=proc.stderr.read().decode();assert code==0,stderr;assert summary and summary['result']=='PASS'
        assert sum(m['method']=='POST' and m['path'].endswith('/service-plan-candidates') for m in messages)==(2 if mode in ('late_newcase','late_plan') else 1)
        if mode in ('lost_generate','cold_generate','lost_adopt','cold_adopt'):assert dropped
    finally:
        out=Path(os.environ.get('PLAN_CANDIDATE_EVIDENCE','.runtime/service-plan-candidates-20261014/page-dev'));out.mkdir(parents=True,exist_ok=True);out.joinpath('page-'+mode+'-chain.json').write_text(json.dumps(dict(summary=summary,requests=messages,stderr=stderr),indent=2)+'\n');selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

@pytest.mark.parametrize('constraints',[{'excluded_roles':['service_executor']},{'additional_requirements':['SYNTHETIC global institutional permission']},{'excluded_roles':['enterprise_operator']}])
def test_candidate_cannot_override_saved_global_hard_constraints(preparation_fixture,constraints):
    from test_planning_constraints import update
    f=preparation_fixture;p=setup(f,[GOAL]);r=update(f,p,[GOAL],constraints);assert r.status_code==200;p['revision']=r.json()['revision'];v=generate(f,p).json();assert v['state']=='BLOCKED' and not v['can_adopt'] and not v['can_adopt_partial'];before=digest(f);assert adopt(f,p,v).status_code==409;assert digest(f)==before


def test_original_constraint_cannot_be_cleared_to_make_candidate_satisfied(preparation_fixture):
    from test_planning_constraints import update
    f=preparation_fixture;p=setup(f,[GOAL]);r=update(f,p,[GOAL],{'additional_requirements':['SYNTHETIC global immutable condition']});assert r.status_code==200;p['revision']=r.json()['revision'];r=update(f,p,[GOAL,'SYNTHETIC global immutable condition'],{'excluded_roles':[],'additional_requirements':[]});assert r.status_code==200;p['revision']=r.json()['revision'];v=generate(f,p).json();assert v['state']=='BLOCKED' and not v['can_adopt_partial'];assert adopt(f,p,v).status_code==409


def test_candidate_mixed_history_capacity_and_original_capture_compatibility(preparation_fixture):
    from test_bounded_planning import capture,read
    f=preparation_fixture;p=setup(f,[GOAL]);assert capture(f,p).status_code==200
    for _ in range(15):assert generate(f,p).status_code==201
    before=digest(f);assert generate(f,p).status_code==409 and digest(f)==before
    x=read(f,p).json();assert len(x['history'])==1 and x['candidate_metadata_count']==15 and x['history'][0]['state']=='CURRENT'


def test_candidate_key_cannot_cross_case_or_subject_and_not_observed_is_not_failure(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);other=setup(f,[GOAL]);key=uuid4().hex;v=generate(f,p,key).json();before=digest(f);assert generate(f,other,key).status_code==409;assert preview(f,other,v['candidate_id']).status_code==409
    r=f[3].get(path(p)+'/recovery',headers=headers(f[2],key=uuid4().hex));assert r.status_code==200 and r.json()['status']=='NOT_OBSERVED' and r.json()['items']==[] and r.json()['automatically_replayed'] is False;assert digest(f)==before


def test_candidate_concurrent_same_key_returns_one_original_record_and_different_input_conflicts(preparation_fixture):
    from concurrent.futures import ThreadPoolExecutor
    f=preparation_fixture;p=setup(f,[GOAL]);key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:generate(f,p,key),range(2)))
    assert all(r.status_code==201 for r in results);assert results[0].json()['candidate_id']==results[1].json()['candidate_id']
    data=adoption(f,p,results[0].json());ak=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:adopt(f,p,{},ak,data),range(2)))
    assert all(r.status_code==201 for r in results);assert results[0].json()['plan_id']==results[1].json()['plan_id'];assert len(results[0].json()['events'])==1
    assert adopt(f,p,{},ak,{**data,'reason':'SYNTHETIC different explicit input'}).status_code==409

@pytest.mark.parametrize('stage',['generation','adoption'])
def test_owned_pg_parent_wait_fixture_revision_change_wins_current_source_cas(preparation_fixture,stage):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from test_preparation import add
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v)
    current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];genbody=dict(expected_preparation_revision=current['preparation_revision'],expected_source_sha256=current['source_sha256'])
    with f[1].connect() as c,ThreadPoolExecutor(max_workers=1) as pool:
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        future=pool.submit(lambda:generate(f,p,data=genbody) if stage=='generation' else adopt(f,p,v,data=data))
        end=time.monotonic()+10
        while time.monotonic()<end:
            with f[1].connect() as observer:
                waits=observer.execute("SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%%preparations%%FOR UPDATE%%'").fetchall()
            if waits:break
            time.sleep(.01)
        assert waits,'actual PostgreSQL lock wait was not observed'
        # Use the original ADD_EVIDENCE implementation on the same owned connection
        # is impossible across its independent transaction; commit the same material
        # update via existing API after releasing this lock, serialized ahead of old
        # request by holding its key guard is not deterministic. Instead mutate this
        # fixture revision under the real held parent lock to invalidate the original
        # recorded CAS, without claiming actual user material workflow.
        c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],));c.commit()
        r=future.result(timeout=15);assert r.status_code==409,r.text
    with f[1].connect() as c:
        row=c.execute('SELECT planning_previews,service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();assert len(row['planning_previews'])==1 and row['service_case_plan'] is None

@pytest.mark.parametrize('field',['schema_version','provider_enabled','preparation_revision'])
def test_nontrusted_json_boolean_integer_types_are_not_interchangeable(preparation_fixture,field):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json()
    with f[1].connect() as c:
        records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];h=records[0]
        if field=='schema_version':h['candidate'][field]=True
        elif field=='provider_enabled':h['candidate'][field]=0
        else:h['candidate']['binding'][field]=float(h['candidate']['binding'][field])
        h['candidate_sha256']=cp._hash(h['candidate']);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    before=digest(f);assert preview(f,p,v['candidate_id']).status_code==409;assert digest(f)==before

def test_original_candidate_cache_and_get_agree_after_plan_replacement(preparation_fixture):
    from test_request_intents import save
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v);key=uuid4().hex;old=adopt(f,p,v,key,data);assert old.status_code==201,old.text
    oldid=old.json()['plan_id'];changed=save(f,p,goals=[GOAL,'UNSUPPORTED_NEW_PLAN']);assert changed.status_code==200;p['revision']=changed.json()['revision']
    x=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).json();r=f[3].post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_preview']['source_sha256'],expected_plan_revision=x['revision'],required_goals=x['current_preview']['required_goals'],reason='SYNTHETIC explicit original plan replacement',partial_adoption=True));assert r.status_code==201,r.text;assert r.json()['plan_id']!=oldid
    before=digest(f);assert adopt(f,p,v,key,data).status_code==201
    r=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key));assert r.status_code==200,r.text;assert r.json()['event']['plan_id']==oldid and r.json()['event']['current_plan'] is False;assert digest(f)==before
    with f[1].connect() as c:c.execute("UPDATE preparations SET planning_previews='[]'::jsonb WHERE id=%s",(p['preparation_id'],))
    before=digest(f);get=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key));assert get.status_code==409;cached=adopt(f,p,v,key,data);assert cached.status_code==409,cached.text;assert digest(f)==before

@pytest.mark.parametrize('change',['consumption','request_reason','event_fingerprint','step_contract','missing_consumption','both_removed'])
def test_candidate_current_plan_keeps_event_request_and_consumed_graph_proof(preparation_fixture,change):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v);key=uuid4().hex;assert adopt(f,p,v,key,data).status_code==201
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        if change=='consumption':plan['candidate_consumption']['verification_sha256']='0'*64
        elif change=='request_reason':plan['adoption_request']['reason']='SYNTHETIC replaced private reason'
        elif change=='event_fingerprint':plan['events'][0]['fingerprint']='0'*64
        elif change=='step_contract':plan['steps'][0]['contract']['actions'][0]['role']='service_executor'
        else:
            plan.pop('candidate_consumption')
            if change=='both_removed':plan.pop('adoption_request')
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);assert f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).status_code==409
    assert adopt(f,p,v,key,data).status_code==409
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key)).status_code==409;assert digest(f)==before
