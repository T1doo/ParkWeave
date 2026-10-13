"""Original page business entries, owned PG/ASGI, existing isolated access bridge."""
import json,selectors,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()/"tests"))
from conftest import pg,fixture

from parkweave.isolated_run_access import IsolatedRunAccessBridge
from test_case_resources import link_fixture
from test_preparation import headers,preparation_fixture
from test_executor_receipts import receipt_fixture
from test_isolated_run_access import permission_snapshot


def test_original_page_differentiates_declared_constraints_and_confirms_exact_source(link_fixture,tmp_path):
    f=link_fixture;permissions=permission_snapshot(f[1])
    bridge=IsolatedRunAccessBridge(f[1],f[1]._case_fact_fixture_receipt,
        tmp_path/'original-page.run-access.candidate.sqlite3',approver_ids={'prep-specialist-fixture-a'},enabled_for_isolated_tests=True)
    bridge.attach_store(f[0]);assert permission_snapshot(f[1])==permissions
    proc=subprocess.Popen(['node',str(Path.cwd()/'tests/differentiated_planning.js'),'differentiated_planning'],
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
            drop=False
            if drop:lost=True
            proc.stdin.write((json.dumps({'status':response.status_code,'body':response.json(),'lost':bool(drop)})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read()
        assert summary and summary['checks']>=20
        assert permission_snapshot(f[1])==permissions
        with f[1].connect() as c:
            assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(summary['first'],)).fetchone()['service_case_plan']['id']==summary['adopted']
            assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(summary['second'],)).fetchone()['service_case_plan'] is None
        out=Path('.runtime/differentiated-planning-20261013/independent');out.mkdir(parents=True,exist_ok=True)
        (out/'actual-chain.json').write_text(json.dumps({'summary':summary,'requests':requests,'lost_responses':1,'permission_snapshot_unchanged':True},indent=2)+'\n')
    finally:
        out=Path('.runtime/differentiated-planning-20261013/independent');out.mkdir(parents=True,exist_ok=True)
        (out/'latest-partial-chain.json').write_text(json.dumps({'requests':requests,'summary':summary,'lost_responses':int(lost)},indent=2)+'\n')
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
