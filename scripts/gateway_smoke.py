"""Real localhost HTTP trace; requires the explicitly opted-in synthetic harness."""
import json
import hashlib
import time
import uuid
from pathlib import Path
import httpx

root=Path.cwd()
tokens=json.loads((root/'.runtime/synthetic-sessions.json').read_text())
headers={'Authorization':'Bearer '+tokens['fixture-a'],'Idempotency-Key':'gateway-smoke-'+uuid.uuid4().hex}
body={'action':'fault.record','goal':'合成：通过正常API/worker核对丢失的响应'}
with httpx.Client(base_url='http://127.0.0.1:8765',timeout=5) as api:
    health=api.get('/health').json()
    assert health['execution_mode']=='FAULT_INJECTION'
    create=api.post('/api/runs',headers=headers,json=body);assert create.status_code==202
    run=create.json()['run_id'];states=[];record=None
    for _ in range(120):
        response=api.get('/api/runs/'+run,headers=headers);assert response.status_code==200
        record=response.json()
        pair=(record['state'],record['operation']['state'])
        if not states or states[-1]!=pair:states.append(pair)
        if record['state']=='SUCCEEDED':break
        time.sleep(.05)
    assert ('RECONCILING','OUTCOME_UNKNOWN') in states,states
    assert record['success_scope']=='FAULT_INJECTION_EFFECT_KNOWN' and record['case'] is None
    denied=api.get('/api/runs/'+run,headers={'Authorization':'Bearer '+tokens['fixture-c']})
    assert denied.status_code==403
    report={'status':'PASS','environment':'Linux local HTTP + independent persistent worker + PostgreSQL16.2',
            'type':'FAULT_INJECTION','real_model_calls':0,'input_sha256':hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'health':health,'create_status':202,'cross_park_status':403,'state_trace':states,'result':record,
            'processes':json.loads((root/'.runtime/smoke-environment.json').read_text()),'windows':'BLOCKED'}
    (root/'docs/F1/evidence/eng003-gateway-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
