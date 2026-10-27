"""Original strict Release/current P2 initial state; no new business commands."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from release_new_case_support import (release_case,cancel33_case,capability_resource_catalog,
    capability_catalog,preparation_fixture,receipt_fixture,publish_revision,admit_new,
    new_planned_case,new_holds,approval,ok)
from test_preparation import headers
from test_case_resource_delivery import submit
from test_service_case_steps import verified
from test_service_dispatches import offer,command as dispatch_command
from test_executor_receipts import act as receipt_command
from service_release_acceptance_support import case_history


@pytest.fixture
def strict_p2(release_case):
    t=release_case
    with TestClient(t['app']) as api:
        release=publish_revision(api,t);refs=admit_new(t,release)
        f,p=new_planned_case(t,api);holds=new_holds(t,f);item,data=approval(t,f,p,holds)
        sent=ok(submit(f,p,{**data,'approval_id':item['id']}),201)
        plan=verified(f,p,'P2')
        assert all(s['state']=='VERIFIED' for s in plan['steps'][:2])
        assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
        yield dict(t=t,f=f,p=p,holds=holds,refs=refs,release=release,approval=item,delivery=sent)


def accept_new(x):
    f,p=x['f'],x['p']
    catalog=ok(f[3].get('/api/service-dispatches/catalog',params={'preparation_id':p['preparation_id']},headers=headers(f[2],'prep-specialist-fixture-a')))
    row=ok(offer(f,p,expected_business_frontier=catalog['business_frontier'])[0],201)
    return ok(dispatch_command(f,row,'ACCEPT',expected_business_frontier=row['business_frontier']))


def submitted(x):
    d=accept_new(x);verified(x['f'],x['p'],'P3')
    row=ok(x['f'][3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(x['f'][2],'executor-a')))
    return ok(receipt_command(x['f'],row,'SUBMIT',text='SYNTHETIC strict new Release manual local receipt',expected_business_frontier=row['business_frontier']))


def snapshot(f):
    """All owned public product rows; current rejection audit is separate."""
    with f[1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in tables}
