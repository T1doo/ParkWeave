"""Actual NO_MODEL fixed release; observations do not verify pending work."""
from copy import deepcopy
from uuid import UUID,uuid4
import json
import pytest
from parkweave import difference_observation as observation,local_demo_selections as candidates
from test_local_resource_reapproval import ordinary_local,approved,ledger
from test_local_synthetic_demo import demo_inputs,generate
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture,headers,add,command as materials
from test_resource_bundles import bundle,states
from test_case_resource_delivery import quoted,submit,recover,effects
from test_local_resource_approval import approved as first_approval
from test_service_case_steps import adopt,verified,command as step_command
from test_service_plan_manual_lock import stored,lock

GOALS=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION']


def source_adopt(f,p,page_directory=None):
    from test_source_change_adoption import changed,preview
    response=preview(f,p,changed(f,p));assert response.status_code==200,response.text
    value=response.json()
    if not value['can_adopt']:
        graph=value['source_impact']
        assert False,dict(blockers=value['blocking_reasons'],unknown_reasons=graph['unknown_reasons'],unknown_nodes=[dict(adapter=n['adapter_id'],facet=n['facet'],fields=n['fields']) for n in graph['nodes'] if not n['known']])
    if page_directory is not None:
        response=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2]));assert response.status_code==200,response.text
        page_oracle(page_directory,value,response.json())
    response=adopt(f,p,value['adoption']);assert response.status_code==201,response.text
    return stored(f,p)['events'][-1]


def staged(f,directory):
    from test_request_intents import save
    from ordinary_case_step_support import worker_once
    run=f[3].post('/api/runs',headers=headers(f[2],key=uuid4().hex),json=dict(goal='SYNTHETIC NO_MODEL新输入完整候选来源变化'))
    assert run.status_code==202,run.text;worker_once(f,directory)
    response=f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=dict(run_id=run.json()['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id='prep-specialist-fixture-a'))
    assert response.status_code==201,response.text;p=response.json()
    response=save(f,p,goals=GOALS,text='SYNTHETIC 本次NO_MODEL独立目标');assert response.status_code==200,response.text;p=response.json()
    p=add(f,p,text='SYNTHETIC 新诉求完整原文').json();p=add(f,p,'material_outline','SYNTHETIC 新材料目录原文').json()
    p=materials(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC 原专员独立审核').json()
    p=materials(f,p,'CONFIRM',reason='SYNTHETIC 本人确认').json()
    current,_,response=generate(f,p);assert response.status_code==201,response.text;candidate=response.json()
    assert candidate['producer']['mode']=='NO_MODEL' and candidate['producer']['real_model_calls']==0
    body=dict(expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,
        expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC 明确采纳完整NO_MODEL候选',
        candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256'])
    return p,body,candidate


def first(f,directory):
    p,body,candidate=staged(f,directory);response=adopt(f,p,body);assert response.status_code==201,response.text
    plan=stored(f,p);assert [s['adapter_id'] for s in plan['steps']]==['P1','P2','P3','P4']
    assert set(plan['adoption_preview'][observation.FIELD]['sources'])=={'P1','P2','P3','P4'}
    assert all(s['coordination_state']=='PENDING' and s['verified_sources'] is None and s['verified_sha256'] is None for s in plan['steps'])
    verified(f,p,'P1');assert lock(f,p,'P1').status_code==200
    hs,members=bundle(f);data=quoted(f,p,members);item,_=first_approval(f,p,data)
    response=submit(f,p,{**data,'approval_id':item['id']});assert response.status_code==201,response.text;verified(f,p,'P2')
    return p,hs,response.json(),candidate


def tail_pending(plan):
    assert all(s['coordination_state']=='PENDING' and s['verified_sources'] is None and s['verified_sha256'] is None for s in plan['steps'] if s['adapter_id'] in ('P3','P4'))
    tail={s['id'] for s in plan['steps'] if s['adapter_id'] in ('P3','P4')}
    assert not any(e['action']=='VERIFY' and e['step_id'] in tail for e in plan['events'])


def test_new_no_model_fixed_release_source_adopt_reapproval_keeps_tail_pending(ordinary_local,tmp_path):
    f,_,requests=ordinary_local;p,old_holds,old,candidate=first(f,tmp_path/'worker');before=stored(f,p);prefix=deepcopy(ledger(f,p)['events'])
    tail_pending(before);event=source_adopt(f,p,tmp_path);tail_pending(stored(f,p))
    hs,members=bundle(f);data=quoted(f,p,{**members,'expected_link_revision':1});item,_=approved(f,p,data);key=uuid4().hex
    response=submit(f,p,{**data,'approval_id':item['id']},key);assert response.status_code==201,response.text;current=response.json()
    verified(f,p,'P2');after=stored(f,p);tail_pending(after)
    assert before['id']==after['id'] and before['steps'][0]==after['steps'][0]
    assert ledger(f,p)['events'][:3]==prefix and effects(f)==[2,6,2,2,2]
    assert states(f,hs)==states(f,old_holds)==['CONFIRMED']*3
    assert recover(f,p,key).json()['receipt']==current['receipt']
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']
    trace=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert trace.status_code==200,trace.text
    assert trace.json()['source_trace']['candidate']['producer']['mode']=='NO_MODEL'
    (tmp_path/'actual-no-model-chain.json').write_text(json.dumps(dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],
        plan_id=after['id'],candidate_id=candidate['candidate_id'],candidate_validator=candidate['validator_version'],baseline=before['adoption_preview'][observation.FIELD],
        seal=before['candidate_consumption'][observation.SEAL],source_adopt_event_id=event['id'],tail_pending=True,HTTP_calls=len(requests),
        old_receipt=old['receipt'],new_receipt=current['receipt'],real_model_calls=0,browser=False),ensure_ascii=False,indent=2)+'\n')

    # These are later real actions, not retrospective qualifications of the seal.
    from test_service_dispatches import offer,command as dispatch_command
    from test_executor_receipts import act as receipt_command
    from parkweave import case_resource_delivery as delivery
    from parkweave.store import Store
    response=offer(f,p)[0];assert response.status_code==201,response.text
    response=dispatch_command(f,response.json(),'ACCEPT');assert response.status_code==200,response.text
    dispatch=response.json();verified(f,p,'P3')
    response=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a'));assert response.status_code==200,response.text
    response=receipt_command(f,response.json(),'SUBMIT');assert response.status_code==200,response.text
    response=receipt_command(f,response.json(),'ACKNOWLEDGE');assert response.status_code==200,response.text
    verified(f,p,'P4');history=stored(f,p)
    cold=Store(f[0].dsn)
    for original in (old,current):
        restored=delivery.recover(cold,f[2]['fixture-a'],UUID(p['preparation_id']),original['delivery_binding']['request_key'])
        assert restored['receipt']==original['receipt']
    assert stored(f,p)==history
    evidence=tmp_path/'actual-no-model-chain.json';value=json.loads(evidence.read_text())
    value.update(later_actual_P3_P4_verified=True,cold_original_receipts_equal=True,HTTP_calls=len(requests))
    evidence.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


@pytest.mark.parametrize('started',['OFFER','BEGIN'])
def test_second_source_adopt_cannot_wash_observation_lineage_after_start(ordinary_local,tmp_path,started):
    from test_service_dispatches import offer
    from test_source_change_adoption import changed,preview
    f,_,_=ordinary_local;p,_,old,_=first(f,tmp_path/'worker');source_adopt(f,p)
    # Recheck the existing P2 output before using its unchanged original offer.
    verified(f,p,'P2')
    response=offer(f,p)[0] if started=='OFFER' else step_command(f,p,'P3','BEGIN',user='prep-specialist-fixture-a')
    assert response.status_code in (200,201),response.text
    before=deepcopy(ledger(f,p));result=preview(f,p,changed(f,p))
    assert result.status_code==409 and 'local source continuation refuses' in result.text,result.text
    assert ledger(f,p)==before and effects(f)==[1,3,1,1,1]
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']


@pytest.mark.parametrize('fault',['PLAN','STEP','CANDIDATE','STRIP','VERSION'])
def test_rehashed_seal_changes_or_downgrade_refuse_original_history(ordinary_local,tmp_path,fault):
    from psycopg.types.json import Jsonb
    from parkweave import controlled_plans as cp
    f,_,_=ordinary_local;p,_,old,_=first(f,tmp_path/'worker');plan=stored(f,p)
    if fault=='STRIP':plan['candidate_consumption'].pop(observation.SEAL)
    elif fault=='VERSION':plan['adoption_preview'][observation.VERSION]=True
    else:
        seal=plan['candidate_consumption'][observation.SEAL]
        if fault=='PLAN':seal['plan_id']=str(uuid4())
        elif fault=='STEP':seal['steps'][-1]['step_id']=str(uuid4())
        else:seal['candidate_id']=str(uuid4())
        seal['sha256']=cp._hash({k:v for k,v in seal.items() if k!='sha256'})
    plan['events'][0]['candidate_consumption_sha256']=cp._hash(plan['candidate_consumption'])
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    for endpoint in ('service-case-plan','goal-results'):
        result=f[3].get('/api/preparations/'+p['preparation_id']+'/'+endpoint,headers=headers(f[2]));assert result.status_code==409,result.text
    assert recover(f,p,old['delivery_binding']['request_key']).status_code==409


def test_resource_grant_aba_invalidates_unconsumed_candidate_observation(ordinary_local,tmp_path):
    f,_,_=ordinary_local;p,body,_=staged(f,tmp_path/'worker')
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    result=adopt(f,p,body);assert result.status_code==409,result.text
    with f[1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'] is None


def test_foreign_case_candidate_cannot_supply_observation_baseline(ordinary_local,tmp_path):
    f,_,_=ordinary_local;p,body,_=staged(f,tmp_path/'worker-a');other,foreign,_=staged(f,tmp_path/'worker-b')
    result=adopt(f,p,foreign);assert result.status_code==409,result.text
    assert p['case_id']!=other['case_id']
    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM preparations WHERE id=ANY(%s::uuid[]) AND service_case_plan IS NOT NULL',([p['preparation_id'],other['preparation_id']],)).fetchone()['n']==0


def test_initial_seal_failure_rolls_back_plan_and_original_key_can_commit_once(ordinary_local,tmp_path,monkeypatch):
    from parkweave import service_case_steps as steps
    f,_,_=ordinary_local;p,body,_=staged(f,tmp_path/'worker');save=steps._save;key=uuid4().hex
    def fault(c,parent,plan):save(c,parent,plan);raise RuntimeError('controlled original observation seal rollback')
    with monkeypatch.context() as patch:
        patch.setattr(steps,'_save',fault);result=adopt(f,p,body,key)
        assert result.status_code==500
    with f[1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'] is None
    result=adopt(f,p,body,key);assert result.status_code==201,result.text
    assert len(stored(f,p)['events'])==1


def test_strict_versions_and_legacy_missing_baseline_never_backfill(monkeypatch):
    from parkweave import controlled_plans as cp,typed_source_impact as typed
    from parkweave.store import Conflict
    from test_typed_source_impact import sample
    value=dict(profile=candidates.PROFILE,legacy_source_sha256='a'*64,capability_catalog_sha256='b'*64)
    expected=cp._hash(dict(legacy_source_sha256='a'*64,capability_catalog_sha256='b'*64))
    assert observation.version(value)==1 and observation.source_hash(value)==expected
    def forbidden(*args,**kwargs):raise AssertionError('old history must not acquire live observations')
    monkeypatch.setattr(observation,'capture',forbidden)
    assert observation.tail_sources({},dict(adoption_preview=value))=={}
    parent,plan,sources,manifest=sample();plan['adoption_preview']=value
    sources.pop('P3');sources.pop('P4')
    graph=typed.build(parent,plan,sources,sources,manifest,manifest)
    assert graph['schema']==1 and graph['unknown_scope']=='THIS_CASE' and 'SOURCE_BASE_UNAVAILABLE' in graph['unknown_reasons']
    with pytest.raises(Conflict):typed.build_v2(parent,plan,sources,sources,manifest,manifest)
    for version in (True,1.0,2,'1',None):
        with pytest.raises(Conflict):observation.version({**value,observation.VERSION:version,observation.FIELD:None})
    for extra in ({observation.VERSION:1},{observation.FIELD:None}):
        with pytest.raises(Conflict):observation.version({**value,**extra})


def test_legacy_history_begin_and_unknown_database_never_qualify_empty(monkeypatch):
    from parkweave import service_case_steps as steps
    from parkweave.store import Denied
    # The caller has already checked history; a historical BEGIN alone suffices.
    monkeypatch.setattr(steps,'_recovery_proofs',lambda parent:[])
    prior=dict(steps=[dict(id='old-step',adapter_id='P3')],events=[dict(step_id='old-step',action='BEGIN')])
    parent=dict(id=uuid4(),service_case_plan=dict(history=[prior],steps=[],events=[]))
    class Inaccessible:
        def execute(self,*args):raise Denied('controlled observation table privilege missing')
    with pytest.raises(observation.Started):observation.unstarted(Inaccessible(),parent)
    parent['service_case_plan']=None
    with pytest.raises(Denied,match='privilege missing'):observation.capture(None,Inaccessible(),None,parent,{})


def test_exact_empty_assignment_mapping_and_record_versions(ordinary_local,tmp_path):
    from parkweave import typed_source_impact as typed,controlled_plans as cp
    from parkweave.store import Conflict
    f,_,_=ordinary_local;p,_,_,_=first(f,tmp_path/'worker');plan=stored(f,p)
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    before=plan['adoption_preview'][observation.FIELD]['sources'];manifest=plan['events'][0]['dependencies']
    graph=typed.build_v2(parent,plan,before,before,manifest,manifest)
    assert graph['schema']==2 and graph['unknown_scope'] is None and not graph['affected']
    assert typed.build_v1(parent,plan,before,before,manifest,manifest)['unknown_scope']=='THIS_CASE'
    for field,value in (('current',0),('current',True),('marker',{}),('contract_id',str(uuid4())),('contract','UNKNOWN'),('unknown',False)):
        for side in ('before','current'):
            bad=deepcopy(before);bad['P3']['case_step_assignment'][field]=value
            args=(bad,before) if side=='before' else (before,bad)
            result=typed.build_v2(parent,plan,*args,manifest,manifest)
            assert result['unknown_scope']=='THIS_CASE' and 'SOURCE_GROUP_SHAPE_UNAVAILABLE' in result['unknown_reasons']
    record=parent['planning_previews'][0]
    for kind in ('missing_record_version','bool_record_version','v1_producer','changed_source','missing_source'):
        bad=deepcopy(record)
        if kind=='missing_record_version':bad.pop('difference_observation_record_version')
        elif kind=='bool_record_version':bad['difference_observation_record_version']=True
        elif kind=='v1_producer':bad['producer']['schema_version']='local-synthetic-demo-producer/1'
        else:
            base=bad['base_document'][observation.FIELD]
            if kind=='changed_source':base['sources']['P3']['case_step_assignment']['contract_id']=str(uuid4())
            else:base['sources'].pop('P4')
            base['sha256']=cp._hash({k:v for k,v in base.items() if k!='sha256'})
        with pytest.raises(Conflict):candidates._proof(parent,bad)


def test_observation_source_adopt_rechecks_aba_and_rolls_back_original_key(ordinary_local,tmp_path,monkeypatch):
    from test_source_change_adoption import changed,preview
    from parkweave import service_case_steps as steps
    f,_,_=ordinary_local;p,_,old,_=first(f,tmp_path/'worker');card=changed(f,p)
    view=preview(f,p,card).json();assert view['can_adopt'];original=stored(f,p);approval=deepcopy(ledger(f,p))
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert adopt(f,p,view['adoption']).status_code==409
    assert stored(f,p)==original and ledger(f,p)==approval
    view=preview(f,p,card).json();assert view['can_adopt'];key=uuid4().hex;save=steps._save
    def fail(c,parent,plan):save(c,parent,plan);raise RuntimeError('controlled source observation ADOPT after save')
    with monkeypatch.context() as patch:
        patch.setattr(steps,'_save',fail);response=adopt(f,p,view['adoption'],key)
        assert response.status_code==500
    assert stored(f,p)==original and ledger(f,p)==approval and effects(f)==[1,3,1,1,1]
    response=adopt(f,p,view['adoption'],key);assert response.status_code==201,response.text
    tail_pending(stored(f,p))
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']


def test_original_page_accepts_only_paired_local_producer_versions():
    from pathlib import Path
    import subprocess
    html=Path('src/parkweave/web.html').read_text()
    selected='\n'.join(line for line in html.splitlines() if line.startswith(('function localDemoProducerValid(','function serviceSelectionCandidateProfile(')))
    script=selected+'''
const assert=require('node:assert/strict');
const producer={schema_version:'local-synthetic-demo-producer/2',origin:'LOCAL_SYNTHETIC_DEMO_NO_MODEL_V1',mode:'NO_MODEL',model:null,provider_enabled:false,real_model_calls:0,executed:false};
for(const key of ['selection_sha256','pack_sha256','journal_sha256','base_sha256','attempt_sha256'])producer[key]='a'.repeat(64);
const view={profile:'LOCAL_SYNTHETIC_DEMO',scope:'LOCAL_SYNTHETIC_DEMO_SELECTION_CANDIDATE',validator_version:'LOCAL_SYNTHETIC_DEMO_V2',producer};
assert.equal(serviceSelectionCandidateProfile(view),true);
for(const validator_version of ['LOCAL_SYNTHETIC_DEMO_V1','LOCAL_SYNTHETIC_DEMO_V3',2])assert.equal(serviceSelectionCandidateProfile({...view,validator_version}),false);
assert.equal(serviceSelectionCandidateProfile({...view,producer:{...producer,real_model_calls:false}}),false);
assert.equal(serviceSelectionCandidateProfile({...view,producer:{...producer,schema_version:'local-synthetic-demo-producer/1'}}),false);
assert.equal(serviceSelectionCandidateProfile({...view,validator_version:'LOCAL_SYNTHETIC_DEMO_V1',producer:{...producer,schema_version:'local-synthetic-demo-producer/1'}}),true);
console.log('Original page paired V1/V2 producer checks PASS; Node only, no browser');
'''
    result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def page_oracle(directory,preview,plan):
    from pathlib import Path
    import subprocess
    data=directory/'original-page-schema2.json';data.write_text(json.dumps(dict(preview=preview,plan=plan),ensure_ascii=False)+'\n')
    result=subprocess.run(['node','tests/difference_observation_page_oracle.js',str(data)],capture_output=True,text=True,timeout=15)
    (directory/'original-page-schema2.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
