from pathlib import Path
import hashlib,json,os,subprocess
import psycopg
from psycopg.rows import dict_row
from scripts import material_only_demo as demo
os.umask(0o077)
R=Path.cwd();D=R/'.runtime/material-two-case-demo-20261018';P=Path('/tmp/parkweave-material-demo-fsnwe42i')
OLD='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765';NEW='24f6db12490b7ba7f01099d311af97e926eeddd0'
old_source=subprocess.check_output(['git','show',OLD+':scripts/material_only_demo.py'])
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NEW
with demo.locked(P):
 before=(P/'state.json').read_bytes();marker=json.loads(before)
 assert marker['source_commit']==OLD and marker['bootstrap_sha256']==hashlib.sha256(old_source).hexdigest()
 assert marker['src_tree']==demo.source_binding()['src_tree'] and not(P/'stop-unconfirmed').exists()
 creation=(P/'creation-observation.json').read_bytes();sessions=(P/'sessions.json').read_bytes()
 with demo.postgres(P):
  with psycopg.connect(demo.dsn(P),row_factory=dict_row) as c:
   c.execute('SET TRANSACTION READ ONLY')
   assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()['system_identifier']==marker['system_identifier']
   assert c.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']==marker['database_oid']
   assert c.execute('SELECT max(version) n FROM schema_version').fetchone()['n']==32
   assert demo.authority(c)==marker['authority']
   counts={n:c.execute('SELECT count(*) n FROM '+n).fetchone()['n'] for n in ['runs','cases','preparations','preparation_evidence','preparation_events']}
   assert counts==dict(runs=2,cases=2,preparations=2,preparation_evidence=4,preparation_events=10)
 assert (P/'state.json').read_bytes()==before and (P/'creation-observation.json').read_bytes()==creation and(P/'sessions.json').read_bytes()==sessions
 with(P/'state-before-restart-source-fix.json').open('xb') as f:f.write(before)
 marker.update(demo.source_binding());marker['explicit_restart_revision']='SO_REUSEADDR only; private error capture begins before port probe. No authority/SQL/source algorithm change.'
 demo.dump(P/'state-revision.pending',marker);os.replace(P/'state-revision.pending',P/'state.json')
r=dict(previous_source_commit=OLD,new_source_commit=NEW,reason='Safe same-port listener precheck after shutdown',authority_unchanged=True,business_rows_unchanged=counts,sql_permissions_unchanged=True,creation_observation_bytes_unchanged=True,sessions_bytes_unchanged=True,no_new_setup=True,no_issued_receipt_reconstructed=True,old_state_bytes_retained=True)
(D/'restart-explicit-source-revision.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
