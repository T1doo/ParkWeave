"""Finite release comparison over original V4 adoption, HTTP and owned PG."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from threading import Event
from uuid import UUID,uuid4
import json

import pytest
from fastapi.testclient import TestClient

from parkweave.api import create_app
from parkweave import service_release_preflight as preflight, service_case_steps as steps, service_selection_candidates as selection, bounded_planning as bp
from parkweave import typed_source_impact as typed
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_capability_contract import hash_instance
from parkweave.store import Conflict,Denied
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog,register,material_instance
from test_independent_selection_integration import adoption
from test_service_selection_candidates import planner
from test_service_case_steps import verified,setup
from test_service_plan_manual_lock import lock
from test_template_upgrade import publication
from service_release_acceptance_support import case_history,authority_snapshot,stable_hash,wait_for_pg_blocker


@pytest.fixture
def checked(capability_catalog,receipt_fixture,tmp_path):
    a=capability_catalog;f=a['f']
    journal=ConsumerRepository(tmp_path/'preflight.consumer.candidate.sqlite3')
    checker=preflight.ServiceReleasePreflight(a['catalog'],journal,enabled_for_isolated_tests=True)
    with TestClient(create_app(f[0],capability_catalog=a['catalog'],service_release_preflight=checker)) as api:
        a['f']=(*f[:3],api)
        f=a['f'];release=register(a)['release'];a['catalog'].bind_instance('park-a',uuid4().hex,material_instance(release))
        p=setup(f,'LOCAL_MATERIAL_PREPARATION')
        with a['catalog'].connection() as c:
            actor,parent=bp._context(f[0],c,f[2]['fixture-a'],UUID(p['preparation_id']))
            current=selection.current(f[0],c,actor,parent,a['catalog'])
        capture=selection.Capture(expected_preparation_revision=current['preparation_revision'],expected_source_sha256=current['source_sha256'],expected_capability_catalog_sha256=current['capability_catalog_sha256'])
        candidate=selection.generate(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,capture,catalog=a['catalog'],planner=planner([]))
        adopted=steps.adopt(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,adoption(candidate))
        verified(f,p,'P1')
        original=candidate['selection']['selections'][0]
        yield dict(a=a,f=f,p=p,checker=checker,journal=journal,original=original,adopted=adopted)


def path(x):return '/api/preparations/'+x['p']['preparation_id']+'/service-release-preflight'


def preview(x,instance=None):
    return x['f'][3].get(path(x)+'/preview',headers=headers(x['f'][2]),params=dict(
        original_release_id=x['original']['release_id'],original_instance_id=x['original']['instance_id'],
        target_instance_id=instance or x['original']['instance_id']))


def record_body(value):
    return dict(original_ref=value['original_ref'],target_ref=value['target_ref'],expected_plan_revision=value['plan_revision'],
        expected_preflight_sha256=value['preflight_sha256'],reason='SYNTHETIC explicit private preflight evidence only')


def save(x,value,key=None,body=None):
    return x['f'][3].post(path(x),headers=headers(x['f'][2],key=key or uuid4().hex),json=body or record_body(value))


def target(x,source='1',name='SYNTHETIC title metadata change'):
    a=x['a'];new=publication(a,goals=a['published']['snapshot']['definition']['required_goals'],source=source,name=name)
    a['published']=new;release=register(a)['release']
    instance=material_instance(release);instance['config_revision']=2;instance['config_sha256']=hash_instance(instance)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance)
    return release,instance


def state(x):
    return dict(case=case_history(x['f'][1],x['p']['preparation_id']),authority=authority_snapshot(x['f'][1]),
        template=x['a']['engine'].repository.path.read_bytes(),consumer=x['a']['consumer'].repository.path.read_bytes())


def test_actual_v4_same_release_directory_preview_and_no_business_writes(checked):
    x=checked;before=state(x);journal=x['journal'].path.read_bytes()
    directory=x['f'][3].get(path(x),headers=headers(x['f'][2]));assert directory.status_code==200,directory.text
    assert directory.json()['originals'][0]['ref']==x['original'] and directory.json()['targets'][0]['ref']==x['original']
    r=preview(x);assert r.status_code==200,r.text;v=r.json()
    assert v['scope']==preflight.SCOPE and v['schema']==1 and v['change_kind']=='NO_RELEASE_CHANGE'
    assert v['classification']==v['contract_classification']=='COMPATIBLE' and not v['affected']
    assert v['preserved']==[s['id'] for s in x['adopted']['steps']] and v['can_record']
    assert state(x)==before and x['journal'].path.read_bytes()==journal


def test_title_only_new_head_is_contract_compatible_but_current_case_needs_recheck(checked):
    x=checked;target(x);before=state(x);r=preview(x);assert r.status_code==200,r.text;v=r.json()
    assert v['contract_classification']=='COMPATIBLE' and v['contract_affected']==[]
    assert v['classification']=='NEEDS_RECHECK' and v['change_kind']=='RELEASE_VERSION_CHANGE' and v['unknown_scope']=='THIS_CASE'
    expected=[s['id'] for s in x['adopted']['steps']]
    assert v['current_case_affected']==v['affected']==expected and v['preserved']==[]
    assert not v['original_source_current_available'] and v['target_current_available'] and v['can_record']
    assert state(x)==before


def test_real_source_rule_change_uses_selected_steps_and_original_lock_not_overwritten(checked):
    x=checked;assert lock(x['f'],x['p'],'P1').status_code==200
    target(x,source='2');before=state(x);v=preview(x).json()
    expected=[s['id'] for s in x['adopted']['steps']]
    assert v['contract_classification']=='NEEDS_RECHECK' and v['contract_affected']==expected
    assert v['classification']=='LOCK_CONFLICT' and v['locked_affected']==expected and v['can_record']
    r=save(x,v);assert r.status_code==201,r.text
    assert r.json()['recorded_preflight']==v and state(x)==before


def test_private_immutable_evidence_idempotency_cold_restart_and_key_parameter_conflict(checked):
    x=checked;target(x);v=preview(x).json();key=uuid4().hex;before=state(x)
    first=save(x,v,key);assert first.status_code==201,first.text;first=first.json()
    assert first['status']=='COMMITTED' and first['recorded_preflight']==v and first['current_available']
    assert save(x,v,key).json()==first and state(x)==before
    with x['journal'].connect() as c:
        assert c.execute('SELECT count(*) FROM consumer_instances').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM consumer_requests').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM consumer_stages').fetchone()[0]==0
    changed=record_body(v);changed['reason']='SYNTHETIC changed evidence request'
    assert save(x,v,key,changed).status_code==409
    restarted=preflight.ServiceReleasePreflight(x['a']['catalog'],ConsumerRepository(x['journal'].path),enabled_for_isolated_tests=True)
    assert restarted.recover(x['f'][2]['fixture-a'],UUID(x['p']['preparation_id']),key)==first
    assert state(x)==before


@pytest.mark.parametrize('mutation',['preparation_aba','catalog_aba','plan_revision'])
def test_observed_case_and_source_aba_or_plan_change_reject_record_without_log_write(checked,mutation):
    x=checked;v=preview(x).json()
    if mutation=='plan_revision':assert lock(x['f'],x['p'],'P1').status_code==200
    elif mutation=='preparation_aba':
        with x['f'][1].connect() as c:goal=c.execute('SELECT goal FROM preparations WHERE id=%s',(x['p']['preparation_id'],)).fetchone()['goal']
        with x['f'][1].connect() as c:c.execute("UPDATE preparations SET goal=goal||' SYNTHETIC changed' WHERE id=%s",(x['p']['preparation_id'],))
        with x['f'][1].connect() as c:c.execute('UPDATE preparations SET goal=%s WHERE id=%s',(goal,x['p']['preparation_id']))
    else:
        for _ in range(2):
            with x['f'][1].connect() as c:c.execute("UPDATE preparation_catalog SET namespace=namespace WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    journal=x['journal'].path.read_bytes();before=state(x);r=save(x,v)
    assert r.status_code==409,r.text;assert x['journal'].path.read_bytes()==journal and state(x)==before


def test_saved_history_survives_current_target_withdrawal_without_becoming_authority(checked):
    x=checked;v=preview(x).json();key=uuid4().hex;first=save(x,v,key).json()
    with x['f'][1].connect() as c:revision=c.execute("SELECT service_capability_catalog->>'revision' r FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone()['r']
    x['a']['catalog'].withdraw_instance('park-a',uuid4().hex,x['original']['instance_id'],int(revision),'SYNTHETIC explicit target withdrawal')
    before=state(x);journal=x['journal'].path.read_bytes()
    cold=x['f'][3].get(path(x)+'/recovery/'+key,headers=headers(x['f'][2]));assert cold.status_code==200,cold.text
    assert cold.json()['recorded_preflight']==first['recorded_preflight'] and not cold.json()['current_available']
    v2=preview(x).json();assert v2['classification']=='UNKNOWN' and not v2['can_record'] and not v2['original_source_current_available']
    assert state(x)==before and x['journal'].path.read_bytes()==journal


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_other_owner_park_or_role_cannot_read_preflight_or_cold_evidence(checked,user):
    x=checked;v=preview(x).json();key=uuid4().hex;assert save(x,v,key).status_code==201
    for suffix in ('','/recovery/'+key):
        r=x['f'][3].get(path(x)+suffix,headers=headers(x['f'][2],user));assert r.status_code==403 and 'recorded_preflight' not in r.text


def test_read_revocation_denies_cold_get_and_prepare_revocation_retains_history_only(checked):
    x=checked;v=preview(x).json();key=uuid4().hex;assert save(x,v,key).status_code==201
    with x['f'][1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
    cold=x['f'][3].get(path(x)+'/recovery/'+key,headers=headers(x['f'][2]));assert cold.status_code==200 and not cold.json()['current_available']
    assert save(x,v,key).status_code==403
    with x['f'][1].connect() as c:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
    assert x['f'][3].get(path(x)+'/recovery/'+key,headers=headers(x['f'][2])).status_code==403


def test_new_graph_schema_is_unknown_not_recordable(checked,monkeypatch):
    x=checked;real=typed.build
    def unsupported(*args,**kwargs):return dict(real(*args,**kwargs),schema=2)
    monkeypatch.setattr(typed,'build',unsupported)
    v=preview(x).json();assert v['classification']=='UNKNOWN' and not v['can_record']
    assert 'SUPPORTED_SOURCE_GRAPH_SCHEMA_REQUIRED' in v['blocking_reasons']


@pytest.mark.parametrize('flag',[False,1,'true',{}])
def test_fixture_gate_is_exact_and_default_capability_remains_closed(capability_catalog,tmp_path,flag):
    a=capability_catalog;repo=ConsumerRepository(tmp_path/'refused.consumer.candidate.sqlite3')
    with pytest.raises(Denied):preflight.ServiceReleasePreflight(a['catalog'],repo,enabled_for_isolated_tests=flag)


@pytest.mark.parametrize('value',[True,1.0])
def test_record_rejects_bool_float_revision_instead_of_canonical_type_alias(checked,value):
    x=checked;v=preview(x).json();body=record_body(v);body['original_ref']['revision']=value
    assert save(x,v,body=body).status_code==422


def test_existing_consumer_and_foreign_nonempty_standard_journal_are_not_reused(capability_catalog,tmp_path):
    a=capability_catalog
    with pytest.raises(Denied):preflight.ServiceReleasePreflight(a['catalog'],a['consumer'].repository,enabled_for_isolated_tests=True)
    foreign=ConsumerRepository(tmp_path/'other-purpose.consumer.candidate.sqlite3')
    # A schema-valid foreign-purpose journal is sufficient to prove that the
    # feature does not reinterpret another consumer's records or stages.
    with foreign.connect(write=True) as c:
        c.execute('INSERT INTO consumer_instances VALUES(?,?,?,?,?,?,?,?)',('synthetic-foreign','fixture-a','park-a','org-a','fixture',json.dumps({'kind':'PARK_INSTANCE_COLD_INPUT_V1'}),'{}','COMMANDS_REQUIRE_EXPLICIT_SUBMISSION'))
    before=foreign.path.read_bytes()
    with pytest.raises(Denied):preflight.ServiceReleasePreflight(a['catalog'],foreign,enabled_for_isolated_tests=True)
    assert foreign.path.read_bytes()==before


def test_real_mapping_wait_expiry_cannot_claim_current_target_available(checked,monkeypatch):
    x=checked;target(x);entered=Event();original=x['a']['catalog'].mapping_states
    def observed(*args,**kwargs):
        entered.set();return original(*args,**kwargs)
    monkeypatch.setattr(x['a']['catalog'],'mapping_states',observed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with x['f'][1].connect() as c:
            x['f'][1].lock_principal(c,'prep-specialist-fixture-a',exclusive=True)
            pid=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            future=pool.submit(preview,x)
            assert entered.wait(3)
            assert wait_for_pg_blocker(x['f'][1],pid)
            x['a']['now'][0]=datetime(2100,1,1,tzinfo=timezone.utc)
        r=future.result(timeout=5)
    assert r.status_code==200,r.text;v=r.json()
    assert v['classification']=='UNKNOWN' and not v['can_record'] and not v['target_current_available']


def test_expiry_after_actual_case_sources_is_rechecked_at_preview_return(checked,monkeypatch):
    x=checked;target(x);original=steps.current_sources
    def expire(*args,**kwargs):
        result=original(*args,**kwargs)
        x['a']['now'][0]=datetime(2100,1,1,tzinfo=timezone.utc)
        return result
    monkeypatch.setattr(steps,'current_sources',expire)
    r=preview(x);assert r.status_code==200,r.text;v=r.json()
    assert v['classification']=='UNKNOWN' and not v['can_record'] and not v['target_current_available']
    assert 'CURRENT_REVIEWED_TARGET_REQUIRED' in v['blocking_reasons']
