import os
import secrets
import uuid
import re
import pytest
import psycopg
from psycopg.conninfo import make_conninfo
from fastapi.testclient import TestClient
from parkweave.store import Store
from parkweave.api import create_app


@pytest.fixture(scope="session")
def pg(tmp_path_factory):
    if os.name=='nt':
        dsn=os.environ.get('PARKWEAVE_TEST_OWNER_DSN')
        if not dsn:pytest.skip('NOT_RUN: explicit native Windows test-owner DSN required')
        pytest.fail('NOT_RUN: installed native PostgreSQL has no reviewed migration-025 creation receipt adapter; blocked before database creation')
    import pgserver  # Linux evidence only; native Windows uses an installed service.
    data=tmp_path_factory.mktemp("parkweave-pg") / 'data'
    server = pgserver.get_server(data, cleanup_mode='delete')
    from parkweave.case_fact_clarifications import capture_fixture_cluster
    server._case_fact_fixture_cluster=capture_fixture_cluster(server.get_uri(),data.resolve())
    with psycopg.connect(server.get_uri(), autocommit=True) as c:
        c.execute("CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
    yield server


def drop_owned_fixture_database(pg,db):
    """Only this fixture's successfully created UUID database, bounded ordinary DROP."""
    if not re.fullmatch(r'fixture_[0-9a-f]{32}',db):raise ValueError('owned fixture UUID database required')
    from psycopg.conninfo import conninfo_to_dict
    options=conninfo_to_dict(pg.get_uri()).get('options','')
    dsn=make_conninfo(pg.get_uri(),connect_timeout=2,options=options+' -c lock_timeout=1000 -c statement_timeout=5000')
    with psycopg.connect(dsn,autocommit=True) as c:
        c.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(db)))


def fixture_progress(request,stage):
    # Existing optional pytest plugin only; no credentials or SQL enter the record.
    if request is None:return
    try:
        plugin=request.config.pluginmanager.get_plugin('scripts.windows_ci.regression_plugin')
        if plugin is not None:plugin.fixture_stage(request,stage)
    except Exception:pass


@pytest.fixture
def fixture(pg,request):
    db = 'fixture_' + uuid.uuid4().hex
    created=False
    try:
        fixture_progress(request,'CREATE_DB')
        with psycopg.connect(pg.get_uri(), autocommit=True) as c:
            c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
            created=True
        owner = Store(make_conninfo(pg.get_uri(), dbname=db))
        with owner.connect() as c:
            owner._case_fact_fixture_receipt=pg._case_fact_fixture_cluster.record_created_database(c)
        fixture_progress(request,'MIGRATE');owner.migrate()
        tokens = {k: secrets.token_urlsafe(32) for k in ('fixture-a','fixture-b','fixture-c')}
        fixture_progress(request,'SEED');owner.seed(tokens)
        fixture_progress(request,'GRANTS')
        with owner.connect() as c:
            c.execute('GRANT USAGE ON SCHEMA public TO parkweave_app')
            c.execute('GRANT SELECT ON schema_version,principals,field_grants TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON fact_assertions TO parkweave_app')
            c.execute('GRANT SELECT ON capability_grants,run_assignments,file_resources TO parkweave_app')
            c.execute('GRANT SELECT,INSERT,UPDATE ON deliveries TO parkweave_app')
            c.execute('GRANT SELECT ON action_grants TO parkweave_app')
            c.execute('GRANT INSERT ON authorization_audit TO parkweave_app')
            c.execute('GRANT SELECT,INSERT,UPDATE ON runs,operations,cases,outbox,run_projection,model_steps TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON model_plans TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON fact_reviews,fact_followups TO parkweave_app')
            c.execute('GRANT SELECT ON preparation_catalog,preparation_grants TO parkweave_app')
            c.execute('GRANT SELECT,INSERT,UPDATE ON preparations TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON preparation_evidence,preparation_events TO parkweave_app')
            c.execute('GRANT SELECT ON synthetic_resources,synthetic_resource_grants TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON synthetic_resource_holds,synthetic_resource_receipts TO parkweave_app')
            c.execute('GRANT UPDATE(state) ON synthetic_resource_holds TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON synthetic_resource_combinations,synthetic_resource_combination_members,synthetic_resource_combination_receipts TO parkweave_app')
            c.execute('GRANT UPDATE(state) ON synthetic_resource_combinations TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON service_receipt_steps,service_step_receipts,service_receipt_events TO parkweave_app')
            c.execute('GRANT UPDATE(state,revision,current_receipt_id) ON service_receipt_steps TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON resource_case_claims,case_resource_links TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON service_dispatches,service_dispatch_offers,service_dispatch_events TO parkweave_app')
            c.execute('GRANT UPDATE(revision,current_offer_id) ON service_dispatches TO parkweave_app')
            c.execute('GRANT UPDATE(state,receipt_step_id) ON service_dispatch_offers TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON case_local_lifecycles,case_local_events TO parkweave_app')
            c.execute('GRANT UPDATE(revision,cycle,state,verified_snapshot,verified_sha256) ON case_local_lifecycles TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON dispatch_notice_outbox,dispatch_notices TO parkweave_app')
            c.execute('GRANT UPDATE(state,consumed_at) ON dispatch_notice_outbox TO parkweave_app')
            c.execute('GRANT UPDATE(seen_at,read_at) ON dispatch_notices TO parkweave_app')
            c.execute('GRANT SELECT,INSERT ON controlled_plans,controlled_plan_events TO parkweave_app')
            c.execute('GRANT UPDATE(revision,checked,invalidated_from,invalidated_at) ON controlled_plans TO parkweave_app')
        store = Store(make_conninfo(owner.dsn, user='parkweave_app'))
        fixture_progress(request,'CLIENT')
        with TestClient(create_app(store)) as client:
            yield store, owner, tokens, client
            fixture_progress(request,'CLIENT_EXIT')
    except BaseException as primary:
        if created:
            try:
                fixture_progress(request,'DROP_DB');drop_owned_fixture_database(pg,db);fixture_progress(request,'DONE')
            except Exception as cleanup:
                primary.add_note('Owned fixture cleanup failed: '+type(cleanup).__name__)
        raise
    else:
        if created:
            fixture_progress(request,'DROP_DB');drop_owned_fixture_database(pg,db);fixture_progress(request,'DONE')
