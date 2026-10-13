import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from conftest import pg,fixture
"""Original page business entries, owned PG/ASGI, existing isolated access bridge."""
import json,selectors,subprocess
from pathlib import Path

from parkweave.isolated_run_access import IsolatedRunAccessBridge
from test_case_resources import link_fixture
from test_preparation import headers,preparation_fixture
from test_executor_receipts import receipt_fixture
from test_isolated_run_access import permission_snapshot


def test_two_new_inputs_same_case_full_original_page_chain_and_lost_response(link_fixture,tmp_path):
    f=link_fixture;permissions=permission_snapshot(f[1])
    bridge=IsolatedRunAccessBridge(f[1],f[1]._case_fact_fixture_receipt,
        tmp_path/'original-page.run-access.candidate.sqlite3',approver_ids={'prep-specialist-fixture-a'},enabled_for_isolated_tests=True)
    bridge.attach_store(f[0]);assert permission_snapshot(f[1])==permissions
    proc=subprocess.Popen(['node',str(Path('tests/full_owned_lifecycle.js')),'full_owned_lifecycle'],
        cwd=Path.cwd(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];lost=False;summary=None
    try:
        while True:
            assert selector.select(timeout=15),'Original chain bridge made no progress within15 seconds'
            line=proc.stdout.readline()
            if not line:break
            message=json.loads(line)
            if 'request' not in message:summary=message;break
            r=message['request'];o=r['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None
            actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_')
            response=f[3].request(method,r['path'],headers=headers(f[2],actor,key=o['headers'].get('Idempotency-Key')),json=body)
            requests.append({'method':method,'path':r['path'],'status':response.status_code,'actor':actor,'action':body.get('action') if body else None})
            assert response.status_code<400,(method,r['path'],response.status_code,response.json())
            if method=='POST' and r['path']=='/api/runs':f[0].finish(f[0].claim('original-page-full-chain'))
            drop=not lost and method=='POST' and body and body.get('action')=='ADD_EVIDENCE'
            if drop:lost=True
            proc.stdin.write((json.dumps({'status':response.status_code,'body':response.json(),'lost':bool(drop)})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read()
        assert summary and summary['checks']>=60 and len(summary['milestones'])==2 and lost
        assert len([r for r in requests if r['method']=='POST' and r['path']=='/api/runs'])==2
        assert len([r for r in requests if r['action']=='ADD_EVIDENCE'])==4
        assert len([r for r in requests if r['method']=='GET' and r['path'].endswith('/command-recovery')])==1
        assert permission_snapshot(f[1])==permissions
        with f[1].connect() as c:
            for case in summary['milestones']:
                p=c.execute('SELECT case_id,run_id FROM preparations WHERE id=%s',(case['preparation'],)).fetchone()
                assert str(p['case_id'])==case['case'] and str(p['run_id'])==case['run']
                step=c.execute('SELECT case_id,run_id,preparation_id,state FROM service_receipt_steps WHERE id=%s',(case['receipt'],)).fetchone()
                assert str(step['case_id'])==case['case'] and str(step['run_id'])==case['run'] and str(step['preparation_id'])==case['preparation']
                assert step['state']=='LOCAL_ACKNOWLEDGED'
                assert c.execute('SELECT count(*) n FROM preparation_events WHERE preparation_id=%s AND action=%s',(case['preparation'],'ADD_EVIDENCE')).fetchone()['n']==2
                assert c.execute('SELECT count(*) n FROM case_local_events WHERE preparation_id=%s',(case['preparation'],)).fetchone()['n']==3
                assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(case['combination'],)).fetchone()['state']=='CONFIRMED'
                assert c.execute('SELECT count(*) n FROM synthetic_resource_combination_members m JOIN synthetic_resource_holds h ON h.id=m.hold_id WHERE m.combination_id=%s AND h.state=%s',(case['combination'],'CONFIRMED')).fetchone()['n']==2
        out=Path('.runtime/full-owned-lifecycle-20261013/independent');out.mkdir(parents=True,exist_ok=True)
        (out/'actual-chain.json').write_text(json.dumps({'summary':summary,'requests':requests,'lost_responses':1,'permission_snapshot_unchanged':True},indent=2)+'\n')
    finally:
        out=Path('.runtime/full-owned-lifecycle-20261013/independent');out.mkdir(parents=True,exist_ok=True)
        (out/'latest-partial-chain.json').write_text(json.dumps({'requests':requests,'summary':summary,'lost_responses':int(lost)},indent=2)+'\n')
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
