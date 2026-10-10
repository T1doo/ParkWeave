"""Observe real relation locks of catalog schema proof on fresh transactions."""
from pathlib import Path
import json
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture
from test_catalog_approval_coordination import setup
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/schema-locks')

def test_original_catalog_schema_metadata_proof_real_lock_set(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);records=[]
    for name,store in [('owner',f[1]),('application',f[0])]:
        with store.connect() as c:
            before=c.execute("SELECT locktype,mode,granted FROM pg_locks WHERE pid=pg_backend_pid() AND relation='preparation_catalog'::regclass").fetchall()
            protocol._schema(c)
            after=c.execute("SELECT locktype,mode,granted FROM pg_locks WHERE pid=pg_backend_pid() AND relation='preparation_catalog'::regclass").fetchall()
            records.append({'connection_role':name,'before':before,'after_schema_proof':after})
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual-schema-relation-locks.json').write_text(json.dumps(records,indent=2)+'\n')
    assert all(r['before']==[] and r['after_schema_proof']==[] for r in records)
