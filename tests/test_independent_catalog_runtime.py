from uuid import uuid4
import pytest
from parkweave.store import Denied, Conflict
from test_service_capability_catalog_actual import capability_catalog,register,material_instance,snapshot
from test_preparation import create,preparation_fixture
from concurrent.futures import ThreadPoolExecutor
from service_release_acceptance_support import wait_for_pg_blocker
from pathlib import Path
import json
import sqlite3
import threading
from parkweave.template_candidate import TemplateEngine,Command
from parkweave.service_capability_catalog import lock


def test_declared_reviewer_with_revoked_original_review_capability_not_satisfiable(capability_catalog):
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance)
    p,_,_=create(a['f'])
    with a['f'][1].connect() as c:
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
    result=snapshot(a,p)
    assert not result['instances'] and result['unknowns'], 'Revoked reviewer mapping was advertised as a known legal capability'


def test_existing_capability_journal_scope_cannot_be_rewritten_directly(capability_catalog):
    a=capability_catalog;register(a)
    with pytest.raises(Exception):
        with a['f'][1].connect() as c:
            c.execute("UPDATE preparation_catalog SET version=2 WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")


def test_current_original_template_withdrawal_invalidates_live_capability(capability_catalog):
    from parkweave.template_candidate import Command
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance);p,_,_=create(a['f'])
    view=a['engine'].read('template-publisher',a['scope'])
    body=dict(action='WITHDRAW',expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='Original reviewed source withdrawn by current publisher')
    a['engine'].command('template-publisher',a['scope'],uuid4().hex,Command.model_validate(body))
    result=snapshot(a,p)
    assert not result['releases'] and not result['instances'] and result['unknowns']


def test_real_pg_waiting_snapshot_rechecks_winning_reviewer_revocation(capability_catalog):
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance);p,_,_=create(a['f'])
    owner=a['f'][1]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with owner.connect() as blocker:
            a['f'][0].lock_principal(blocker,'prep-specialist-fixture-a',exclusive=True)
            pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            future=pool.submit(snapshot,a,p)
            waiters=wait_for_pg_blocker(owner,pid)
            assert waiters, 'No actual PostgreSQL waiter was observed'
            assert not future.done()
            evidence=Path('.runtime/service-capability-selection-20261014/catalog-role-lock-wait.json')
            evidence.parent.mkdir(parents=True,exist_ok=True)
            evidence.write_text(json.dumps(dict(blocker_pid=pid,waiters=waiters,mechanism='PG_BLOCKING_PIDS_PRINCIPAL_AUTHORITY_LOCK',sqlite_used_for_lock_acceptance=False),indent=2)+'\n')
            blocker.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
        result=future.result(timeout=5)
    assert not result['instances'] and result['unknowns']


def withdrawal(a,engine):
    view=engine.read('template-publisher',a['scope'])
    return Command.model_validate(dict(action='WITHDRAW',expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='Independent second engine original source withdrawal'))


def test_original_sqlite_source_lease_serializes_second_engine_publication_until_pg_commit(capability_catalog):
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance);p,_,_=create(a['f'])
    second=TemplateEngine(a['engine'].config,a['engine'].repository,a['engine'].clock)
    command=withdrawal(a,second)
    started=threading.Event()
    def withdraw():
        started.set()
        return second.command('template-publisher',a['scope'],uuid4().hex,command)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with a['catalog'].owner_connection() as c:
            parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
            assert a['catalog'].snapshot(c,parent)['releases']
            future=pool.submit(withdraw)
            assert started.wait(2)
            with sqlite3.connect(a['engine'].repository.path,timeout=0) as probe:
                with pytest.raises(sqlite3.OperationalError,match='locked'):
                    probe.execute('BEGIN IMMEDIATE')
            assert not future.done()
            evidence=Path('.runtime/service-capability-selection-20261014/source-lease-sqlite-lock.json')
            evidence.write_text(json.dumps(dict(sqlite_probe='BEGIN IMMEDIATE',actual_error='database is locked',source_writer_pending=True,postgres_transaction_pid=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'],lock_acceptance='ORIGINAL_SOURCE_REPOSITORY_GATE_NOT_A_PG_LOCK'),indent=2)+'\n')
        assert future.result(timeout=5)['state']=='WITHDRAWN'
    assert not snapshot(a,p)['releases']


def test_standalone_catalog_get_under_pg_share_avoids_source_writer_inversion(capability_catalog):
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    a['catalog'].bind_instance('park-a',uuid4().hex,instance);p,_,_=create(a['f'])
    acquired_source=threading.Event()
    def source_writer():
        with a['catalog'].owner_connection() as c:
            acquired_source.set()
            lock(c,'park-a',True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with a['f'][1].connect() as c:
            lock(c,'park-a')
            pid=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            future=pool.submit(source_writer)
            assert acquired_source.wait(2)
            waiters=wait_for_pg_blocker(a['f'][1],pid)
            parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
            result=a['catalog'].snapshot(c,parent)
            assert result['releases'] and result['instances'] and not future.done()
            Path('.runtime/service-capability-selection-20261014/source-lease-get-inversion.json').write_text(json.dumps(dict(blocker_pid=pid,waiters=waiters,readonly_get_returned=True,sqlite_writer_gate_held=True),indent=2)+'\n')
        future.result(timeout=5)


def test_original_withdrawal_wins_before_new_leased_source_check(capability_catalog):
    a=capability_catalog;release=register(a)['release']
    second=TemplateEngine(a['engine'].config,a['engine'].repository,a['engine'].clock)
    second.command('template-publisher',a['scope'],uuid4().hex,withdrawal(a,second))
    with a['catalog'].owner_connection() as c:
        records=__import__('parkweave.service_capability_catalog',fromlist=['fold']).fold(__import__('parkweave.service_capability_catalog',fromlist=['proof']).proof(c.execute("SELECT * FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone()))[0]
        with pytest.raises((Denied,Conflict,ValueError)):
            a['catalog']._current_release(records[release['release_id']])


def test_resigned_capability_title_cannot_replace_original_reviewed_definition(capability_catalog):
    from copy import deepcopy
    from parkweave.service_capability_contract import hash_release
    from parkweave.service_capability_catalog import fold,proof
    a=capability_catalog;release=register(a)['release']
    with a['catalog'].owner_connection() as c:
        journal=proof(c.execute("SELECT * FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone())
        record=deepcopy(fold(journal)[0][release['release_id']])
        record['release']['title']='Resigned metadata unsupported by original reviewed definition'
        record['release']['release_sha256']=hash_release(record['release'])
        with pytest.raises(Conflict,match='original trusted reviewed definition'):
            a['catalog']._current_release(record)


def test_invalid_resource_uuid_is_explicit_denial_before_database_cast(capability_catalog):
    a=capability_catalog;release=register(a)['release'];instance=material_instance(release)
    instance['resources']={'primary':'not-a-resource-uuid'}
    with a['catalog'].owner_connection() as c:
        with pytest.raises(Denied,match='exact resource UUID'):
            a['catalog'].mapping_states(c,instance)
        assert c.execute('SELECT 1 AS still_usable').fetchone()['still_usable']==1


def test_second_park_collection_hash_changes_for_new_unselected_portable_service(capability_catalog):
    a=capability_catalog;release=register(a)['release']
    a['catalog'].bind_instance('park-b',uuid4().hex,material_instance(release,'park-b'))
    p,_,_=create(a['f'],user='fixture-c',goal='SYNTHETIC independent hash request')
    first=snapshot(a,p)
    register(a,service='synthetic-local-record-recheck')
    second=snapshot(a,p)
    assert first['revision']==second['revision']
    assert first['instances']==second['instances']
    assert first['sha256']!=second['sha256']
    assert second==snapshot(a,p), 'Collection hash must remain deterministic without mutation'


def test_admitted_catalog_journal_cannot_be_deleted_by_owned_metadata_path(capability_catalog):
    a=capability_catalog;register(a)
    with pytest.raises(Exception,match='immutable|capability|history'):
        with a['f'][1].connect() as c:
            c.execute("DELETE FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")


def test_admitted_catalog_journal_cannot_be_truncated(capability_catalog):
    a=capability_catalog;register(a)
    with pytest.raises(Exception,match='immutable|capability|history'):
        with a['f'][1].connect() as c:
            c.execute('TRUNCATE preparation_catalog CASCADE')


def test_runtime_schema_gate_refuses_column_limited_journal_trigger(capability_catalog):
    from parkweave.service_capability_catalog import IsolatedServiceCapabilityCatalog
    a=capability_catalog
    with a['f'][1].connect() as c:
        c.execute('DROP TRIGGER service_capability_prefix ON preparation_catalog')
        c.execute('CREATE TRIGGER service_capability_prefix BEFORE UPDATE OF service_capability_catalog OR DELETE ON preparation_catalog FOR EACH ROW EXECUTE FUNCTION service_capability_prefix()')
    with pytest.raises(Denied,match='immutable capability schema'):
        IsolatedServiceCapabilityCatalog(a['consumer'],a['f'][1],enabled_for_isolated_tests=True)


def test_second_park_fingerprint_binds_unavailable_portable_journal_revision(capability_catalog):
    a=capability_catalog;material=register(a)['release']
    a['catalog'].bind_instance('park-b',uuid4().hex,material_instance(material,'park-b'))
    a['catalog'].bind_instance('park-a',uuid4().hex,material_instance(material))
    p,_,_=create(a['f'],user='fixture-c',goal='SYNTHETIC unavailable portable collection')
    # Expire original source before changing the metadata collection head: current
    # release IDs are already UNKNOWN on both reads, so hashing only those IDs
    # cannot represent the intervening append-only publication decision.
    a['now'][0]=__import__('datetime').datetime(2100,1,1,tzinfo=__import__('datetime').timezone.utc)
    first=snapshot(a,p)
    with a['f'][1].connect() as c:
        revision=c.execute("SELECT service_capability_catalog->>'revision' AS rev FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone()['rev']
    a['catalog'].withdraw_instance('park-a',uuid4().hex,'park-a-material-instance',int(revision),'SYNTHETIC explicit unavailable source instance withdrawal')
    second=snapshot(a,p)
    assert first['revision']==second['revision']
    assert first['sha256']!=second['sha256']


from test_service_capability_catalog_actual import capability_resource_catalog,coordination_instance
from test_executor_receipts import receipt_fixture


def test_bind_resource_wait_does_not_hold_collection_exclusive(capability_resource_catalog):
    from parkweave import resource_holds as rh
    a=capability_resource_catalog;release=register(a,service='synthetic-resource-coordination')['release'];instance=coordination_instance(release)
    owner=a['f'][1]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with owner.connect() as blocker:
            rh._lock(blocker,rh.RESOURCE_ID)
            pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            future=pool.submit(a['catalog'].bind_instance,'park-a',uuid4().hex,instance)
            waiters=wait_for_pg_blocker(owner,pid)
            assert waiters and not future.done()
            # This is the real business resource-X -> collection-S order.
            # A preexisting writer collection-X would make this time out.
            blocker.execute("SET LOCAL lock_timeout='1000ms'")
            lock(blocker,'park-a')
            Path('.runtime/service-capability-selection-20261014/resource-collection-order.json').write_text(json.dumps(dict(blocker_pid=pid,waiters=waiters,resource_exclusive_held=True,collection_shared_acquired=True,writer_pending=True,sqlite_used_for_pg_acceptance=False),indent=2)+'\n')
        assert future.result(timeout=5)['instance']==instance


@pytest.mark.parametrize('shape',['uppercase','duplicate-alias'])
def test_config_resource_references_cannot_alias_original_uuid_lock_identity(capability_resource_catalog,shape):
    from parkweave.service_capability_contract import hash_instance
    a=capability_resource_catalog;release=register(a,service='synthetic-resource-coordination')['release'];instance=coordination_instance(release)
    if shape=='uppercase':instance['resources']['primary']=instance['resources']['primary'].upper()
    else:instance['resources']['secondary']=instance['resources']['primary'].upper()
    instance['config_sha256']=hash_instance(instance)
    with pytest.raises((Denied,Conflict,ValueError)):
        a['catalog'].bind_instance('park-a',uuid4().hex,instance)
