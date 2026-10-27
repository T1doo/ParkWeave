"""Existing least-app-role synthetic PG; ASGI only, no listener or browser."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID
import json
import pytest
from psycopg.types.json import Jsonb

from parkweave import history_summary as hs, fact_history_read_source as read, case_fact_clarifications as facts
from parkweave import resource_combinations
from parkweave.store import Store, Denied
from test_preparation import preparation_fixture, filled, headers
from test_case_fact_clarifications import three, declare, confirm, assertion
from test_history_summary import sample, seal
from test_case_fact_bundle import setup as bundle_setup, register, choose, get as bundle_get, command as bundle_command, body as bundle_body


def parent(f, p):
    with f[0].connect() as c:
        return c.execute('SELECT * FROM preparations WHERE id=%s', (UUID(p['preparation_id']),)).fetchone()


def selected(f):
    resource_combinations.seed_synthetic(f[1])
    p = filled(f);three(f);declare(f, p);confirm(f, p)
    return p


def descriptor(f, p):
    with f[0].connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        return hs.current_context(f[0], c, f[2]['fixture-a'], UUID(p['preparation_id']))


def snapshot(f):
    with f[1].connect() as c:
        tables = [row['tablename'] for row in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()]
        return {table:c.execute('SELECT * FROM '+table+' ORDER BY to_jsonb('+table+')::text').fetchall() for table in tables}


def memory_reader(f, p, stage):
    context = descriptor(f, p)
    _, _, row, checks = sample(stage)
    doc = json.loads(row['document']);doc['actor_id'] = context.owner
    doc['binding'].update(preparation_id=context.preparation, case_id=context.case, run_id=context.run)
    row = seal(doc, checks)
    anchor = hs.RecordAnchor(doc['id'], row['request_key'], hs.row_sha256(row), context.source_sha256)
    baseline = hs.TrustedBaseline(stage, checks.storage_scope, checks.namespace, checks.document_version,
        checks.execution_contract, context.owner, context.park, context.org, context.preparation, context.case,
        context.run, context.database, context.now-timedelta(minutes=1), context.now+timedelta(minutes=10), False, (anchor,))
    return hs.MemoryHistorySummaryReader(stage, {context.preparation:baseline}, {context.preparation:(row,)})


@pytest.mark.parametrize('stage', ['P4','P5'])
def test_declared_source_read_after_execution_authority_removed_and_old_gates_stay_closed(preparation_fixture, monkeypatch, stage):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, stage)
    with f[1].connect() as c:
        for table, clause in [('capability_grants',"capability='EXECUTE'"), ('field_grants',"capability='WRITE'"),
                ('preparation_grants',"capability='PREPARE'"), ('action_grants',"action='case.create'"),
                ('synthetic_resource_grants',"capability='HOLD'")]:
            c.execute("UPDATE "+table+" SET active=false WHERE principal_id='fixture-a' AND "+clause)
    def forbidden(*args, **kwargs):raise AssertionError('execution dependency used for independent READ')
    for name in ('gate','_owner','_scope','_sources'):monkeypatch.setattr(facts, name, forbidden)
    before = snapshot(f)
    result = reader.read(Store(f[0].dsn), f[2]['fixture-a'], UUID(p['preparation_id']), 'synthetic-key')
    assert result['status'] == 'COMMITTED' and result['history'][0]['source_state'] == 'SNAPSHOT_MATCH'
    assert result['result']['state'] == 'FAILED' and not result['execution_available'] and result['formal_writes'] == 0
    raw = json.dumps(result)
    for secret in ('地区甲','合成服务需求','source_excerpt','source_snapshot','choices','fact_clarifications'):
        assert secret not in raw
    assert snapshot(f) == before
    route = 'receipt' if stage == 'P4' else 'lifecycle'
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview', headers=headers(f[2])).status_code == 403
    body = dict(expected_preparation_revision=1, expected_request_revision=1,
        expected_source_sha256='0'*64, review_decision='ACKNOWLEDGE')
    if stage == 'P5':body['lifecycle_sequence'] = 'REVALIDATE_CLOSE_REOPEN'
    assert f[3].post('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview', headers=headers(f[2], key='synthetic-old-gate'), json=body).status_code == 403


@pytest.mark.parametrize('change', ['read','field_read','field_expired','inactive','wrong_owner','wrong_tenant',
    'missing_ledger','truncated_ledger','missing_receipt','extra_receipt','receipt_case','receipt_status','ledger_rehash',
    'source_body','source_version','source_missing','source_expired','source_tenant','source_kind'])
def test_current_read_and_persisted_source_refusals_have_no_writes(preparation_fixture, change):
    f = preparation_fixture;p = selected(f);id = UUID(p['preparation_id']);token = f[2]['fixture-a']
    if change == 'wrong_owner':token = f[2]['fixture-b']
    else:
        with f[1].connect() as c:
            if change == 'read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif change == 'field_read':c.execute("UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'")
            elif change == 'field_expired':c.execute("UPDATE field_grants SET valid_until=clock_timestamp() WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'")
            elif change == 'inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
            elif change == 'wrong_tenant':c.execute("UPDATE principals SET org_id='other' WHERE id='fixture-a'")
            elif change == 'missing_ledger':c.execute('UPDATE preparations SET fact_clarifications=NULL WHERE id=%s', (id,))
            elif change in ('truncated_ledger','ledger_rehash'):
                ledger = deepcopy(c.execute('SELECT fact_clarifications FROM preparations WHERE id=%s',(id,)).fetchone()['fact_clarifications'])
                if change == 'truncated_ledger':ledger['events'].pop();ledger['revision'] -= 1
                else:
                    event = ledger['events'][-1];event['reason'] = 'SYNTHETIC forged ledger'
                    event['decision_sha256'] = facts._hash({k:v for k,v in event.items() if k != 'decision_sha256'})
                c.execute('UPDATE preparations SET fact_clarifications=%s WHERE id=%s', (Jsonb(ledger), id))
            elif change == 'missing_receipt':c.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND action='CONFIRM_FACT_PURPOSE'", (id,))
            elif change == 'extra_receipt':c.execute("UPDATE preparation_events SET action='CONFIRM_FACT_PURPOSE' WHERE preparation_id=%s AND action='ADD_EVIDENCE'", (id,))
            elif change == 'receipt_case':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{case_id}','\"wrong\"') WHERE preparation_id=%s AND action='CONFIRM_FACT_PURPOSE'", (id,))
            elif change == 'receipt_status':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{public_status,state}','\"UNKNOWN\"') WHERE preparation_id=%s AND action='CONFIRM_FACT_PURPOSE'", (id,))
            elif change == 'source_body':c.execute("UPDATE fact_assertions SET source_excerpt='SYNTHETIC changed without fingerprint' WHERE field_name='region'")
            elif change == 'source_version':c.execute("UPDATE fact_assertions SET revision=revision+1 WHERE field_name='region'")
            elif change == 'source_missing':c.execute("DELETE FROM fact_assertions WHERE field_name='region'")
            elif change == 'source_expired':c.execute("UPDATE fact_assertions SET valid_until=clock_timestamp() WHERE field_name='region'")
            elif change == 'source_tenant':c.execute("UPDATE fact_assertions SET org_id='other' WHERE field_name='region'")
            elif change == 'source_kind':c.execute("UPDATE fact_assertions SET source_ref=jsonb_set(source_ref,'{kind}','\"AUTHORIZED_REAL\"') WHERE field_name='region'")
    before = snapshot(f)
    with f[0].connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        with pytest.raises(Denied):hs.current_context(f[0], c, token, id)
    assert snapshot(f) == before


def test_field_read_precedes_private_source_queries(preparation_fixture, monkeypatch):
    f = preparation_fixture;p = selected(f);f[1].revoke_field('fixture-a','region','READ')
    def forbidden(*args, **kwargs):raise AssertionError('private source read before field READ')
    monkeypatch.setattr(f[0], 'facts_query', forbidden)
    with pytest.raises(Denied, match='current field grant required'):descriptor(f, p)


@pytest.mark.parametrize('change', ['source','selection','read'])
def test_before_after_guard_rejects_noncooperative_change(preparation_fixture, monkeypatch, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P5');original = hs.summaries
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        with f[1].connect() as c:
            if change == 'source':c.execute("UPDATE fact_assertions SET value='\"SYNTHETIC change\"'::jsonb WHERE field_name='region'")
            elif change == 'selection':c.execute('UPDATE preparations SET fact_clarifications=NULL WHERE id=%s', (UUID(p['preparation_id']),))
            else:c.execute("UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        return result
    monkeypatch.setattr(hs,'summaries',changed)
    old = deepcopy(reader.records)
    with pytest.raises(Denied):reader.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']))
    assert reader.records == old


def mixed_document(f):
    resource_combinations.seed_synthetic(f[1])
    p = bundle_setup(f)
    _, entry = register(f, p, 'region')
    response = f[3].get('/api/preparations/'+p['preparation_id']+'/fact-clarifications', headers=headers(f[2]))
    assert response.status_code == 200
    selected = {row['field_name']:row['id'] for row in response.json()['sources'] if row['source_kind'] == 'USER_ASSERTED_SYNTHETIC'}
    selected['region'] = entry['id']
    response = choose(f, p, selected)
    assert response.status_code == 200, response.text
    return p, entry


def test_mixed_document_source_after_execute_removed_is_readable_without_body(preparation_fixture):
    f = preparation_fixture;p, entry = mixed_document(f);reader = memory_reader(f, p, 'P5')
    f[1].revoke_capability('fixture-a', 'EXECUTE')
    before = snapshot(f)
    result = reader.read(f[0], f[2]['fixture-a'], UUID(p['preparation_id']))
    assert result['read_only'] and result['history'][0]['source_state'] == 'SNAPSHOT_MATCH'
    raw = json.dumps(result)
    for secret in (entry['id'], entry['material']['id'], entry['material']['excerpt'], 'source_snapshot'):
        assert secret not in raw
    assert snapshot(f) == before


@pytest.mark.parametrize('change', ['withdraw','material_version','material_body','material_actor','bundle_receipt','assumption_selection'])
def test_document_source_and_bundle_integrity_denials(preparation_fixture, change):
    f = preparation_fixture;p, entry = mixed_document(f)
    if change == 'withdraw':
        response = bundle_command(f, p, bundle_body(bundle_get(f, p).json(), 'WITHDRAW', source_id=entry['id']))
        assert response.status_code == 200, response.text
    else:
        with f[1].connect() as c:
            if change == 'material_version':c.execute('UPDATE preparation_evidence SET version=version+1 WHERE id=%s', (UUID(entry['material']['id']),))
            elif change == 'material_body':c.execute("UPDATE preparation_evidence SET text=text||'SYNTHETIC tamper' WHERE id=%s", (UUID(entry['material']['id']),))
            elif change == 'material_actor':c.execute("UPDATE preparation_evidence SET actor_id='fixture-b' WHERE id=%s", (UUID(entry['material']['id']),))
            elif change == 'bundle_receipt':c.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND action='FACT_BUNDLE_COMMAND'", (UUID(p['preparation_id']),))
            else:
                # Only the untrusted purpose row is relabelled; no proof repair.
                ledger = deepcopy(parent(f, p)['fact_clarifications'])
                for row in ledger['events'][-1]['source_snapshot']['sources']:
                    if row['id'] == entry['id']:row['source_kind'] = 'ASSUMPTION_SYNTHETIC'
                event = ledger['events'][-1]
                event['source_sha256'] = facts._hash(event['source_snapshot'])
                event['decision_sha256'] = facts._hash({k:v for k,v in event.items() if k != 'decision_sha256'})
                c.execute('UPDATE preparations SET fact_clarifications=%s WHERE id=%s', (Jsonb(ledger), UUID(p['preparation_id'])))
    before = snapshot(f)
    with pytest.raises(Denied):descriptor(f, p)
    assert snapshot(f) == before


def test_timed_field_permission_rechecked_after_supported_lock_wait(preparation_fixture, monkeypatch):
    f = preparation_fixture;p = selected(f);original = facts._field_locks
    def expired(c, owner):
        original(c, owner)
        # Noncooperative fixture admin mutation after the initial permission read.
        with f[1].connect() as other:
            other.execute("UPDATE field_grants SET valid_until=clock_timestamp() WHERE principal_id='fixture-a' AND capability='READ' AND field_name='region'")
    monkeypatch.setattr(facts, '_field_locks', expired)
    with pytest.raises(Denied, match='current field grant required'):descriptor(f, p)


@pytest.mark.parametrize('timed', ['field_read','selected_source'])
def test_final_context_denies_expiry_during_later_catalog_lock_wait(preparation_fixture, monkeypatch, timed):
    from parkweave import catalog_publication as catalog
    f = preparation_fixture
    if timed == 'selected_source':
        resource_combinations.seed_synthetic(f[1]);p = filled(f)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=2)
        assertion(f, 'region', 'SYNTHETIC timed region', end=deadline)
        assertion(f, 'employees', 7);assertion(f, 'service_need', 'SYNTHETIC timed need')
        declare(f, p);confirm(f, p)
    else:p = selected(f)
    reader = memory_reader(f, p, 'P5')
    if timed == 'field_read':
        with f[1].connect() as c:
            deadline = c.execute("UPDATE field_grants SET valid_until=clock_timestamp()+interval '1 second' WHERE principal_id='fixture-a' AND capability='READ' AND field_name='region' RETURNING valid_until").fetchone()['valid_until']
    before = snapshot(f);old_records = deepcopy(reader.records);calls = []
    original = catalog.lock
    def delayed(c, key):
        original(c, key);calls.append(key)
        if len(calls) == 2:
            # Only the final context, after its first fact source check. No
            # source/authority mutation; the real database clock crosses expiry.
            c.execute('SELECT pg_sleep(greatest(0,extract(epoch from (%s::timestamptz-clock_timestamp())))+0.02)', (deadline,))
    monkeypatch.setattr(catalog, 'lock', delayed)
    with pytest.raises(Denied):reader.read(f[0], f[2]['fixture-a'], UUID(p['preparation_id']))
    assert len(calls) == 2 and reader.records == old_records and snapshot(f) == before


def test_legacy_undeclared_case_never_uses_fact_source_contract(preparation_fixture, monkeypatch):
    f = preparation_fixture;resource_combinations.seed_synthetic(f[1]);p = filled(f)
    def forbidden(*args, **kwargs):raise AssertionError('legacy history acquired a new fact dependency')
    monkeypatch.setattr(read, 'source_descriptor', forbidden)
    reader = memory_reader(f, p, 'P4');before = snapshot(f)
    result = reader.read(f[0], f[2]['fixture-a'], UUID(p['preparation_id']), 'synthetic-key')
    assert result['status'] == 'COMMITTED' and result['history'][0]['source_state'] == 'SNAPSHOT_MATCH'
    assert snapshot(f) == before
