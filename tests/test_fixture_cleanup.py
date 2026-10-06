"""Controlled owned UUID database cleanup failures; no product reset/force drop."""
import psycopg
import pytest
import conftest as cf


def owned_dbs(pg):
    with psycopg.connect(pg.get_uri(),autocommit=True,connect_timeout=2,options='-c lock_timeout=1000 -c statement_timeout=5000') as c:
        return {r[0] for r in c.execute("SELECT datname FROM pg_database WHERE datname ~ '^fixture_[0-9a-f]{32}$'")}


def cleanup_probe(pg,names):
    for name in names:
        with psycopg.connect(pg.get_uri(),autocommit=True,connect_timeout=2,options='-c lock_timeout=1000 -c statement_timeout=5000') as c:
            c.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(name)))


@pytest.mark.parametrize('stage',['migration','client_exit'])
def test_owned_fixture_database_dropped_on_setup_or_client_exit_failure(pg,monkeypatch,stage):
    before=owned_dbs(pg)
    class ExitFailure:
        def __init__(self,*args):pass
        def __enter__(self):return self
        def __exit__(self,*args):raise RuntimeError('SYNTHETIC_CLIENT_EXIT_FAILURE')
    def migrate_failure(self):raise RuntimeError('SYNTHETIC_MIGRATION_FAILURE')
    try:
        if stage=='migration':monkeypatch.setattr(cf.Store,'migrate',migrate_failure)
        else:monkeypatch.setattr(cf,'TestClient',ExitFailure)
        generator=cf.fixture.__wrapped__(pg)
        with pytest.raises(RuntimeError,match='SYNTHETIC_'):
            next(generator)
            if stage=='client_exit':next(generator)
        remaining=owned_dbs(pg)-before
        assert len(remaining)==0,f'{len(remaining)} owned fixture database remains after controlled failure'
    finally:cleanup_probe(pg,owned_dbs(pg)-before)


def test_owned_fixture_cleanup_refusal_preserves_original_setup_failure(pg,monkeypatch):
    before=owned_dbs(pg);attempts=[]
    def migrate_failure(self):raise RuntimeError('SYNTHETIC_PRIMARY_FAILURE')
    def drop_failure(*args):attempts.append(True);raise RuntimeError('SYNTHETIC_CLEANUP_REFUSAL')
    try:
        with monkeypatch.context() as patch:
            patch.setattr(cf.Store,'migrate',migrate_failure);patch.setattr(cf,'drop_owned_fixture_database',drop_failure)
            with pytest.raises(RuntimeError) as failure:next(cf.fixture.__wrapped__(pg))
            assert failure.value.args==('SYNTHETIC_PRIMARY_FAILURE',)
            assert attempts==[True] and any('RuntimeError' in note for note in failure.value.__notes__)
            assert len(owned_dbs(pg)-before)==1
    finally:cleanup_probe(pg,owned_dbs(pg)-before)
