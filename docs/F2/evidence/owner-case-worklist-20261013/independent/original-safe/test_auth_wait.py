import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture,create
from parkweave import case_worklist
from parkweave.store import Denied

def test_revoked_during_authorization_lock_wait(preparation_fixture):
    f=preparation_fixture;create(f)
    entered=threading.Event();original=f[0].lock_principal
    def observed(c,id,*a,**kw):
        entered.set();return original(c,id,*a,**kw)
    f[0].lock_principal=observed
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            future=pool.submit(case_worklist.read,f[0],f[2]['fixture-a'])
            assert entered.wait(10)
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        try:
            with pytest.raises(Denied):future.result(timeout=10)
        finally:f[0].lock_principal=original

from test_executor_receipts import receipt_fixture, create as create_receipt

def test_legacy_receipt_broken_binding_is_unknown(receipt_fixture):
    f=receipt_fixture;r,p,_=create_receipt(f);assert r.status_code==201
    row=case_worklist.read(f[0],f[2]['fixture-a'])['items'][0]
    assert row['attention']=='WAITING_RECEIPT'
    with f[1].connect() as c:
        c.execute('UPDATE service_receipt_steps SET owner_id=%s WHERE id=%s',('fixture-b',r.json()['step']['id']))
    row=case_worklist.read(f[0],f[2]['fixture-a'])['items'][0]
    assert row['attention']=='UNKNOWN' and row['open_target']=='run' and row['receipt_step_id'] is None
