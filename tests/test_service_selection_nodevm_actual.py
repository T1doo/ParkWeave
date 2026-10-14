"""Complete original HTML consumes actual PG/ASGI DTOs over local JSON IPC."""
from pathlib import Path
import json
import selectors
import shutil
import subprocess
import time
from uuid import UUID

from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave import service_selection_candidates as selections
from test_preparation import preparation_fixture,create,command,headers
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain,GOALS,ok
from test_service_selection_candidates import planner
from test_request_intents import save
from service_release_acceptance_support import authority_snapshot


def test_complete_original_html_real_second_park_catalog_candidate_recovery_adopt(selection_full_chain):
    a=selection_full_chain;f=a['f'];calls=[]
    p,_,_=create(f,user='fixture-c',goal='SYNTHETIC B fresh real HTML API flow')
    p=ok(save(f,p,goals=GOALS,user='fixture-c'))
    for slot in ('need_summary','material_outline'):
        p=ok(command(f,p,'ADD_EVIDENCE',user='fixture-c',slot=slot,text='SYNTHETIC B HTML fresh '+slot,source_kind='USER_STATEMENT',source_label='SYNTHETIC B HTML input'))
    p=ok(command(f,p,'REVIEW',user='prep-specialist-fixture-c',reason='SYNTHETIC B review'))
    p=ok(command(f,p,'CONFIRM',user='fixture-c',reason='SYNTHETIC B explicit confirmation'))
    f[1].assign_status('executor-c',UUID(p['run_id']),active=True)
    authority=authority_snapshot(f[1]);model=planner(calls,mode='all')
    assert shutil.which('node'),'Node required for actual whole HTML verification'
    root=Path(__file__).resolve().parents[1]
    proc=subprocess.Popen(['node','tests/service_selection_actual_nodevm.js',p['preparation_id']],cwd=root,text=True,
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    traffic=[];result=None;selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        with TestClient(create_app(f[0],capability_catalog=a['catalog'],selection_planner=model)) as api:
            until=time.monotonic()+25
            while time.monotonic()<until:
                if not selector.select(.1):
                    if proc.poll() is not None:break
                    continue
                line=proc.stdout.readline()
                if not line:break
                message=json.loads(line)
                if message['type']=='result':result=message;break
                assert message['type']=='request'
                options=message['options'];auth=options.get('headers',{}).get('Authorization')
                assert auth=='Bearer SYNTHETIC_NODE_API_SESSION'
                actual_headers={**options.get('headers',{}),'Authorization':'Bearer '+f[2]['fixture-c']}
                reply=api.request(options.get('method','GET'),message['path'],headers=actual_headers,content=options.get('body'))
                body=reply.json();traffic.append(dict(path=message['path'],method=options.get('method','GET'),status=reply.status_code,body=body))
                proc.stdin.write(json.dumps(dict(id=message['id'],status=reply.status_code,body=body))+'\n');proc.stdin.flush()
        proc.wait(timeout=5)
        stderr=proc.stderr.read()
        assert proc.returncode==0,stderr
        assert result and result['result']=='PASS' and result['completeOriginalHTML'] and result['realASGIResponses']
    finally:
        selector.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
    assert len(calls)==1
    posts=[t for t in traffic if t['method']=='POST']
    assert len(posts)==2 and posts[0]['path'].endswith('/service-selections') and posts[1]['path'].endswith('/service-case-plan')
    assert any(t['path'].endswith('/service-selections/recovery') for t in traffic)
    assert all(t['status']<300 for t in traffic)
    traces=[t['body']['source_trace'] for t in traffic if t['path'].endswith('/goal-results')]
    assert len(traces)==2 and traces[0]==traces[1]
    assert result['selected_services_visible']==3 and result['selected_instances_visible']==3
    assert result['source_trace_sha256']==traces[0]['trace_sha256']
    from parkweave.controlled_plans import _hash
    assert _hash({k:v for k,v in traces[0].items() if k!='trace_sha256'})==traces[0]['trace_sha256']
    actual=selections.read(f[0],f[2]['fixture-c'],p['preparation_id'],candidate_id=result['candidate_id'],catalog=a['catalog'])
    assert actual['validator_version']==4 and actual['candidate_id']==result['candidate_id']
    assert authority_snapshot(f[1])==authority
    out=Path('.runtime/service-release-tests-20261014');out.mkdir(parents=True,exist_ok=True)
    (out/'nodevm-actual-traffic.json').write_text(json.dumps(dict(result=result,traffic=traffic,real_model_calls=0,offline_model_calls=1,initial_fixture_assignments=1,runtime_authority_changed=0),indent=2)+'\n')
