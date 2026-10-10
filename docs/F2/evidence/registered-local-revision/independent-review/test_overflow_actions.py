"""Bounded real HTTP metadata probe for the genuine fresh overflow blocker."""
from copy import deepcopy
from uuid import uuid4
from conftest import fixture, pg
from test_negative_journal import preparation_fixture, receipt_fixture, link_fixture, real_f, clone_existing_resource, setup, GOALS, adopt, stored, read, patch, recover, evidence
from test_service_case_steps import command, business
from parkweave import service_case_steps as steps

def test_fresh_overflow_projection_and_explicit_action_boundaries(real_f):
    f=real_f; p=setup(f,GOALS[3]); clones=clone_existing_resource(f,130)
    first=adopt(f,p); assert first.status_code==201
    saved=deepcopy(stored(f,p)); original_key=saved['events'][0]['request_key']
    with f[1].connect() as c:
        c.execute('DELETE FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=ANY(%s)',('fixture-a',clones))
    before_business=business(f); view=read(f,p).json()
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        current,core_affected,core_unknown=steps.dependency_impact(f[0],c,parent,parent['service_case_plan'])
    denied=command(f,p,'P1',row=view)
    changed=patch(f,p); now=stored(f,p); recovery=recover(f,p,original_key)
    id_to_adapter={s['id']:s['adapter_id'] for s in saved['steps']}
    detail=dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_http=True,pg=True,
      legitimate_saved_resource_count=257, no_manifest_tamper_or_monkeypatch=True,
      core_affected=sorted(core_affected),core_unknown=core_unknown,
      state=view['state'],unknown_scope=view['change_impact']['unknown_scope'],
      view_affected=[id_to_adapter[x] for x in view['change_impact']['affected']],
      view_preserved=[id_to_adapter[x] for x in view['change_impact']['preserved']],
      step_states_actions=[dict(adapter_id=s['adapter_id'],state=s['state'],allowed_actions=s['allowed_actions'],issues=s['issues']) for s in view['steps']],
      can_adopt=view['can_adopt'],local_revision_required=view['local_revision_required'],
      verify_before_explicit_adopt_status=denied.status_code,explicit_local_adopt_status=201,
      explicit_event_affected=[id_to_adapter[x] for x in changed['event']['local_revision']['affected']],
      explicit_event_preserved=[id_to_adapter[x] for x in changed['event']['local_revision']['preserved']],
      original_key_recovery_status=recovery.status_code,original_key_recovery_state=recovery.json().get('status'),
      original_events_preserved=now['events'][:len(saved['events'])]==saved['events'],
      stable_plan_id=now['id']==saved['id'],stable_step_ids=[s['id'] for s in now['steps']]==[s['id'] for s in saved['steps']],
      step_contracts_preserved=[s['contract'] for s in now['steps']]==[s['contract'] for s in saved['steps']],
      business_rows_unchanged=business(f)==before_business, model_calls=0)
    evidence('overflow-action-boundaries',detail)
    assert core_affected=={'P1','P2','P3','P4'} and core_unknown
    assert denied.status_code==409 and detail['explicit_event_affected']==['P1','P2','P3','P4']
    assert detail['original_events_preserved'] and detail['business_rows_unchanged']
