"""Exact genuine historical template adoption keys, never a broad colon-key gate."""
from copy import deepcopy
from psycopg.types.json import Jsonb

from test_template_migration_independent import (
    upgrade_case, link_fixture, receipt_fixture, preparation_fixture, private_fixture_sessions,
    instance, confirmed, publication, admit, apply, stored, facts, all_pg_rows,
    assert_preserved, headers, GOALS, plan_read, adopt, adopt_body, accepted,
    verified, receipt_act,
)


def legacy_full(u):
    row,release=instance(u,GOALS,legacy=True);p=confirmed(u,row)
    with u['f'][1].connect() as c:
        for actor in ('prep-specialist-fixture-a','executor-a'):
            c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(row['run_id'],actor,'park-a','org-a'))
    current=plan_read(u['f'],p).json()
    assert adopt(u['f'],p,{**adopt_body(u['f'],p),'expected_plan_revision':current['revision'],'local_revision':True}).status_code==201
    group,dispatch=accepted(u['f'],p);verified(u['f'],p,'P3')
    receipt=u['f'][3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(u['f'][2],'executor-a')).json()
    receipt=receipt_act(u['f'],receipt,'SUBMIT').json();receipt=receipt_act(u['f'],receipt,'ACKNOWLEDGE').json();verified(u['f'],p,'P4')
    from test_case_lifecycle import read as local_read, act as local_act
    assert local_act(u['f'],p,local_read(u['f'],p).json(),'REVALIDATE').status_code==200
    verified(u['f'],p,'P5')
    assert stored(u,row)['events'][0]['request_key']=='tc:'+row['instance_id']+':ADOPT_PLAN'
    return row,p,group,dispatch,receipt


def migrate(u):
    row,p,group,dispatch,receipt=legacy_full(u);old=deepcopy(stored(u,row));before=facts(u)
    target=publication(u,GOALS,'1','Independent exact historical-key upgrade')
    _,data=admit(u,row,target);r=apply(u,row,data,'independent-exact-legacy')
    assert r.status_code in (200,201),r.text
    assert_preserved(old,stored(u,row),before,facts(u))
    return row,p,group,dispatch,receipt


def test_independent_genuine_legacy_key_full_five_goal_results(upgrade_case):
    u=upgrade_case;row,p,group,dispatch,receipt=migrate(u)
    before=all_pg_rows(u)
    r=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert r.status_code==200,r.text
    assert r.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    out={z['adapter_id']:z['actual_output'] for z in r.json()['results']}
    assert set(out)=={'P1','P2','P3','P4','P5'}
    assert out['P1']['materials'] and all(x['evidence_id'] and x['version'] for x in out['P1']['materials'])
    assert out['P2']['combination_id']==group['id']
    assert out['P3']['offer_id']==dispatch['current_offer']['id'] and out['P3']['receipt_step_id']==dispatch['receipt_step_id']
    assert out['P4']['receipt_id']==receipt['current_receipt']['id'] and out['P4']['receipt_version']==receipt['current_receipt']['version']
    with u['f'][1].connect() as c:
        event=c.execute("SELECT id FROM case_local_events WHERE preparation_id=%s AND action='REVALIDATE' ORDER BY revision DESC LIMIT 1",(row['preparation_id'],)).fetchone()
    assert out['P5']['local_record_state']=='READY' and out['P5']['revalidation_event_id']==str(event['id'])
    assert all_pg_rows(u)==before


def test_independent_arbitrary_legacy_like_key_is_refused_without_repair(upgrade_case):
    u=upgrade_case;row,_,_,_,_=migrate(u)
    plan=deepcopy(stored(u,row));original_fp=plan['events'][0]['fingerprint']
    plan['events'][0]['request_key']='tc:'+row['instance_id']+':ADOPT_PLAN:arbitrary'
    # Preserve the independent original request fingerprint: a colon prefix is
    # never enough to create a legitimate historical key or migration proof.
    assert plan['events'][0]['fingerprint']==original_fp
    with u['f'][1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    before=all_pg_rows(u)
    r=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert r.status_code==409,r.text
    assert all_pg_rows(u)==before and stored(u,row)==plan
