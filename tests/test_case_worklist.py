"""Real existing owned PG fixtures and ASGI; no native security probe."""
from uuid import UUID,uuid4
import pytest
from parkweave import case_worklist as work
from parkweave.store import Store
from parkweave.domain import Intake
from test_preparation import preparation_fixture,headers,create,add,command
from test_executor_receipts import receipt_fixture,ready,act as receipt_command
from test_service_dispatches import offer,command as dispatch_command
from test_case_cancellation import snapshot,post as cancel_case


def page(f,user='fixture-a',**query):
    return f[3].get('/api/cases/worklist',headers=headers(f[2],user),params=query)


def item(f,p,want):
    before=snapshot(f);r=page(f);assert r.status_code==200,r.text
    v=r.json();assert v['read_only'] and v['recorded_states_only'] and not v['automatically_replayed']
    found=next(x for x in v['items'] if x['case_id']==p['case_id'])
    assert found['attention']==want and not found['case_goal_completed'] and not found['evidence_verified']
    assert 'current_receipt' not in found and 'executor_id' not in found and 'materials' not in found
    assert snapshot(f)==before
    return found


def test_existing_business_path_updates_queue_after_every_actual_command(receipt_fixture):
    f=receipt_fixture;p,_,_=create(f,goal='SYNTHETIC private request <script>')
    item(f,p,'NEEDS_MATERIALS')
    p=command(f,p,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC request').json()
    item(f,p,'MATERIAL_CORRECTION')
    p=add(f,p).json();p=add(f,p,'material_outline').json()
    p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC independent review').json()
    item(f,p,'OWNER_CONFIRMATION')
    p=command(f,p,'CONFIRM',reason='SYNTHETIC owner').json();item(f,p,'NEEDS_DISPATCH')
    f[1].assign_status('executor-a',UUID(p['run_id']))
    d=offer(f,p)[0].json();item(f,p,'WAITING_ACCEPTANCE')
    d=dispatch_command(f,d,'DECLINE').json();item(f,p,'NEEDS_REASSIGNMENT')
    d=offer(f,p,revision=d['revision'])[0].json();d=dispatch_command(f,d,'ACCEPT').json()
    row=item(f,p,'WAITING_RECEIPT');assert row['receipt_step_id']==d['receipt_step_id']
    receipt=f[3].get('/api/executor-receipts/'+row['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    receipt=receipt_command(f,receipt,'SUBMIT').json();item(f,p,'OWNER_RECEIPT_REVIEW')
    receipt=receipt_command(f,receipt,'REQUEST_CHANGES').json();item(f,p,'RECEIPT_CORRECTION')
    receipt=receipt_command(f,receipt,'SUBMIT').json();receipt=receipt_command(f,receipt,'ACKNOWLEDGE').json()
    item(f,p,'LOCAL_ACKNOWLEDGED')
    cold=work.read(Store(f[0].dsn),f[2]['fixture-a']);assert cold==page(f).json()


def test_cancellation_keeps_readable_history_and_independent_release_warning(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f)
    assert cancel_case(f,p).status_code==200
    row=item(f,p,'CANCELLED');assert row['resource_release_required_separately'] and row['open_target']=='materials'


def test_source_change_does_not_keep_actionable_old_receipt(receipt_fixture):
    f=receipt_fixture;p=ready(f);d=offer(f,p)[0].json();d=dispatch_command(f,d,'ACCEPT').json()
    item(f,p,'WAITING_RECEIPT')
    # Existing legal material reopen, no business history discarded.
    p=command(f,p,'REOPEN',reason='SYNTHETIC source changed').json()
    row=item(f,p,'NEEDS_MATERIALS');assert row['receipt_step_id'] is None and row['open_target']=='materials'


def test_bounded_case_pagination_tenant_owner_isolation_no_setup_writes(preparation_fixture):
    f=preparation_fixture;ps=[create(f)[0] for _ in range(5)]
    create(f,'fixture-b',goal='FOREIGN_ORG_SECRET');create(f,'fixture-c',goal='FOREIGN_PARK_SECRET')
    before=snapshot(f);seen=[];after=None
    for _ in range(3):
        v=page(f,limit=2,**({'after':after} if after else {})).json()
        seen.extend(x['case_id'] for x in v['items']);after=v['next_after']
        assert all(x['preparation_id'] in {p['preparation_id'] for p in ps} for x in v['items'])
    assert seen==sorted(p['case_id'] for p in ps) and after is None and snapshot(f)==before
    assert 'FOREIGN_' not in page(f).text
    assert len(page(f,'fixture-b').json()['items'])==1


@pytest.mark.parametrize('changed',['READ','PREPARE','identity','role'])
def test_current_revocation_or_nonowner_role_cannot_read_old_queue(preparation_fixture,changed):
    f=preparation_fixture;create(f);assert page(f).json()['items']
    with f[1].connect() as c:
        if changed=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif changed=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        elif changed=='identity':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:c.execute("UPDATE principals SET role='service_executor' WHERE id='fixture-a'")
    before=snapshot(f);r=page(f);assert r.status_code==403 and 'items' not in r.json() and snapshot(f)==before


@pytest.mark.parametrize('query',[{'limit':0},{'limit':51},{'after':'bad'}])
def test_malformed_query_rejected(preparation_fixture,query):
    assert page(preparation_fixture,**query).status_code==422


def test_missing_preparation_opens_original_run_and_read_transaction_is_enforced(preparation_fixture):
    f=preparation_fixture;r=f[0].submit(f[2]['fixture-a'],uuid4().hex,Intake(goal='SYNTHETIC no preparation'))
    f[0].finish(f[0].claim('worklist-no-preparation'))
    original=f[0].auth
    def checked(c,*a,**kw):
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
        assert c.execute('SHOW transaction_isolation').fetchone()['transaction_isolation']=='read committed'
        return original(c,*a,**kw)
    f[0].auth=checked
    try:
        x=page(f).json()['items'][0];assert x['run_id']==str(r) and x['attention']=='NEEDS_PREPARATION' and x['open_target']=='run'
    finally:f[0].auth=original


def test_current_offer_selects_receipt_generation_not_historical_acknowledgement(receipt_fixture):
    f=receipt_fixture;p=ready(f);d=offer(f,p)[0].json();d=dispatch_command(f,d,'ACCEPT').json()
    item(f,p,'WAITING_RECEIPT')
    # Owner-only corrupt pointer negative control: a stale accepted step must not
    # be projected as the new current offer's receipt generation.
    with f[1].connect() as c:
        c.execute('UPDATE service_receipt_steps SET preparation_sha256=%s WHERE id=%s',('f'*64,d['receipt_step_id']))
    row=item(f,p,'UNKNOWN');assert row['receipt_step_id'] is None


def test_existing_specialist_and_executor_roles_do_not_gain_owner_queue(receipt_fixture):
    f=receipt_fixture;p=ready(f)
    for user in ('prep-specialist-fixture-a','executor-a','unassigned'):
        r=page(f,user);assert r.status_code==403 and 'items' not in r.json()


@pytest.mark.parametrize('case_state,local_state,want',[('RECONCILING','LOCAL_RECORD_CLOSED','RECONCILING'),
    ('CANCELLED','LOCAL_RECORD_CLOSED','CANCELLED'),('NEEDS_INPUT','LOCAL_RECORD_CLOSED','LOCAL_CLOSED')])
def test_recorded_terminal_and_reconciliation_precedence(case_state,local_state,want):
    assert work.classify(dict(state=case_state),None,None,None,dict(state=local_state))==want
