"""Owned PostgreSQL and real ASGI through both complete original HTML scripts."""
import json,os,selectors,subprocess,time
from copy import deepcopy
from pathlib import Path
import pytest
from test_template_upgrade import upgrade_case,instance,publication,confirmed,snapshot,link_fixture,receipt_fixture,preparation_fixture
from test_service_case_steps import verified,read as plan_read,business
from test_preparation import headers

@pytest.mark.parametrize('mode',['normal','lost_apply','lost_choice','wrong_target','wrong_plan','wrong_source'])
def test_template_migration_actual_page_explicit_apply_key_recovery_and_original_verify(upgrade_case,mode):
    u=upgrade_case;f=u['f'];row,old=instance(u);p=confirmed(u,row);original=verified(f,p,'P1');target=publication(u,source='2')
    initial=snapshot(u);unchanged=business(f);old_binding=deepcopy(row['binding'])
    out=Path('.runtime/template-migration-ui-20261014');out.mkdir(parents=True,exist_ok=True)
    params=dict(mode=mode,instance_id=row['instance_id'],target_release_id=target['release_id'],preparation_id=p['preparation_id'],plan_id=original['plan_id'],step_id=original['steps'][0]['id'])
    stderr_path=out/(mode+'-node.stderr.log');err=stderr_path.open('w')
    proc=subprocess.Popen(['node','tests/template_migration_actual_nodevm.js',json.dumps(params)],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0)
    sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);buffered=b'';lines=[];traffic=[];summary=None;checkpoints=[]
    try:
        deadline=time.monotonic()+75
        while time.monotonic()<deadline:
            if not lines:
                if not sel.select(.1):
                    if proc.poll() is not None:break
                    continue
                chunk=os.read(proc.stdout.fileno(),65536)
                if not chunk:break
                buffered+=chunk
                while b'\n' in buffered:
                    line,buffered=buffered.split(b'\n',1);lines.append(line)
                if not lines:continue
            message=json.loads(lines.pop(0))
            if message['type']=='result':summary=message;break
            if message['type']=='request':
                options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_NODE_API_SESSION'
                h={**options['headers'],'Authorization':'Bearer '+f[2]['fixture-a']}
                r=u['client'].request(options.get('method','GET'),message['path'],headers=h,content=options.get('body'))
                body=r.json();traffic.append(dict(method=options.get('method','GET'),path=message['path'],status=r.status_code,key=h.get('Idempotency-Key'),body=body))
                response=dict(id=message['id'],status=r.status_code,body=body)
            else:
                checkpoints.append(message['type']);current=snapshot(u)
                assert business(f)==unchanged
                assert current[1]==initial[1],'consumer immutable binding/stage history changed'
                assert u['consumer'].read(f[2]['fixture-a'],row['instance_id'])['binding']==old_binding
                if message['type'] in ('readonly_checkpoint','choice_checkpoint'):assert current[0]==initial[0]
                elif message['type']=='apply_checkpoint':
                    for table in initial[0]:
                        if table!='preparations':assert current[0][table]==initial[0][table],table
                    current_plan=plan_read(f,p).json();assert current_plan['plan_id']==original['plan_id']
                    assert current_plan['steps'][0]['id']==original['steps'][0]['id'] and current_plan['steps'][0]['state']!='VERIFIED'
                else:raise AssertionError(message)
                response=dict(id=message['id'],status=200,body={})
            (out/(mode+'-latest-traffic.json')).write_text(json.dumps(traffic,indent=2)+'\n')
            proc.stdin.write((json.dumps(response)+'\n').encode());proc.stdin.flush()
        proc.wait(timeout=5);err.flush();stderr=stderr_path.read_text()
        evidence=dict(params=params,summary=summary,checkpoints=checkpoints,traffic=traffic,exit=proc.returncode,stderr=stderr)
        (out/(mode+'-actual-traffic.json')).write_text(json.dumps(evidence,indent=2)+'\n')
        assert proc.returncode==0,stderr
        assert summary and summary['result']=='PASS' and summary['checks']>=25
        assert all(t['status']<300 for t in traffic)
        if mode.startswith('wrong_'):assert summary['tamperedRecoveryProofRejected'] is True
        assert checkpoints==['readonly_checkpoint','choice_checkpoint','apply_checkpoint']
        final=plan_read(f,p).json();assert final['steps'][0]['state']=='VERIFIED'
        assert final['events'][:len(original['events'])]==original['events']
        assert [e['action'] for e in final['events'][-2:]]==['TEMPLATE_UPGRADE','VERIFY']
        assert business(f)==unchanged and snapshot(u)[1]==initial[1]
    finally:
        sel.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        err.close()
