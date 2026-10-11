"""Independent prior-local-ledger projection checks, owned PG only."""
import pytest
from psycopg.types.json import Jsonb
from test_independent_probes import pg,fixture,preparation_fixture,receipt_fixture,link_fixture,observe
from test_case_lifecycle import built,read,act
import test_case_cancellation_reconciliation as new
import test_case_cancellation as old

@pytest.mark.parametrize('damage',['state','verified_snapshot','verified_sha'])
def test_request_requires_exact_latest_preexisting_local_projection(link_fixture,damage):
 f=link_fixture;p,g,d,row=built(f)
 r=act(f,p,read(f,p).json(),'REVALIDATE');assert r.status_code==200,r.text
 with f[1].connect() as c:
  if damage=='state':
   c.execute("UPDATE case_local_lifecycles SET state='REOPENED',verified_snapshot=NULL,verified_sha256=NULL")
  elif damage=='verified_snapshot':
   c.execute('UPDATE case_local_lifecycles SET verified_snapshot=%s',(Jsonb({'unproved':'SYNTHETIC projection replacement'}),))
  else:c.execute("UPDATE case_local_lifecycles SET verified_sha256=repeat('0',64)")
 before=old.snapshot(f);preview=new.get(f,p);assert preview.status_code==200,preview.text
 r=new.post(f,p)
 observe('prefix-projection-'+damage,{'preview_blockers':preview.json()['blockers'],'can_request':preview.json()['can_request'],'post_status':r.status_code,'post_result':r.json()})
 assert not preview.json()['can_request'] and r.status_code==409
 assert old.snapshot(f)==before
