"""Current ordinary source provenance, owned fixture only."""
from pathlib import Path
import sys
import pytest
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from conftest import fixture, pg
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_native_run_access import native_fixture, act, body, ledger, snapshot
from parkweave.store import Conflict


@pytest.mark.parametrize('mutation', ['malformed_input', 'input_fingerprint', 'operation_action'])
def test_approval_requires_original_ordinary_case_creation_proof(native_fixture, mutation):
    a = native_fixture
    f, parent, _, before = a
    act(a, 'REQUEST')
    approve = body(a, 'APPROVE')
    with f[1].connect() as c:
        if mutation == 'operation_action':
            c.execute("UPDATE operations SET action='facts.assess' WHERE run_id=%s", (parent['run_id'],))
        else:
            value = c.execute('SELECT input FROM runs WHERE id=%s', (parent['run_id'],)).fetchone()['input']
            if mutation == 'malformed_input':
                value = {}
            else:
                value['goal'] += ' SYNTHETIC changed without original fingerprint'
            c.execute('UPDATE runs SET input=%s WHERE id=%s', (Jsonb(value), parent['run_id']))
    with pytest.raises(Conflict):
        act(a, 'APPROVE', data=approve)
    assert ledger(a)['state'] == 'REQUESTED' and len(ledger(a)['events']) == 1
    assert snapshot(f[1]) == before
