"""Independent exact SQL closure and actual previous-schema no-migration oracle."""
from pathlib import Path
from uuid import uuid4
import sqlite3,json,os
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture
from test_isolated_execution_preview import setup,body,execute,snapshot
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import isolated_execution_preview as ep,preparation as prep
from parkweave.store import Denied
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-isolated-execution-preview-v2-review')
@pytest.fixture
def actual(preparation_fixture):
 f=preparation_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,)

def test_unknown_selects_denied_before_real_adapter_executes(actual,tmp_path,monkeypatch):
 f=actual;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);command=prep.command;rejected=[];connections=[]
 def inspect(store,token,id,key,data):
  connections.append(store.connection.connection)
  if not rejected:
   for sql in ["SELECT set_config('application_name','SYNTHETIC_UNREGISTERED',true)",'SELECT pg_sleep(0)','SELECT pg_advisory_unlock_all()',' SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s FOR UPDATE']:
    with pytest.raises(Denied):store.connection.execute(sql)
    rejected.append(True)
  return command(store,token,id,key,data)
 monkeypatch.setattr(prep,'command',inspect);r=execute(f,p,b)
 assert r.status_code==201 and len(rejected)==4 and r.json()['result']['artifact']['revision']==5 and all(c.closed for c in connections) and snapshot(f)==before
 (PRIVATE_EVIDENCE/'sql-exact-closure-safe.json').write_text(json.dumps(dict(unregistered_selects_refused=4,known_adapter_chain_still_runs=True,all_private_connections_closed=True,formal_public_values_unchanged=True,actual_http=True,model_calls=0),indent=2)+'\n')

def test_actual_v1_schema_refused_without_migration(actual,tmp_path):
 f=actual;p,e=setup(f,tmp_path);before=snapshot(f);root=tmp_path/'literal-v1-store';root.mkdir(mode=0o700);path=root/'preview.sqlite3'
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
 with sqlite3.connect(path) as db:
  db.executescript("CREATE TABLE meta(value TEXT NOT NULL); CREATE TABLE previews(owner TEXT NOT NULL, preparation TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(owner,request_key)); CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END; CREATE TRIGGER immutable_delete BEFORE DELETE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END;")
  db.execute('INSERT INTO meta VALUES(?)',(prep.canonical(dict(scope=ep.SCOPE,version=1,id=str(uuid4()),database=e.database_identity)),));db.commit()
 data=path.read_bytes();mode=path.stat().st_mode;files=sorted(p.name for p in root.iterdir())
 with pytest.raises(Denied):ep.IsolatedExecutionPreview(f[0],root.resolve(),enabled_for_synthetic_preview=True)
 assert path.read_bytes()==data and path.stat().st_mode==mode and sorted(p.name for p in root.iterdir())==files and snapshot(f)==before
 (PRIVATE_EVIDENCE/'literal-v1-no-migration-safe.json').write_text(json.dumps(dict(actual_v1_schema=True,construct_denied=True,no_file_change=True,no_chmod=True,no_migration=True,formal_public_values_unchanged=True),indent=2)+'\n')
