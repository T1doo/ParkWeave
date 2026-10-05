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
        c.execute('GRANT SELECT,INSERT,UPDATE ON runs,operations,cases,outbox,run_projection TO parkweave_app')
    store = Store(make_conninfo(owner.dsn, user='parkweave_app'))
    with TestClient(create_app(store)) as client:
        yield store, owner, tokens, client
    with psycopg.connect(pg.get_uri(), autocommit=True) as c:
        c.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(db)))
