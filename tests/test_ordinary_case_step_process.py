"""Three ordinary API processes and original worker; complete original HTML."""
from pathlib import Path
from uuid import uuid4
import json,subprocess
from test_preparation import preparation_fixture,headers,add,command as prep_command
from test_executor_receipts import receipt_fixture
from test_case_step_assignments import ok,REVIEWER
from test_case_step_assignments import prepared
from test_service_dispatches import offer
from service_release_acceptance_support import authority_snapshot
from ordinary_case_step_support import ordinary_api,worker_once

def html(f,directory,phase,p,**extra):
    directory.mkdir(parents=True,exist_ok=True)
    executor_id=extra.pop('executor_id','executor-a')
    config=dict(base=str(f[3].base_url).rstrip('/'),preparation_id=p['preparation_id'],phase=phase,
        tokens=dict(owner=f[2]['fixture-a'],reviewer=f[2][REVIEWER],executor=f[2][executor_id]),**extra)
    with (directory/'html.stdout').open('w') as out,(directory/'html.stderr').open('w') as err:
        result=subprocess.run(['node','tests/ordinary_case_step_real_html.js'],input=json.dumps(config)+'\n',
            text=True,stdout=out,stderr=err,timeout=60)
    assert result.returncode==0,(directory/'html.stderr').read_text()
    rows=[json.loads(s) for s in (directory/'html.stdout').read_text().splitlines()]
    return rows[-1]

def test_original_html_and_worker_restarts_retain_uuid_deadline_and_read_receipt(receipt_fixture,tmp_path):
    initial=receipt_fixture;baseline=authority_snapshot(initial[1])
    with ordinary_api(initial,tmp_path/'first') as api:
        f=(*initial[:3],api)
        run=ok(api.post('/api/runs',headers=headers(f[2],key=uuid4().hex),json=dict(goal='SYNTHETIC ordinary restart case')),202)
        worker_once(f,tmp_path/'case-worker')
        p=ok(api.post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=dict(run_id=run['run_id'],
            service_id='synthetic-material-preparation',service_version=1,reviewer_id=REVIEWER)),201)
        p=ok(add(f,p,text='SYNTHETIC ordinary need'));p=ok(add(f,p,'material_outline','SYNTHETIC ordinary outline'))
        p=ok(prep_command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC independent review'))
        p=ok(prep_command(f,p,'CONFIRM',reason='SYNTHETIC owner confirms'))
        offered=html(f,tmp_path/'offer-html','OFFER',p)
    # Fresh worker and API see the persisted first offer, never a shared object.
    worker_once(initial,tmp_path/'delivery-worker')
    with ordinary_api(initial,tmp_path/'second') as api:
        f=(*initial[:3],api);done=html(f,tmp_path/'execute-html','EXECUTE',p,deadline=offered['deadline'])
    worker_once(initial,tmp_path/'acceptance-worker')
    with ordinary_api(initial,tmp_path/'third') as api:
        f=(*initial[:3],api);cold=html(f,tmp_path/'cold-html','READ',p,deadline=offered['deadline'],step=done['step'])
    assert offered['deadline']==done['deadline']==cold['deadline']
    assert authority_snapshot(initial[1])==baseline
    with initial[1].connect() as c:
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n']==1
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==1
    (tmp_path/'chain-proof.json').write_text(json.dumps(dict(ordinary_api_processes=3,worker_processes=3,
        first_offer=offered,executed=done,cold=cold,authority_unchanged=True,real_browser=False),indent=2)+'\n')

def test_original_ordinary_decline_clears_terminal_view_without_forbidden_get(receipt_fixture,tmp_path):
    initial=receipt_fixture
    with ordinary_api(initial,tmp_path/'ordinary-decline') as api:
        f=(*initial[:3],api);p=prepared(f);ok(offer(f,p)[0],201)
        result=html(f,tmp_path/'decline-html','DECLINE',p)
        assert result['terminal'] and result['calls'][-1]['body']['action']=='DECLINE'
