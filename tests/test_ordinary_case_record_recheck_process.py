"""Original P5 HTML on three ordinary API starts and the unchanged TXT format."""
import json
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture,act
from test_ordinary_case_steps import ordinary
from test_ordinary_case_goal_results import ordinary_plan,start,acceptance,results
from test_ordinary_case_goal_record_pack_process import html
from test_service_case_steps import GOALS
from test_case_step_assignments import ok
from ordinary_case_step_support import ordinary_api
from service_release_acceptance_support import authority_snapshot


def test_original_html_p5_close_verify_download_cold_start_and_reopen(ordinary_plan,tmp_path):
    initial,baseline=ordinary_plan
    with ordinary_api(initial,tmp_path/'first-api') as api:
        f=(*initial[:3],api);p=start(f,GOALS);d,r=acceptance(f,p)
        r=ok(act(f,r,'SUBMIT'));ok(act(f,r,'ACKNOWLEDGE'))
        plan_id=ok(results(f,p))['plan_id']
        first=html(f,tmp_path/'closed-html',p,plan_id,'LOCAL_OUTPUTS_VERIFIED',verify=True,goal_count=5,local_action='CLOSE')
        assert first['pack']['results'][4]['actual_output']['local_record_state']=='LOCAL_RECORD_CLOSED'
        assert not first['pack']['case_goal_completed']
    with ordinary_api(initial,tmp_path/'second-api') as api:
        f=(*initial[:3],api)
        cold=html(f,tmp_path/'cold-html',p,plan_id,'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
        assert (tmp_path/'closed-html/download.txt').read_bytes()==(tmp_path/'cold-html/download.txt').read_bytes()
        assert first['pack_sha256']==cold['pack_sha256'] and all(c['method']=='GET' for c in cold['calls'])
    with ordinary_api(initial,tmp_path/'third-api') as api:
        f=(*initial[:3],api)
        reopened=html(f,tmp_path/'reopened-html',p,plan_id,'UNVERIFIED',goal_count=5,local_action='REOPEN')
        old=first['pack']['results'][4]['historical_verification'];current=reopened['pack']['results'][4]
        assert current['historical_verification']['id']==old['id'] and not current['historical_verification']['current']
        assert current['actual_output'] is None and reopened['pack_sha256']!=cold['pack_sha256']
    assert authority_snapshot(initial[1])==baseline
    with initial[1].connect() as c:
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
        assert c.execute('SELECT count(*) n FROM case_local_events').fetchone()['n']==3
        marker=c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload']['case_step_assignment']
        assert marker['valid_until']==d['assignment_valid_until']
    (tmp_path/'process-chain.json').write_text(json.dumps(dict(ordinary_api_processes=3,worker_processes=0,
        closed_pack=first['pack_sha256'],cold_pack=cold['pack_sha256'],reopened_pack=reopened['pack_sha256'],
        deadline=d['assignment_valid_until'],real_browser=False,new_real_authority=False),indent=2)+'\n')
