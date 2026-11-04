"""Negative HTTP concurrency contract; the password seam never issues identity."""
from concurrent.futures import ThreadPoolExecutor
import sys
import threading

import pytest
from fastapi.testclient import TestClient

if sys.platform!='linux':pytest.skip('Linux local product only',allow_module_level=True)

from scripts import local_product as product
from parkweave.store import Denied


def test_password_work_is_serialized_before_unlock_and_failed_attempts_stay_bounded(tmp_path,monkeypatch):
    entered=threading.Event();release=threading.Event();calls=[]
    def refuse(cls,path,marker,role,password):
        calls.append(role)
        if len(calls)==1:
            entered.set()
            assert release.wait(5),'bounded test password-work timeout'
        raise Denied('negative password-work seam; no identity issued')
    monkeypatch.setattr(product.LocalSessionVault,'unlock',classmethod(refuse))
    base='http://127.0.0.1:58762'
    app=product.application(tmp_path,{},58762)
    with TestClient(app,base_url=base,client=('127.0.0.1',12345)) as client:
        def attempt():
            return client.post('/api/local/session',headers={'Origin':base},
                json=dict(role='enterprise',password='PUBLIC_NEGATIVE_TEST_PASSWORD'))
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(attempt)
            try:
                assert entered.wait(5)
                assert attempt().status_code==429
                assert calls==['enterprise']
            finally:release.set()
            assert first.result(timeout=5).status_code==403
        for _ in range(5):assert attempt().status_code==403
        assert attempt().status_code==429 and len(calls)==6
