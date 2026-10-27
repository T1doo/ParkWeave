"""Typed structure proof must reject Python-equal JSON type substitutions."""
from copy import deepcopy
import pytest
from psycopg.types.json import Jsonb

from test_template_structure_independent import complete_declared, admit, apply, stored, all_pg_rows, recovery, GOALS, private_fixture_sessions
from test_template_upgrade import upgrade_case, publication, plan_read
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture


@pytest.mark.parametrize('forged_version',[True,1.0],ids=['boolean_true','float_one'])
def test_stored_structure_proof_type_substitution_is_refused(upgrade_case,forged_version):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic typed structure proof')
    view,data=admit(u,row,target)
    assert view['application']['eligible'],view['application']
    response=apply(u,row,data,'structural-type-proof')
    assert response.status_code==200,response.text
    saved=deepcopy(stored(u,row))
    proof=saved['events'][-1]['template_upgrade']['structure_change']
    assert type(proof['version']) is int and proof['version']==1
    proof['version']=forged_version
    # This is the actual independently owned PG row, not an in-memory checker.
    with u['f'][1].connect() as c:
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(saved),row['preparation_id']))
    before=all_pg_rows(u)
    response=recovery(u,row,'structural-type-proof')
    assert response.status_code==409,response.text
    response=plan_read(u['f'],p)
    assert response.status_code==409,response.text
    assert all_pg_rows(u)==before, 'rejected historical read changed stored facts or repaired forged proof'
