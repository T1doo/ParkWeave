"""Original page must show every current required goal before replacing a plan."""
import json,selectors,subprocess
from pathlib import Path
from test_partial_service_plan import setup_partial
from test_preparation import headers,preparation_fixture
from test_executor_receipts import receipt_fixture
from test_case_resources import link_fixture
from test_service_case_steps import adopt,adopt_body,business

def test_actual_original_plan_page_lists_new_required_goal_before_partial_replacement(link_fixture):
    f=link_fixture;p=setup_partial(f)
    r=adopt(f,p,adopt_body(f,p,partial_adoption=True));assert r.status_code==201,r.text
    before=business(f)
    proc=subprocess.Popen(['node','tests/partial_service_plan_expansion.js','partial_expansion',p['preparation_id']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None
    out=Path('.runtime/partial-plan-20261013/independent/final-source');out.mkdir(parents=True,exist_ok=True)
    try:
        while True:
            assert selector.select(timeout=15),'Original expansion UI bridge stalled'
            line=proc.stdout.readline()
            if not line:break
            message=json.loads(line)
            if 'request' not in message:summary=message;break
            req=message['request'];options=req['options'];method=options.get('method','GET');body=json.loads(options['body']) if options.get('body') else None
            actor=options['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_')
            response=f[3].request(method,req['path'],headers=headers(f[2],actor,key=options['headers'].get('Idempotency-Key')),json=body)
            requests.append(dict(method=method,path=req['path'],status=response.status_code,required_goals=body.get('required_goals') if body else None))
            assert response.status_code<400,(requests[-1],response.text)
            proc.stdin.write((json.dumps(dict(status=response.status_code,body=response.json(),lost=False))+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode()
        assert summary and summary['checks']==17 and summary['adopts']==1
        assert business(f)==before
        (out/'actual-expansion-chain.json').write_text(json.dumps(dict(summary=summary,requests=requests,business_rows_unchanged=True),indent=2)+'\n')
    finally:
        (out/'latest-partial-expansion-chain.json').write_text(json.dumps(dict(summary=summary,requests=requests),indent=2)+'\n')
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
