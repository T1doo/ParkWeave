import json,selectors,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from conftest import pg,fixture
from test_preparation import preparation_fixture,headers


def test_independent_original_cold_chain(preparation_fixture):
    f=preparation_fixture
    root=Path('.runtime/run-refresh-recovery-20261013/independent')
    proc=subprocess.Popen(['node',str(root/'run_recovery.js'),'cold_owned'],cwd=Path.cwd(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None
    try:
        while True:
            assert selector.select(timeout=15),'Independent cold bridge made no progress within15 seconds'
            line=proc.stdout.readline()
            if not line:break
            message=json.loads(line)
            if 'request' not in message:
                summary=message
                assert summary['mode']=='cold_owned' and summary['checks']>=20
                break
            request=message['request'];options=request['options'];method=options.get('method','GET')
            response=f[3].request(method,request['path'],headers=headers(f[2],key=options.get('headers',{}).get('Idempotency-Key')),json=json.loads(options['body']) if options.get('body') else None)
            requests.append(dict(method=method,path=request['path'],status=response.status_code))
            assert response.status_code<400,(method,request['path'],response.status_code)
            if method=='POST' and request['path']=='/api/runs':f[0].finish(f[0].claim('synthetic-independent-cold-entry'))
            proc.stdin.write(json.dumps(dict(status=response.status_code,body=response.json()))+'\n');proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read()
        assert sum(r['method']=='POST' for r in requests)==4
        (root/'cold-owned-result.json').write_text(json.dumps(dict(summary=summary,requests=requests,scope='Original HTML real handlers + owned synthetic PostgreSQL ASGI API; no pending/entry mocks'),indent=2)+'\n')
    finally:
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
