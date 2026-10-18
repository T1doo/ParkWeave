from pathlib import Path
import hashlib,json,os,subprocess
import psycopg
from psycopg.rows import dict_row
from scripts import material_only_demo as demo
os.umask(0o077)
R=Path.cwd();D=R/'.runtime/material-two-case-demo-20261018'
P=Path('/tmp/parkweave-material-demo-fsnwe42i')
OLD='4e55fa77caa54bf15715189588c9dcd8fd0b890c';NEW='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NEW
old_source=subprocess.check_output(['git','show',OLD+':scripts/material_only_demo.py'])
with demo.locked(P):
 before=(P/'state.json').read_bytes();marker=json.loads(before)
 assert marker['source_commit']==OLD and marker['bootstrap_sha256']==hashlib.sha256(old_source).hexdigest()
 assert marker['src_tree']==demo.source_binding()['src_tree']
 creation=(P/'creation-observation.json').read_bytes()
 with demo.postgres(P) as child:
  with psycopg.connect(demo.dsn(P),row_factory=dict_row) as c:
   identity=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()['system_identifier']
   oid=c.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
   schema=c.execute('SELECT max(version) version FROM schema_version').fetchone()['version']
   auth=demo.authority(c)
   assert identity==marker['system_identifier'] and oid==marker['database_oid'] and schema==32 and auth==marker['authority']
   c.execute('GRANT UPDATE(invalidated_from,invalidated_at) ON controlled_plans TO parkweave_app')
  with psycopg.connect(demo.dsn(P),row_factory=dict_row) as c:
   assert demo.authority(c)==auth
   rights=dict(c.execute("SELECT has_column_privilege('parkweave_app','controlled_plans','invalidated_from','UPDATE') a, has_column_privilege('parkweave_app','controlled_plans','invalidated_at','UPDATE') b, has_table_privilege('parkweave_app','controlled_plans','INSERT') inserts").fetchone())
   assert rights==dict(a=True,b=True,inserts=False)
 assert (P/'state.json').read_bytes()==before and (P/'creation-observation.json').read_bytes()==creation
 with (P/'state-before-sql-lock-fix.json').open('xb') as f:f.write(before)
 marker.update(demo.source_binding());marker['sql_rights']=demo.SQL_RIGHTS
 marker['setup_source_commit']=OLD;marker['explicit_source_revision']='Original empty-table FOR UPDATE requires two SQL column privileges; no authority or source algorithm change.'
 demo.dump(P/'state-revision.pending',marker);os.replace(P/'state-revision.pending',P/'state.json')
result=dict(setup_source_commit=OLD,tested_source_commit=NEW,same_private_database=True,system_identifier=identity,database_oid=oid,schema=32,authority_counts=auth['counts'],authority_unchanged=True,creation_observation_bytes_unchanged=True,old_state_bytes_retained=True,sql_column_update_added=['controlled_plans.invalidated_from','controlled_plans.invalidated_at'],controlled_plan_insert=False,new_setup_or_new_session=False,owned_postgres_stopped=True)
(D/'explicit-sql-source-revision.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
