"""Real administrator catalog changes against isolated PG confirmation requests.

The insert barrier is an ordinary invoker trigger owned by the synthetic test
database owner. It pauses the actual application INSERT; it neither replaces a
product comparison nor supplies a catalog lock or a new application privilege.
"""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from uuid import UUID

import pytest
import psycopg

from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_resource_substitution_confirm import prepare, compared, confirm, body, authority_records
from test_resource_plan_binding import complete_digest


def change_catalog(owner,parent,revision,isolation=None):
    # Separate connection and committed direct administrator DML, without any
    # product advisory lock convention or application role grant.
    with owner.connect() as c:
        if isolation is not None:
            c.isolation_level=psycopg.IsolationLevel[isolation]
        c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}',to_jsonb(%s::integer)) WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",
                  (revision,UUID(parent['preparation_id'])))


def insert_barrier(owner,deferred=False):
    with owner.connect() as c:
        c.execute("""CREATE FUNCTION synthetic_catalog_insert_barrier() RETURNS trigger
          LANGUAGE plpgsql SECURITY INVOKER AS $$
          BEGIN
            IF NEW.snapshot ? 'binding_impact' THEN
              PERFORM pg_advisory_xact_lock(95095,1);
            END IF;
            RETURN NEW;
          END$$""")
        if deferred:
            c.execute("""CREATE CONSTRAINT TRIGGER synthetic_catalog_insert_barrier
              AFTER INSERT ON case_resource_links DEFERRABLE INITIALLY DEFERRED
              FOR EACH ROW EXECUTE FUNCTION synthetic_catalog_insert_barrier()""")
        else:
            c.execute("""CREATE TRIGGER synthetic_catalog_insert_barrier
              BEFORE INSERT ON case_resource_links FOR EACH ROW
              EXECUTE FUNCTION synthetic_catalog_insert_barrier()""")


def await_actual_phase(owner,future,blocker_pid,phase='INSERT INTO case_resource_links'):
    deadline=monotonic()+5
    with owner.connect() as c:
        while monotonic()<deadline:
            c.execute('SELECT pg_stat_clear_snapshot()')
            rows=c.execute("""SELECT pid FROM pg_stat_activity
              WHERE datname=current_database() AND usename='parkweave_app'
              AND wait_event_type='Lock' AND wait_event='advisory'
              AND query LIKE %s
              AND %s=ANY(pg_blocking_pids(pid))""",(phase+'%',blocker_pid)).fetchall()
            if rows:return rows[0]['pid']
            if future.done():
                response=future.result()
                pytest.fail('Confirmation did not reach the actual '+phase+' barrier: '+response.text)
            sleep(0.01)
    pytest.fail('Actual application '+phase+' did not reach the database barrier')


def test_admin_committed_catalog_change_visible_before_confirm_is_rejected(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    authority=authority_records(f)
    change_catalog(f[1],p,2)
    before=complete_digest(f)
    response=confirm(f,p,body(candidate,row))
    assert response.status_code==409,response.text
    assert complete_digest(f)==before
    assert authority_records(f)==authority


def test_admin_commits_after_last_comparison_before_insert_cannot_commit_stale_link(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    authority=authority_records(f)
    insert_barrier(f[1])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as barrier:
            blocker_pid=barrier.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            barrier.execute('SELECT pg_advisory_xact_lock(95095,1)')
            future=pool.submit(confirm,f,p,body(candidate,row))
            app_pid=await_actual_phase(f[1],future,blocker_pid)
            assert app_pid!=blocker_pid
            # This commit precedes completion of the actual application INSERT.
            change_catalog(f[1],p,2)
        response=future.result(timeout=5)
    assert authority_records(f)==authority
    assert response.status_code==409,(
        'An independently committed catalog source changed after the last CAS '
        'read but before the application INSERT; the confirmation still committed: '+response.text)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==1
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==1


@pytest.mark.parametrize('app_isolation,admin_isolation',[
    ('READ_COMMITTED','READ_COMMITTED'),
    ('REPEATABLE_READ','READ_COMMITTED'),
    ('SERIALIZABLE','READ_COMMITTED'),
    ('SERIALIZABLE','SERIALIZABLE')])
def test_admin_commit_after_last_response_read_documents_remaining_commit_window(
        link_fixture,monkeypatch,app_isolation,admin_isolation):
    """Evidence of a limitation: last response read does not lock catalog DML.

This intentionally expects the current residual behavior, rather than treating
READ COMMITTED or an uncoordinated advisory lock as a guarantee of atomicity.
"""
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    authority=authority_records(f)
    insert_barrier(f[1],deferred=True)
    original_connect=f[0].connect
    def actual_connection():
        c=original_connect()
        c.isolation_level=psycopg.IsolationLevel[app_isolation]
        return c
    monkeypatch.setattr(f[0],'connect',actual_connection)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as barrier:
            blocker_pid=barrier.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            barrier.execute('SELECT pg_advisory_xact_lock(95095,1)')
            future=pool.submit(confirm,f,p,body(candidate,row))
            assert await_actual_phase(f[1],future,blocker_pid,phase='COMMIT')!=blocker_pid
            # The actual COMMIT has started, so all response source reads finished.
            change_catalog(f[1],p,2,isolation=admin_isolation)
        response=future.result(timeout=5)
    assert response.status_code==201,response.text
    committed=response.json()
    assert committed['current']['source_status']=='CURRENT'
    event=committed['event']
    assert event['snapshot']['binding_impact']['comparison_sha256']==row['comparison']['sha256']
    assert event['snapshot']['binding_impact']['before']['source_snapshots']['P1']['service_catalog']['source']==row['checkpoints']['P1']['current_snapshot']['service_catalog']['source']
    current=compared(f,p,candidate)
    assert current['history'][1]['source_status']=='NEEDS_RECHECK'
    assert 'RESOURCE_BINDING_SOURCE_CHANGED' in current['history'][1]['issues']
    assert current['history'][1]['record']==event
    assert authority_records(f)==authority
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==2
