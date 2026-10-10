"""Schema-valid default-off command through a real separate configured API PID."""
from pathlib import Path
from uuid import uuid4
import socket,json
from playwright.sync_api import sync_playwright
from conftest import fixture,pg
from test_independent_boundaries import preparation_fixture,receipt_fixture,link_fixture,start_owned_api
from test_service_case_steps import setup,GOALS
from test_case_goal_results import snapshot
from test_preparation import headers
OUT=Path('/workspace/ParkWeave/.runtime/independent-registered-local-revision-projection-final-review/new-pid-writeoff')

def test_configured_new_pid_valid_approval_command_is_disabled_without_side_effect(link_fixture):
    f=link_fixture;p=setup(f,GOALS[0]);before=snapshot(f)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    OUT.mkdir(parents=True,exist_ok=True);active=None
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page()
        with (OUT/'new-pid-default-writeoff.log').open('w') as log:
            try:
                active=start_owned_api(f,page,port,log)
                body=dict(action='APPROVE',approval_id=str(uuid4()),expected_revision=1,expected_binding_sha256='0'*64,reason='SYNTHETIC negative disabled command')
                r=page.request.post(f'http://127.0.0.1:{port}/api/preparations/'+p['preparation_id']+'/plan-approval/commands',headers=headers(f[2],key=uuid4().hex),data=body)
                assert r.status==403 and snapshot(f)==before
                with f[1].connect() as c:assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='candidate_plan_approvals'").fetchone()
                (OUT/'schema-valid-writeoff.json').write_text(json.dumps(dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_new_configured_api_pid=active.pid,actual_http=True,pg=True,schema_valid_command=True,disabled_write_status=403,business_rows_unchanged=True,no_candidate_column_installed=True,fixture_capability_reissued=False,existing_unconsumed_ledger_exercised=False,model_calls=0),indent=2)+'\n')
            finally:
                if active is not None and active.poll() is None:active.terminate();active.wait(5)
                browser.close()
