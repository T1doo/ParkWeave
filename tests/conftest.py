import os
import secrets
import uuid
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
        from psycopg.conninfo import conninfo_to_dict
        parsed=conninfo_to_dict(dsn)
        if parsed.get('host') not in ('127.0.0.1','localhost') or parsed.get('dbname')!='postgres' or parsed.get('service') or parsed.get('hostaddr') not in (None,'127.0.0.1','::1'):
            pytest.fail('explicit localhost maintenance postgres DSN required; no remote/production test reset')
        # Explicit installed native service only. Tests create/drop UUID-prefixed
        # fixture databases, never reset the configured parkweave application DB.
        with psycopg.connect(dsn) as c:
            row=c.execute("SELECT rolsuper,rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
            if not any(row):pytest.fail('native test owner needs isolated database creation permission')
            if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='parkweave_app'").fetchone():pytest.fail('parkweave_app must be explicitly prepared')
        class NativeTestServer:
            def get_uri(self):return dsn
        yield NativeTestServer()
        return
    import pgserver  # Linux evidence only; native Windows uses an installed service.
    server = pgserver.get_server(tmp_path_factory.mktemp("parkweave-pg") / 'data', cleanup_mode='delete')
    with psycopg.connect(server.get_uri(), autocommit=True) as c:
        c.execute("CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
    yield server


@pytest.fixture
def fixture(pg):
    db = 'fixture_' + uuid.uuid4().hex
    with psycopg.connect(pg.get_uri(), autocommit=True) as c:
        c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
    owner = Store(make_conninfo(pg.get_uri(), dbname=db))
    owner.migrate()
    tokens = {k: secrets.token_urlsafe(32) for k in ('fixture-a','fixture-b','fixture-c')}
    owner.seed(tokens)
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
    store = Store(make_conninfo(owner.dsn, user='parkweave_app'))
    with TestClient(create_app(store)) as client:
        yield store, owner, tokens, client
    with psycopg.connect(pg.get_uri(), autocommit=True) as c:
        c.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(db)))
