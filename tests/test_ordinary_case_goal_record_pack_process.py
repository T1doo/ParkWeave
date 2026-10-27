"""Normal configured_app processes, full original HTML, durable record pack."""
import json,subprocess
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture,act
from test_ordinary_case_steps import ordinary
from test_ordinary_case_goal_results import ordinary_plan,start,acceptance,results
from test_case_step_assignments import ok
from ordinary_case_step_support import ordinary_api
from service_release_acceptance_support import authority_snapshot


def html(f,directory,p,plan_id,state,verify=False,**extra):
    directory.mkdir(parents=True,exist_ok=True)
    config=dict(base=str(f[3].base_url).rstrip('/'),preparation_id=p['preparation_id'],plan_id=plan_id,
        state=state,verify=verify,tokens=dict(owner=f[2]['fixture-a'],executor=f[2]['executor-a']),**extra)
    with (directory/'html.stdout').open('w') as out,(directory/'html.stderr').open('w') as err:
        result=subprocess.run(['node','tests/ordinary_case_goal_record_pack_html.js'],input=json.dumps(config)+'\n',
            text=True,stdout=out,stderr=err,timeout=60)
    assert result.returncode==0,(directory/'html.stderr').read_text()
    row=json.loads((directory/'html.stdout').read_text().splitlines()[-1])
    (directory/'download.txt').write_text(row.pop('text'))
    (directory/'summary.json').write_text(json.dumps(row,indent=2)+'\n')
    return row


def test_normal_process_original_html_verify_download_cold_read_and_revoked_source(ordinary_plan,tmp_path):
    initial,baseline=ordinary_plan
    with ordinary_api(initial,tmp_path/'first-api') as api:
        f=(*initial[:3],api);p=start(f);d,r=acceptance(f,p)
        r=ok(act(f,r,'SUBMIT'));r=ok(act(f,r,'ACKNOWLEDGE'))
        pending=ok(results(f,p));plan_id=pending['plan_id']
        assert pending['results'][2]['state']=='AWAITING_OWNER_VERIFICATION'
        first=html(f,tmp_path/'first-html',p,plan_id,'LOCAL_OUTPUTS_VERIFIED',verify=True)
    with ordinary_api(initial,tmp_path/'second-api') as api:
        f=(*initial[:3],api);cold=html(f,tmp_path/'cold-html',p,plan_id,'LOCAL_OUTPUTS_VERIFIED')
        assert first['pack_sha256']==cold['pack_sha256']
        assert all(c['method']=='GET' for c in cold['calls'])
    assert authority_snapshot(initial[1])==baseline
    # Owned synthetic negative change only; never a real Grant management step.
    with initial[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    with ordinary_api(initial,tmp_path/'third-api') as api:
        f=(*initial[:3],api);revoked=html(f,tmp_path/'revoked-html',p,plan_id,'UNVERIFIED')
        for row in revoked['pack']['results'][2:]:
            assert row['actual_output'] is None and not row['historical_verification']['current']
        assert all(c['method']=='GET' for c in revoked['calls'])
    (tmp_path/'process-chain.json').write_text(json.dumps(dict(ordinary_api_processes=3,first_pack=first['pack_sha256'],
        cold_pack=cold['pack_sha256'],revoked_pack=revoked['pack_sha256'],deadline=d['assignment_valid_until'],
        real_browser=False,new_real_authority=False),indent=2)+'\n')
