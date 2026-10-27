"""Literal ServiceRelease preflight answers, actual HTTP and owned PostgreSQL.

The only model transport is the existing exact offline selection fixture. New
versions use original independent review/publication/catalog commands; no old
release, selection, verification or business history is manufactured.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
from uuid import UUID, uuid4

import pytest

from parkweave.api import create_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_capability_contract import hash_instance
from test_preparation import preparation_fixture, headers, create
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain, GOALS, ok
from test_service_selection_candidates import planner
from test_service_selection_replay_acceptance import new_confirmed_parent, adopt_selection, execute_to_receipt, result as goal_results
from test_new_enterprise_local_chain import actual_http
from test_template_upgrade import publication
from service_release_acceptance_support import case_history, authority_snapshot
from test_service_case_steps import command as plan_command

OUT=Path('.runtime/service-release-preflight-independent')
RUN_ID=uuid4().hex
KINDS=('synthetic-material-preparation','synthetic-resource-coordination','synthetic-local-record-recheck')
ALL=('P1','P2','P3','P4','P5')


@pytest.fixture
def preflight_http(selection_full_chain,tmp_path):
    from parkweave.service_release_preflight import ServiceReleasePreflight
    a=selection_full_chain; original=a['f']; calls=[]
    OUT.mkdir(parents=True,exist_ok=True)
    private=OUT/('fixture-redaction-'+uuid4().hex+'.private.json')
    descriptor=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as output:output.write(json.dumps(sorted(original[2].values()))+'\n')
    facade=ParkInstanceConsumer(a['catalog'],ConsumerRepository(tmp_path/'preflight-original-cold.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
    repository=ConsumerRepository(tmp_path/'preflight-dedicated-audit.consumer.candidate.sqlite3')
    checker=ServiceReleasePreflight(a['catalog'],repository,enabled_for_isolated_tests=True)
    app=create_app(original[0],capability_catalog=a['catalog'],selection_planner=planner(calls,mode='all'),instance_consumer=facade,service_release_preflight=checker)
    with actual_http(app) as (client,traffic):
        yield dict(a=a,f=(*original[:3],client),facade=facade,checker=checker,repository=repository,calls=calls,traffic=traffic)


def chain(r):
    p,_=new_confirmed_parent(r,'PREFLIGHT-'+uuid4().hex[:6]); adopt_selection(r,p)
    execute_to_receipt(r,p,'PREFLIGHT independent original',1)
    value=goal_results(r,p); assert value['state']=='LOCAL_OUTPUTS_VERIFIED' and len(value['results'])==6
    assert value['source_trace']['candidate']['validator_version']==4 and not value['case_goal_completed']
    return p


def selected(r,p,kind=KINDS[1]):
    trace=goal_results(r,p)['source_trace']
    release=next(x for x in trace['service_capabilities'] if x['service_id']==kind)
    return next(x for x in trace['service_selection']['selection']['selections'] if x['release_id']==release['release_id'])


def target(r,kind=KINDS[1],scenario='title'):
    a=r['a']; goals=list(GOALS)
    if scenario=='goal_removal': goals.remove('LOCAL_SYNTHETIC_COORDINATION_RECORDS')
    published=publication(a,goals,source='2' if scenario=='source' else '1',name='SYNTHETIC independent preflight changed title')
    release=a['catalog'].register_release('park-a','org-a',uuid4().hex,template_scope=a['scope'],template_release_id=published['release_id'],expected_template_release_sha256=published['release_sha256'],service_id=kind)['release']
    instance=deepcopy(a['configs']['park-b',kind]); instance.update(release_id=release['release_id'],release_sha256=release['release_sha256'],config_revision=instance['config_revision']+1)
    if scenario=='field_mapping':
        for slot in instance['fields']: instance['fields'][slot]['input_field']='independent-new-'+slot
    instance['config_sha256']=hash_instance(instance)
    a['catalog'].bind_instance('park-b',uuid4().hex,instance)
    return dict(release=release,instance=instance,ref=dict(release_id=release['release_id'],revision=release['revision'],release_sha256=release['release_sha256'],instance_id=instance['instance_id'],config_revision=instance['config_revision'],config_sha256=instance['config_sha256']))


def endpoint(p): return '/api/preparations/'+p['preparation_id']+'/service-release-preflight'
def directory(r,p,actor='fixture-c'): return r['f'][3].get(endpoint(p),headers=headers(r['f'][2],actor))
def preview(r,p,old,new,actor='fixture-c'):
    return r['f'][3].get(endpoint(p)+'/preview',headers=headers(r['f'][2],actor),params=dict(original_release_id=old['release_id'],original_instance_id=old['instance_id'],target_instance_id=new['instance']['instance_id']))


def plan(r,p):
    with r['f'][1].connect() as c: return c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']


def all_pg(r):
    with r['f'][1].connect() as c:
        names=[x['tablename'] for x in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        return {name:c.execute('SELECT * FROM "'+name+'" ORDER BY to_jsonb("'+name+'")::text').fetchall() for name in names}


def sqlite_rows(repository):
    manager=getattr(repository,'transaction',None) or repository.connect
    with manager() as c:
        names=[row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name:[tuple(row) for row in c.execute('SELECT * FROM "'+name+'" ORDER BY rowid')] for name in names}


def originals(r):
    return dict(pg=all_pg(r),template=sqlite_rows(r['a']['engine'].repository),consumer=sqlite_rows(r['a']['consumer'].repository),cold=sqlite_rows(r['facade'].repository))


def record_body(r,p,old,new,value,reason='SYNTHETIC explicit read-only preflight report'):
    return dict(original_ref=old,target_ref=new['ref'],expected_plan_revision=plan(r,p)['revision'],expected_preflight_sha256=value['preflight_sha256'],reason=reason)


def save(r,p,body,key=None,actor='fixture-c'):
    return r['f'][3].post(endpoint(p),headers=headers(r['f'][2],actor,key or uuid4().hex),json=body)
def recover(r,p,key,actor='fixture-c'):
    return r['f'][3].get(endpoint(p)+'/recovery/'+key,headers=headers(r['f'][2],actor))


def expect(value,original,scenario,classification,affected,preserved,locked=()):
    ids={step['adapter_id']:step['id'] for step in original['steps']}
    wanted_a={ids[x] for x in affected}; wanted_p={ids[x] for x in preserved}; wanted_l={ids[x] for x in locked}
    got_a=set(value['affected']); got_p=set(value['preserved']); got_l=set(value['locked_affected'])
    record=dict(run_id=RUN_ID,test=os.environ.get('PYTEST_CURRENT_TEST'),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),scenario=scenario,
        expected_classification=classification,actual_classification=value['classification'],expected_affected=sorted(wanted_a),actual_affected=sorted(got_a),
        expected_preserved=sorted(wanted_p),actual_preserved=sorted(got_p),expected_locked=sorted(wanted_l),actual_locked=sorted(got_l),
        missed_count=len(wanted_a-got_a),wrong_count=len(got_a-wanted_a),wrong_preserved_count=len(wanted_p^got_p),wrong_locked_count=len(wanted_l^got_l),intentional_unknown=classification=='UNKNOWN')
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/('oracle-'+RUN_ID+'.jsonl')).open('a') as output: output.write(json.dumps(record,sort_keys=True)+'\n')
    assert value['classification']==classification,record
    assert got_a==wanted_a and got_p==wanted_p and got_l==wanted_l,record
    assert got_a.isdisjoint(got_p) and got_a|got_p==set(ids.values())


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('scenario,classification,affected,preserved',[
    ('title','NEEDS_RECHECK',ALL,()),('source','NEEDS_RECHECK',ALL,())])
def test_literal_release_title_and_source_deltas_preserve_actual_six_goal_case(preflight_http,kind,scenario,classification,affected,preserved):
    r=preflight_http;p=chain(r);old=selected(r,p,kind);new=target(r,kind,scenario); original=deepcopy(plan(r,p));before=originals(r)
    response=preview(r,p,old,new);assert response.status_code==200,response.text;value=response.json()
    expect(value,original,scenario+'_'+kind,classification,affected,preserved)
    assert value['contract_classification']==('COMPATIBLE' if scenario=='title' else 'NEEDS_RECHECK')
    if scenario=='title': assert value['contract_affected']==[] and set(value['current_case_affected'])=={x['id'] for x in original['steps']}
    assert value['can_record'] and originals(r)==before and plan(r,p)==original
    assert original['required_goals']==GOALS and len(original['required_goals'])==6


@pytest.mark.parametrize('scenario,classification,affected,preserved,locked',[
    ('unchanged','COMPATIBLE',(),ALL,()),
    ('title','LOCK_CONFLICT',ALL,(),('P1',)),('source','LOCK_CONFLICT',ALL,(),('P1',))])
def test_only_intersecting_lock_changes_classification_without_unlock(preflight_http,scenario,classification,affected,preserved,locked):
    r=preflight_http;p=chain(r);f=r['f'];v=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],'fixture-c')))
    step=next(x for x in v['steps'] if x['adapter_id']=='P1')
    ok(plan_command(f,p,'P1','LOCK',row=v,user='fixture-c',expected_source_sha256=step['source_sha256']))
    old=selected(r,p);new=dict(instance=r['a']['configs']['park-b',KINDS[1]],ref=old) if scenario=='unchanged' else target(r,scenario=scenario); original=deepcopy(plan(r,p));before=originals(r)
    value=ok(preview(r,p,old,new));expect(value,original,'lock_'+scenario,classification,affected,preserved,locked)
    assert originals(r)==before and plan(r,p)==original


def test_unchanged_original_release_control_is_compatible_but_not_cross_version(preflight_http):
    r=preflight_http;p=chain(r);old=selected(r,p);instance=r['a']['configs']['park-b',KINDS[1]]
    unchanged=dict(instance=instance,ref=old);original=deepcopy(plan(r,p));before=originals(r)
    value=ok(preview(r,p,old,unchanged));expect(value,original,'same_release_control','COMPATIBLE',(),ALL)
    assert value['contract_classification']=='COMPATIBLE' and value['contract_affected']==value['current_case_affected']==[]
    assert originals(r)==before


def test_removed_selected_mandatory_goal_is_breaking_even_if_dependency_step_survives(preflight_http):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r,scenario='goal_removal');original=deepcopy(plan(r,p));before=originals(r)
    value=ok(preview(r,p,old,new));expect(value,original,'required_goal_removed','BREAKING_REJECTED',ALL,())
    assert plan(r,p)['required_goals']==GOALS and originals(r)==before


def test_changed_input_mapping_requires_recheck_not_automatic_copy(preflight_http):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r,scenario='field_mapping');original=deepcopy(plan(r,p));before=originals(r)
    value=ok(preview(r,p,old,new));expect(value,original,'new_input_mapping','NEEDS_RECHECK',ALL,())
    assert originals(r)==before and plan(r,p)==original


@pytest.mark.parametrize('locked',['none','P1','P3'])
def test_resource_only_exact_partition_and_lock_intersection_at_new_preflight(preflight_http,locked):
    r=preflight_http;p=chain(r);f=r['f'];old=selected(r,p)
    if locked!='none':
        v=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],'fixture-c')));s=next(s for s in v['steps'] if s['adapter_id']==locked)
        ok(plan_command(f,p,locked,'LOCK',row=v,user='fixture-c',expected_source_sha256=s['source_sha256']))
    unchanged=dict(instance=r['a']['configs']['park-b',KINDS[1]],ref=old)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(r['a']['b_resources'][0],))
    original=deepcopy(plan(r,p));before=originals(r);value=ok(preview(r,p,old,unchanged))
    expect(value,original,'resource_only_lock_'+locked,'LOCK_CONFLICT' if locked=='P3' else 'NEEDS_RECHECK',('P2','P3','P4','P5'),('P1',),('P3',) if locked=='P3' else ())
    assert value['contract_classification']=='COMPATIBLE' and value['contract_affected']==[]
    assert originals(r)==before and plan(r,p)==original


def test_explicit_record_is_only_new_audit_journal_and_idempotent_cold_get(preflight_http):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));before=originals(r);journal=sqlite_rows(r['repository']);key=uuid4().hex
    body=record_body(r,p,old,new,value);saved=save(r,p,body,key);assert saved.status_code in (200,201),saved.text
    assert saved.json()['status']=='COMMITTED' and sqlite_rows(r['repository'])!=journal and originals(r)==before
    assert save(r,p,body,key).json()==saved.json()
    assert save(r,p,{**body,'reason':'SYNTHETIC changed reason conflicts'},key).status_code==409
    cold=ok(recover(r,p,key));assert cold['status']=='COMMITTED' and cold['recorded_preflight']['preflight_sha256']==value['preflight_sha256']
    assert ok(recover(r,p,'never-observed-'+uuid4().hex))['status']=='NOT_OBSERVED' and originals(r)==before


@pytest.mark.parametrize('actor',['fixture-a','fixture-b','prep-specialist-fixture-c','executor-c','executor-a'])
def test_current_case_owner_org_park_and_wrong_roles_cannot_preflight_or_record(preflight_http,actor):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));body=record_body(r,p,old,new,value);before=originals(r);journal=sqlite_rows(r['repository'])
    assert directory(r,p,actor).status_code==preview(r,p,old,new,actor).status_code==save(r,p,body,actor=actor).status_code==403
    assert originals(r)==before and sqlite_rows(r['repository'])==journal


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE','ACTIVE'])
def test_revocation_blocks_new_report_but_historical_recovery_needs_only_current_read(preflight_http,capability):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));body=record_body(r,p,old,new,value);key=uuid4().hex
    assert save(r,p,body,key).status_code==201
    with r['f'][1].connect() as c:
        if capability=='ACTIVE': c.execute("UPDATE principals SET active=false WHERE id='fixture-c'")
        elif capability=='PREPARE': c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-c'")
        else: c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-c' AND capability=%s",(capability,))
    before=originals(r);journal=sqlite_rows(r['repository'])
    assert save(r,p,body).status_code==403
    recovered=recover(r,p,key)
    assert recovered.status_code==(403 if capability in ('READ','ACTIVE') else 200)
    if recovered.status_code==200: assert recovered.json()['status']=='COMMITTED' and not recovered.json()['current_available']
    assert originals(r)==before and sqlite_rows(r['repository'])==journal


@pytest.mark.parametrize('change',['case_aba','preparation_aba','authority_aba','source_aba'])
def test_old_preview_cannot_record_after_actual_aba(preflight_http,change):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));body=record_body(r,p,old,new,value)
    if change=='case_aba':
        with r['f'][1].connect() as c: goal=c.execute('SELECT goal FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['goal']
        for text in (goal+' changed',goal):
            with r['f'][1].connect() as c: c.execute('UPDATE cases SET goal=%s WHERE id=%s',(text,p['case_id']))
    elif change=='preparation_aba':
        for delta in (1,-1):
            with r['f'][1].connect() as c: c.execute('UPDATE preparations SET revision=revision+%s WHERE id=%s',(delta,p['preparation_id']))
    elif change=='authority_aba':
        for active in (False,True):
            with r['f'][1].connect() as c: c.execute("UPDATE capability_grants SET active=%s WHERE principal_id='fixture-c' AND capability='READ'",(active,))
    else:
        id=r['a']['b_resources'][0]
        for delta in (1,-1):
            with r['f'][1].connect() as c: c.execute('UPDATE synthetic_resources SET capacity=capacity+%s WHERE id=%s',(delta,id))
    before=originals(r);journal=sqlite_rows(r['repository']);response=save(r,p,body)
    assert response.status_code==409,response.text
    assert originals(r)==before and sqlite_rows(r['repository'])==journal


def withdraw(r,new,kind):
    a=r['a']
    if kind=='template':
        from parkweave.template_candidate import Command
        v=a['engine'].read('template-publisher',a['scope'])
        a['engine'].command('template-publisher',a['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=v['revision'],expected_definition_sha256=v['definition_sha256'],reason='SYNTHETIC independent target source withdrawn'))
    else:
        park='park-a' if kind=='release' else 'park-b'
        with r['f'][1].connect() as c:
            revision=c.execute("SELECT service_capability_catalog->>'revision' AS revision FROM preparation_catalog WHERE park_id=%s AND version=1",(park,)).fetchone()['revision']
        if kind=='release': a['catalog'].withdraw_release(park,uuid4().hex,new['release']['release_id'],int(revision),'SYNTHETIC actual target withdrawal')
        else: a['catalog'].withdraw_instance(park,uuid4().hex,new['instance']['instance_id'],int(revision),'SYNTHETIC actual target withdrawal')


@pytest.mark.parametrize('kind',['release','instance','template'])
def test_withdrawn_target_refuses_new_report_and_cold_record_never_revives_it(preflight_http,kind):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));body=record_body(r,p,old,new,value);key=uuid4().hex
    assert save(r,p,body,key).status_code==201;withdraw(r,new,kind);before=originals(r);journal=sqlite_rows(r['repository'])
    current=ok(preview(r,p,old,new));expect(current,plan(r,p),'withdraw_'+kind,'UNKNOWN',ALL,())
    assert not current['can_record'] and not current['target_current_available']
    assert save(r,p,body).status_code==409
    historical=ok(recover(r,p,key));assert historical['status']=='COMMITTED' and not historical['current_available']
    assert historical['recorded_preflight']['preflight_sha256']==value['preflight_sha256'] and originals(r)==before and sqlite_rows(r['repository'])==journal


@pytest.mark.parametrize('field',['revision','config_revision','release_sha256','config_sha256'])
def test_unknown_target_version_or_hash_cannot_record(preflight_http,field):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);value=ok(preview(r,p,old,new));body=record_body(r,p,old,new,value)
    body['target_ref']={**body['target_ref'],field:(3 if 'revision' in field else '0'*64)}
    before=originals(r);journal=sqlite_rows(r['repository']);assert save(r,p,body).status_code==409
    assert originals(r)==before and sqlite_rows(r['repository'])==journal


def test_plain_original_case_without_v4_selection_cannot_manufacture_compatibility(preflight_http):
    r=preflight_http;p=create(r['f'],user='fixture-c')[0];before=originals(r);value=ok(directory(r,p))
    assert value['state']=='UNKNOWN' and value['originals']==value['targets']==[]
    assert originals(r)==before


def run_html(r,p,old,new,mode,classification='NEEDS_RECHECK',contract_classification='COMPATIBLE'):
    f=r['f'];OUT.mkdir(parents=True,exist_ok=True);attempt=mode+'-'+uuid4().hex[:8];lines=[];result=None;error=''
    process=subprocess.Popen(['node','tests/service_release_preflight_real_html.js'],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    def authority(active):
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-c' AND capability='READ'",(active,))
    controls=dict(revoke=lambda:authority(False),restore=lambda:authority(True),withdraw=lambda:withdraw(r,new,'release'))
    try:
        config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-c'],preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],plan_id=plan(r,p)['id'],original_ref=old,target_ref=new['ref'],mode=mode,classification=classification,contract_classification=contract_classification)
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            assert selector.select(timeout=45),'Original ServiceRelease preflight HTML made no progress within 45 seconds'
            line=process.stdout.readline()
            if not line:break
            lines.append(line);message=json.loads(line)
            if 'control' in message:
                controls[message['control']]();process.stdin.write('{}\n');process.stdin.flush()
            else:result=message;break
        code=process.wait(timeout=10);error=process.stderr.read();assert code==0,error
        assert result and result['scope']=='FULL_ORIGINAL_HTML_SERVICE_RELEASE_PREFLIGHT_REAL_HTTP_ASGI_OWNED_PG'
        return result
    finally:
        selector.close()
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(error+process.stderr.read())


@pytest.mark.parametrize('mode',['record','lost','lost_withdrawn','source','lock','breaking','pending','repeat','tampered'])
def test_actual_original_html_readonly_preflight_and_explicit_audit_record(preflight_http,mode):
    r=preflight_http;p=chain(r);old=selected(r,p)
    if mode=='lock':
        f=r['f'];v=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],'fixture-c')));s=v['steps'][0]
        ok(plan_command(f,p,'P1','LOCK',row=v,user='fixture-c',expected_source_sha256=s['source_sha256']))
    new=dict(instance=r['a']['configs']['park-b',KINDS[1]],ref=old) if mode=='pending' else target(r,scenario='source' if mode=='source' else 'goal_removal' if mode=='breaking' else 'title')
    before=originals(r);original=deepcopy(plan(r,p));journal=sqlite_rows(r['repository'])
    result=run_html(r,p,old,new,mode,classification='LOCK_CONFLICT' if mode=='lock' else 'BREAKING_REJECTED' if mode=='breaking' else 'NEEDS_RECHECK',contract_classification='NEEDS_RECHECK' if mode=='source' else 'BREAKING_REJECTED' if mode=='breaking' else 'COMPATIBLE')
    assert plan(r,p)==original and original['required_goals']==GOALS
    if mode!='lost_withdrawn': assert originals(r)==before
    else:
        after=originals(r)
        assert {k:v for k,v in after['pg'].items() if k!='preparation_catalog'}=={k:v for k,v in before['pg'].items() if k!='preparation_catalog'}
        assert all(after[k]==before[k] for k in ('template','consumer','cold'))
    assert len(r['calls'])==1,'Preflight must never dispatch even the offline model'
    assert len([c for c in result['calls'] if c['method']=='POST'])==(2 if mode=='repeat' else 1 if mode in ('record','lost','lost_withdrawn','tampered') else 0)
    if mode in ('source','lock','breaking','pending'): assert sqlite_rows(r['repository'])==journal


@pytest.mark.parametrize('mode',['current_403','late_aba','late_403','target_aba','unknown_dto'])
def test_actual_original_html_denials_unknown_schema_and_identity_selection_aba(preflight_http,mode):
    r=preflight_http;p=chain(r);old=selected(r,p);new=target(r);original=deepcopy(plan(r,p));journal=sqlite_rows(r['repository'])
    result=run_html(r,p,old,new,mode)
    assert all(c['method']=='GET' for c in result['calls']) and plan(r,p)==original and sqlite_rows(r['repository'])==journal


def test_v4_without_original_verify_baseline_is_unknown_and_cannot_record(preflight_http):
    r=preflight_http;p,_=new_confirmed_parent(r,'PREFLIGHT-NO-VERIFY');adopt_selection(r,p);old=selected(r,p);new=target(r)
    original=deepcopy(plan(r,p));before=originals(r);journal=sqlite_rows(r['repository']);value=ok(preview(r,p,old,new))
    expect(value,original,'missing_original_verify','UNKNOWN',ALL,())
    assert not value['can_record'] and save(r,p,record_body(r,p,old,new,value)).status_code==409
    assert originals(r)==before and sqlite_rows(r['repository'])==journal
