"""Actual ASGI/owned PG composition; fixture authority explicitly disclosed."""
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave.service_capability_contract import hash_instance
from release_new_case_support import (release_case,cancel33_case,capability_resource_catalog,
    capability_catalog,preparation_fixture,receipt_fixture,publish_revision,admit_new,
    new_planned_case,new_holds,approval,ok)
from test_preparation import headers
from test_case_resource_delivery import submit, recover
from test_service_case_steps import verified
from test_resource_bundles import states
from service_release_acceptance_support import case_history


def test_new_release_fresh_case_separate_approval_capacity_and_original_key_recovery(release_case):
    t=release_case
    with TestClient(t['app']) as api:
        release_id=publish_revision(api,t);refs=admit_new(t,release_id)
        f,p=new_planned_case(t,api)
        for field in ('run_id','case_id','preparation_id'):assert p[field]!=t['x']['p'][field]
        with f[1].connect() as c:
            plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        assert plan['id']!=t['old']['preparations'][0]['service_case_plan']['id']
        # Current adopted immutable candidate snapshot contains exactly new Release refs.
        with f[1].connect() as c:
            parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        from parkweave.service_selection_candidates import find
        saved=find(parent,plan['candidate_consumption']['candidate_id'])
        selections=saved['selection']['selections']
        assert {r['release_id'] for r in selections}=={r['release_id'] for r,i in refs}
        holds=new_holds(t,f);item,data=approval(t,f,p,holds)
        old_approval=t['old']['preparations'][0]['candidate_plan_approvals']['events'][-1]['approval_id']
        assert submit(f,p,{**data,'approval_id':old_approval}).status_code==409
        assert item['id']!=old_approval
        key=uuid4().hex;body={**data,'approval_id':item['id']}
        result=ok(submit(f,p,body,key),201)
        # Discard success receipt and use the original GET route, never a new write.
        recovered=ok(recover(f,p,key));assert recovered['receipt']==result['receipt']
        verified(f,p,'P2')
        assert states(f,holds)==['CONFIRMED']*3
        assert states(f,t['x']['holds'])==['CONFIRMED']*3
        assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
        assert not result['formal_release'] and not result['case_goal_completed']


@pytest.mark.parametrize('change',['config_after_approval','capacity_after_approval','execute_revoked'])
def test_new_release_commit_rechecks_current_version_capacity_and_revocation(release_case,change):
    t=release_case
    with TestClient(t['app']) as api:
        refs=admit_new(t,publish_revision(api,t));f,p=new_planned_case(t,api)
        holds=new_holds(t,f);item,data=approval(t,f,p,holds)
        if change=='config_after_approval':
            instance=deepcopy(refs[0][1]);instance['config_revision']+=1
            instance['fields']['need_summary']['input_field']='SYNTHETIC-changed-input-mapping-after-approval'
            instance['config_sha256']=hash_instance(instance)
            t['a']['catalog'].bind_instance('park-a',uuid4().hex,instance)
        else:
            with f[1].connect() as c:
                if change=='capacity_after_approval':
                    c.execute('UPDATE synthetic_resources SET capacity=1 WHERE id=%s',(holds[0]['resource_id'],))
                else:
                    f[1].lock_principal(c,'fixture-a',exclusive=True)
                    c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        result=submit(f,p,{**data,'approval_id':item['id']})
        assert result.status_code==(403 if change=='execute_revoked' else 409),result.text
        assert states(f,holds)==['HELD']*3
        assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
        with f[1].connect() as c:
            assert not c.execute('SELECT 1 FROM case_resource_links WHERE preparation_id=%s',(p['preparation_id'],)).fetchone()


@pytest.mark.parametrize('change',['old_release_new_hash','new_release_old_hash','stale_config','prepare_revoked'])
def test_new_cold_input_rejects_mixed_release_and_stale_configuration(release_case,change):
    t=release_case
    with TestClient(t['app']) as api:
        # Capture the exact old cold-input body at the facade boundary without a write.
        directory=ok(api.get('/api/service-instance-configurations',headers=headers(t['f'][2])))
        old=next(i for i in directory['instances'] if i['service_id']=='synthetic-material-preparation')
        refs=admit_new(t,publish_revision(api,t))
        directory=ok(api.get('/api/service-instance-configurations',headers=headers(t['f'][2])))
        new=next(i for i in directory['instances'] if i['service_id']=='synthetic-material-preparation')
        body=dict(instance_id=new['instance_id'],expected_config_revision=new['config_revision'],expected_config_sha256=new['config_sha256'],
            expected_release_id=new['release_id'],expected_release_sha256=new['release_sha256'],goal='SYNTHETIC mixed version rejection',required_goals=['LOCAL_MATERIAL_PREPARATION'],
            fields={new['fields'][s]:dict(slot=s,text='SYNTHETIC fresh '+s,source_kind='USER_STATEMENT',source_label='SYNTHETIC own new input') for s in ('need_summary','material_outline')},reason='SYNTHETIC explicit independent request')
        if change=='old_release_new_hash':body['expected_release_id']=old['release_id']
        elif change=='new_release_old_hash':body['expected_release_sha256']=old['release_sha256']
        elif change=='stale_config':
            body['expected_config_revision']=old['config_revision'];body['expected_config_sha256']=old['config_sha256']
        else:
            with t['f'][1].connect() as c:
                t['f'][1].lock_principal(c,'fixture-a',exclusive=True)
                c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        reply=api.post('/api/service-instance-cold-inputs',headers=headers(t['f'][2],key=uuid4().hex),json=body)
        assert reply.status_code==(403 if change=='prepare_revoked' else 409),reply.text
        assert case_history(t['f'][1],t['x']['p']['preparation_id'])==t['old']
