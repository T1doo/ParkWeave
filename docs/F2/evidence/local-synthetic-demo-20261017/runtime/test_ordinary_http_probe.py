"""Additional bounded transport probe; invokes the committed original chain.

Only the test client adapter changes. Application code remains frozen. The child
loads configured_app from its environment and reads the exact existing files/DB.
"""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json,os

import test_local_synthetic_demo as chain
from test_local_synthetic_demo import demo_inputs,preparation_fixture,receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_preparation import headers


def test_original_chain_through_separate_ordinary_factory_process(demo_inputs,tmp_path,monkeypatch):
    f,_,_,_=demo_inputs
    records=[];starts=[];number=0
    @contextmanager
    def actual_client(parent_app):
        nonlocal number
        # The initial parent factory is read-only too. It is deliberately not
        # served: the child constructs its own Store and providers from env.
        number+=1
        with ordinary_demo(f,tmp_path/('http-process-'+str(number))) as api:
            health=api.get('/health').json()
            assert health['process_id']!=os.getpid()
            statuses={path:api.get(path,headers=headers(f[2])).json() for path in
                ('/api/plan-approval/status','/api/run-access/status')}
            assert all(value['enabled'] is False for value in statuses.values())
            starts.append(dict(process_id=health['process_id'],parent_process_id=os.getpid(),isolated_status=statuses))
            def observed(response):
                response.read()
                records.append(dict(process=number,method=response.request.method,path=response.request.url.path,
                    status=response.status_code,response_sha256=sha256(response.content).hexdigest()))
            api.event_hooks['response'].append(observed)
            yield api
    monkeypatch.setattr(chain,'TestClient',actual_client)
    chain.test_ordinary_factory_original_full_chain_and_cold_recovery(demo_inputs,tmp_path)
    assert number==2
    # A real child process must also reject after current PREPARE revocation.
    chain.test_missing_current_authority_refuses_without_writes(demo_inputs,'PREPARE')
    assert number==3
    assert any(r['process']==3 and r['method']=='POST' and r['path'].endswith('/service-selections') and r['status']==403 for r in records)
    assert any(r['method']=='POST' and r['path']=='/api/runs' and r['status']==202 for r in records)
    assert any(r['method']=='POST' and r['path'].endswith('/service-case-plan') and r['status']==201 for r in records)
    assert all(r['method']=='GET' for r in records if r['process']==2)
    output=dict(scope='SEPARATE_ORDINARY_FACTORY_HTTP_FULL_ORIGINAL_CHAIN',source_sha='8ae2892fe56465fbf53e23ae2010258ce7881b47',
        uses_committed_full_chain_assertions=True,current_PREPARE_revocation_HTTP_refused=True,client_adapter_only=True,process_starts=starts,traffic=records,
        real_model_calls=0,exact_run_assignment='one explicit fixture row outside startup',
        zero_preparation_one_click=False,Windows='NOT_RUN',formal_AT='NOT_RUN',real_business='NOT_RUN')
    (tmp_path/'actual-http-full-chain.json').write_text(json.dumps(output,indent=2)+'\n')
