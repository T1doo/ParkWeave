"""Independent actual app SQL, private writer RPC and current-auth counterexamples."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4
import secrets
import pytest
from psycopg.types.json import Jsonb
from parkweave import native_run_access as native, native_run_access_writer as writer
from parkweave.api import create_app
from parkweave.native_run_access_activation import Activate
from parkweave.store import Store, Denied
from test_preparation import preparation_fixture, filled, headers
from test_executor_receipts import receipt_fixture
from test_native_run_access_writer import writer_fixture, approve, act, body
from test_native_run_access_activation import activate, activation_body, business, path


def unsigned_request(h, target='executor-a', key='independent-unsigned'):
    """App may update JSON but has no writer signing key; no permission repair."""
    data=body(h.a,'REQUEST')
    with h.f[0].connect() as c:
        run=c.execute('SELECT * FROM runs WHERE id=%s',(h.parent['run_id'],)).fetchone()
        parent=h.bridge._parent(c,run)
        request=dict(request_id=str(uuid4()),requester_id='fixture-a',target_id=target,
            target_role='service_executor',capability='READ',source=h.bridge._source(c,run,parent),
            authority=h.bridge._authority_snapshot(c,run,target),
            requested_validity=data.requested_validity.model_dump(mode='json'))
        receipt=dict(namespace=native.NAMESPACE,run_id=h.parent['run_id'],actor_id='fixture-a',
            request_key=key,fingerprint=native._hash(dict(run_id=h.parent['run_id'],command=data.model_dump(mode='json'))),
            action='REQUEST',reason=data.reason,revision=1,state='REQUESTED',request=request,lease_id=None,
            recorded_at=datetime.now(timezone.utc).isoformat(),actual_run_access=False,
            actual_assignment_written=False,projection_state='NON_EFFECTIVE')
        ledger=dict(namespace=native.NAMESPACE,revision=1,state='REQUESTED',events=[receipt],request=request,
                    lease_id=None,leases=[])
        c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',(Jsonb(ledger),h.parent['run_id']))
    return receipt


@pytest.mark.parametrize('operation',['COMMAND','ACTIVATE'])
def test_independent_foreign_run_key_never_returns_unsigned_receipt(writer_fixture,operation):
    h=writer_fixture;approve(h)
    data=body(h.a,'REVOKE') if operation=='COMMAND' else Activate.model_validate(activation_body(h.a))
    other=filled(h.f);key='independent-cross-run-key'
    with h.f[0].connect() as c:
        stored=c.execute('SELECT native_run_access_protocol value FROM runs WHERE id=%s',(h.parent['run_id'],)).fetchone()['value']
        fake=deepcopy(stored['events'][0]);fake.pop('writer_proof')
        fake.update(run_id=other['run_id'],request_key=key,
            fingerprint=native._hash(dict(run_id=h.parent['run_id'],command=data.model_dump(mode='json'))))
        fake['request']['source'].update(run_id=other['run_id'],case_id=other['case_id'],preparation_id=other['preparation_id'])
        c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',
            (Jsonb(dict(namespace=native.NAMESPACE,revision=1,state='REQUESTED',events=[fake],
                        request=fake['request'],lease_id=None,leases=[])),other['run_id']))
    before=business(h.a)
    response=h.f[3].post(path(h.a)+('/commands' if operation=='COMMAND' else '/activate'),
        headers=headers(h.f[2],key=key),json=data.model_dump(mode='json'))
    recovery=h.bridge.recover(h.f[2]['fixture-a'],UUID(h.parent['run_id']),key)
    h.observe('INDEPENDENT_FOREIGN_ORIGINAL_KEY',operation=operation,status=response.status_code,found=recovery['found'])
    assert response.status_code==409
    assert not recovery['found'] and business(h.a)==before


@pytest.mark.parametrize('late',[False,True])
def test_independent_private_context_cannot_enter_api_store(writer_fixture,late):
    h=writer_fixture;store=Store(h.f[0].dsn if late else h.f[1].dsn)
    if late:create_app(store)
    context=writer.WriterContext(store,h.bootstrap['policy'],bytes.fromhex(h.bootstrap['key']))
    with pytest.raises(Denied):
        bridge=native.NativeRunAccess(store,writer=context)
        store._native_run_access=bridge
        create_app(store)
    h.observe('INDEPENDENT_PRIVATE_CONTEXT_REJECTED',late_binding=late)


def test_independent_unsigned_target_cannot_grant_metadata_participation(writer_fixture):
    h=writer_fixture
    assert h.f[3].get(path(h.a),headers=headers(h.f[2],'unassigned')).status_code==403
    unsigned_request(h,target='unassigned')
    response=h.f[3].get(path(h.a),headers=headers(h.f[2],'unassigned'))
    h.observe('INDEPENDENT_UNSIGNED_TARGET_METADATA',status=response.status_code,
        writer_history_verified=response.json().get('writer_history_verified'),
        actual_run_access=response.json().get('actual_run_access'))
    assert response.status_code==403, 'Unsigned app JSON changed who can read the private native ledger'


def test_independent_original_key_requires_authenticated_receipt(writer_fixture):
    h=writer_fixture;fake=unsigned_request(h)
    response=h.f[3].get(path(h.a)+'/commands/'+fake['request_key'],headers=headers(h.f[2]))
    value=response.json()
    h.observe('INDEPENDENT_UNSIGNED_KEY_RECOVERY',status=response.status_code,found=value.get('found'),
        exact_unsigned_receipt_returned=value.get('receipt')==fake,
        receipt_verification_flag=value.get('writer_receipt_verified'),actual_run_access=value.get('actual_run_access'))
    assert response.status_code in (403,409) or value.get('found') is False or value.get('writer_receipt_verified') is False, \
        'Recovery called an unissued receipt found without an authentication failure marker'


def test_independent_revoke_preserves_exact_history_and_blocks_current_read(writer_fixture):
    h=writer_fixture;approve(h);original=activate(h.a,key='independent-activation-original').json()
    h.f[1].revoke_capability('executor-a','READ')
    recovered=h.bridge.recover(h.f[2]['fixture-a'],UUID(h.parent['run_id']),'independent-activation-original')
    assert recovered['found'] and recovered['receipt']==original and not recovered['actual_run_access']
    assert h.bridge.writer.verify([original]) is True
    decision=act(h.a,'REVOKE',key='independent-revoke-stale-target')
    assert decision['state']=='REVOKED' and h.bridge.writer.verify([decision])
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    h.observe('INDEPENDENT_STALE_TARGET_REVOKE',history_exact=True,current_access=False)


def test_independent_new_key_and_approved_rows_cannot_replace_original_signing_key(writer_fixture):
    h=writer_fixture;approve(h);original=activate(h.a,key='independent-old-key').json();before=business(h.a)
    h.stop(h.writer_process)
    h.bootstrap={**h.bootstrap,'key':secrets.token_hex(32)}
    h.start_writer();h.bind()
    response=h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a'))
    meta=h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))
    assert response.status_code==403 and not meta['writer_history_verified'] and not meta['actual_run_access']
    assert h.bridge.writer.verify([original]) is False
    assert business(h.a)==before
    h.observe('INDEPENDENT_SIGNING_KEY_CHANGED',stored_approved_retained=True,original_proof_verified=False,business_read_status=403)


def test_independent_current_named_approver_role_required(writer_fixture):
    from test_native_run_access import APPROVER
    h=writer_fixture;request=act(h.a,'REQUEST',key='independent-request')
    data=body(h.a,'APPROVE')
    with h.f[1].connect() as c:
        h.f[1].lock_principal(c,APPROVER,exclusive=True)
        c.execute("UPDATE principals SET role='resource_admin' WHERE id=%s",(APPROVER,))
    with pytest.raises(Denied):act(h.a,'APPROVE',data=data,key='independent-role-changed')
    recovered=h.bridge.recover(h.f[2]['fixture-a'],UUID(h.parent['run_id']),'independent-request')
    assert recovered['receipt']==request and not recovered['actual_run_access']
    h.observe('INDEPENDENT_CURRENT_APPROVER_ROLE',decision_denied=True,original_history_exact=True)
