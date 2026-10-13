import threading,time
from concurrent.futures import ThreadPoolExecutor
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture,create
from parkweave import case_worklist
from parkweave.store import Denied,Store
from psycopg.conninfo import make_conninfo
@pytest.mark.parametrize('level',["repeatable read","serializable"])
@pytest.mark.parametrize('changed',["identity","PREPARE"])
def test_nondefault_wait_rechecks_revocation(preparation_fixture,level,changed):
 f=preparation_fixture;create(f);store=Store(make_conninfo(f[0].dsn,options="-c default_transaction_isolation="+level.replace(' ','\\ ')+" -c application_name=worklist_independent_wait"))
 entered=threading.Event();original=store.lock_principal
 def observed(c,id,*a,**kw):
  assert c.execute('SHOW transaction_isolation').fetchone()['transaction_isolation']=='read committed'
  entered.set();return original(c,id,*a,**kw)
 store.lock_principal=observed
 with ThreadPoolExecutor(max_workers=1) as pool:
  with f[1].connect() as c:
   f[1].lock_principal(c,'fixture-a',exclusive=True)
   future=pool.submit(case_worklist.read,store,f[2]['fixture-a']);assert entered.wait(10)
   until=time.monotonic()+10;waiting=False
   while time.monotonic()<until:
    rows=c.execute("SELECT wait_event_type FROM pg_stat_activity WHERE application_name='worklist_independent_wait'").fetchall()
    if any(r['wait_event_type']=='Lock' for r in rows):waiting=True;break
    time.sleep(.02)
   assert waiting,'actual PG lock wait required'
   if changed=='identity':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
   else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
  with pytest.raises(Denied):future.result(timeout=10)
