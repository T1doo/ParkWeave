"""Retained dedicated journal must reject tampered schema before repair."""
import sqlite3
import pytest
from parkweave.synthetic_rule_readiness import SimulationJournal
from parkweave.store import Conflict

@pytest.mark.parametrize('change',['missing-trigger','forged-trigger'])
def test_retained_journal_schema_tamper_is_refused_without_ddl(tmp_path,change):
    path=tmp_path/'retained.synthetic-readiness.sqlite3';SimulationJournal(path)
    with sqlite3.connect(path) as c:
        c.execute('DROP TRIGGER simulation_immutable_delete')
        if change=='forged-trigger':c.execute('CREATE TRIGGER simulation_immutable_delete BEFORE DELETE ON simulation_assessments BEGIN SELECT 1; END')
    before=path.read_bytes()
    with pytest.raises(Conflict):SimulationJournal(path)
    assert path.read_bytes()==before
