"""Original full HTML cold entry talking to owned PostgreSQL / real ASGI.

IPC only replaces network transport; it never substitutes product response DTOs.
The independent Python worker completes original Run work outside the UI.
"""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain
from service_release_acceptance_support import authority_snapshot


@pytest.mark.parametrize('mode',['normal','facade_loss','run_loss','material_loss','execute_revoked','stage_prepare_loss','stage_prepare_unknown'])
def test_complete_original_html_fresh_cold_input_actual_pg_asgi(selection_full_chain,tmp_path,mode):
    a=selection_full_chain;f=a['f'];store,owner,tokens,_=f
    facade=ParkInstanceConsumer(a['catalog'],ConsumerRepository(tmp_path/'node-cold.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
    assert shutil.which('node'),'Node is required for the permitted offline full HTML harness'
    before=authority_snapshot(owner)
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0
    root=Path(__file__).resolve().parents[1]
    out=root/'.runtime/at-replay-20261014/cold-entry'/('pytest-'+str(os.getpid()));out.mkdir(parents=True,exist_ok=True)
    proc=subprocess.Popen(['node','tests/service_cold_entry_actual_nodevm.js',mode],cwd=root,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    traffic=[];controls=[];result=None;stderr='';run_id=None
    try:
        with TestClient(create_app(store,capability_catalog=a['catalog'],instance_consumer=facade)) as api:
            until=time.monotonic()+40
            while time.monotonic()<until:
                if not selector.select(.1):
                    if proc.poll() is not None:break
                    continue
                line=proc.stdout.readline()
                if not line:break
                message=json.loads(line)
                if message['type']=='result':result=message;break
                if message['type']=='control':
                    action=message['action']
                    if action=='worker':
                        claimed=store.claim('SYNTHETIC independent Python worker for cold '+mode)
                        assert claimed is not None
                        store.finish(claimed)
                        body=dict(worker='ORIGINAL_LOCAL_WORKER',run_id=run_id)
                    else:
                        assert action=='revoke_execute'
                        with owner.connect() as c:
                            owner.lock_principal(c,'fixture-c',exclusive=True)
                            changed=c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-c' AND capability='EXECUTE' RETURNING principal_id").fetchall()
                            assert len(changed)==1
                        body=dict(test_fixture_permission_change='EXECUTE_REVOKED')
                    controls.append(dict(action=action,body=body));status=200
                else:
                    assert message['type']=='request'
                    options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_NODE_API_SESSION'
                    actual_headers={**options['headers'],'Authorization':'Bearer '+tokens['fixture-c']}
                    reply=api.request(options.get('method','GET'),message['path'],headers=actual_headers,content=options.get('body'))
                    status=reply.status_code;body=reply.json()
                    traffic.append(dict(path=message['path'],method=options.get('method','GET'),key=options['headers'].get('Idempotency-Key'),request_body=json.loads(options['body']) if options.get('body') else None,status=status,body=body))
                    if status==200 and message['path']=='/api/service-instance-cold-inputs/recovery':
                        assert body['actor_ref']!='fixture-c'
                        for observation in body['product_observations']:
                            if observation['status']=='COMMITTED' and observation['name']!='CREATE_RUN':
                                assert observation['result']['actor_id']=='fixture-c'
                                assert observation['result']['actor_id']!=body['actor_ref']
                    if options.get('method')=='POST' and message['path']=='/api/runs' and status==202:run_id=body['run_id']
                proc.stdin.write(json.dumps(dict(id=message['id'],status=status,body=body))+'\n');proc.stdin.flush()
        proc.wait(timeout=5);stderr=proc.stderr.read()
    finally:
        selector.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        if not stderr:stderr=proc.stderr.read()
        (out/(mode+'-traffic.json')).write_text(json.dumps(dict(mode=mode,process_exit=proc.returncode,result=result,traffic=traffic,controls=controls,stderr=stderr),indent=2,default=str)+'\n')
    assert proc.returncode==0,stderr
    assert result and result['result']=='PASS' and result['completeOriginalHTML'] and result['realASGIResponses']
    posts=[row for row in traffic if row['method']=='POST']
    assert len(posts)==(2 if mode=='stage_prepare_unknown' else 10)
    assert [row['path'] for row in posts].count('/api/service-instance-cold-inputs')==1
    assert [row['path'] for row in posts].count('/api/runs')==1
    descriptors=[row for row in posts if '/prepare-stage?' in row['path']]
    assert len(descriptors)==(0 if mode=='stage_prepare_unknown' else 4)
    assert len({row['path'] for row in descriptors})==len(descriptors)
    assert len({row['key'] for row in posts if '/prepare-stage?' not in row['path']})==(2 if mode=='stage_prepare_unknown' else 6)
    assert all(row['status']<300 for row in traffic if not(mode=='execute_revoked' and row['path']=='/api/service-instance-configurations' and row['status']==403))
    assert not any(row['method']=='POST' and ('service-selections' in row['path'] or 'service-case-plan' in row['path']) for row in traffic)
    if mode=='stage_prepare_unknown':
        assert result['transportFailedBeforeASGI'] and result['unknownDescriptorRetained']
        assert result['allOriginalStagesObserved'] is False and result['preparation_id'] is None
        assert result['descriptorTransportAttempts']==1
        assert all('/prepare-stage?' not in row['path'] for row in traffic)
        with owner.connect() as c:
            assert c.execute('SELECT count(*) n FROM preparations').fetchone()['n']==0
            run=c.execute('SELECT state,namespace FROM runs WHERE id=%s',(UUID(run_id),)).fetchone()
            assert run==dict(state='SUCCEEDED',namespace='SYNTHETIC')
        assert authority_snapshot(owner)==before
        return
    with owner.connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(UUID(result['preparation_id']),)).fetchone()
        assert parent['park_id']=='park-b' and parent['owner_id']=='fixture-c' and parent['run_id']==UUID(run_id)
        assert parent['state']=='IN_PREPARATION' and parent['service_case_plan'] is None and not parent['planning_previews']
        actual_run=c.execute('SELECT * FROM runs WHERE id=%s',(parent['run_id'],)).fetchone()
        assert actual_run['state']=='SUCCEEDED' and actual_run['namespace']=='SYNTHETIC'
        materials=c.execute('SELECT * FROM preparation_evidence WHERE preparation_id=%s',(parent['id'],)).fetchall()
        assert len(materials)==2 and {m['text'] for m in materials}=={'SYNTHETIC NODE PRIVATE '+mode+' new need','SYNTHETIC NODE PRIVATE '+mode+' new outline'}
        assert c.execute('SELECT count(*) n FROM run_assignments').fetchone()['n']==0
        assert c.execute("SELECT count(*) n FROM runs WHERE namespace<>'SYNTHETIC'").fetchone()['n']==0
    after=authority_snapshot(owner)
    if mode=='execute_revoked':
        assert all(before[t]==after[t] for t in before if t!='capability_grants')
        before_exec=[r for r in before['capability_grants'] if r['principal_id']=='fixture-c' and r['capability']=='EXECUTE']
        after_exec=[r for r in after['capability_grants'] if r['principal_id']=='fixture-c' and r['capability']=='EXECUTE']
        assert len(before_exec)==len(after_exec)==1 and before_exec[0]['active'] and not after_exec[0]['active']
        is_executor_grant=lambda row:row['principal_id']=='fixture-c' and row['capability']=='EXECUTE'
        assert [row for row in before['capability_grants'] if not is_executor_grant(row)]==[row for row in after['capability_grants'] if not is_executor_grant(row)]
    else:assert after==before
