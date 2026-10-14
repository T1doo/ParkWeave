"""Actual owned PG / ASGI responses through the complete original HTML."""
from datetime import datetime,timedelta,timezone
import json,selectors,subprocess,time,os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from test_preparation import headers,preparation_fixture
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain,ok
from test_service_selection_replay_acceptance import replay,all_public_rows
from test_service_resource_change_replay import prepare_changed
from test_synthetic_rule_readiness import simulation
from service_release_acceptance_support import authority_snapshot


def bridge(api,f,p,params,actor,*,readonly_rows=None):
    out=Path('.runtime/preview-rules-ui-20261014');out.mkdir(parents=True,exist_ok=True)
    errpath=out/(params['mode']+'-node.stderr.log');errfile=errpath.open('w')
    proc=subprocess.Popen(['node','tests/preview_rules_change_actual_nodevm.js',json.dumps(params)],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errfile,bufsize=0)
    traffic=[];external=[];value=None;selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        until=time.monotonic()+45
        buffered=b'';lines=[]
        while time.monotonic()<until:
            if not lines:
                if not selector.select(.1):
                    if proc.poll() is not None:break
                    continue
                chunk=os.read(proc.stdout.fileno(),65536)
                if not chunk:break
                buffered+=chunk
                while b'\n' in buffered:
                    line,buffered=buffered.split(b'\n',1);lines.append(line)
                if not lines:continue
            message=json.loads(lines.pop(0))
            if message['type']=='result':value=message;break
            if message['type']=='readonly_checkpoint':
                assert all_public_rows(f[1])==readonly_rows,'read-only proposal changed business rows'
                reply=dict(id=message['id'],status=200,body={})
            elif message['type']=='explicit_original_binding_confirmation':
                # This is a separately simulated explicit owner action using the
                # original compare/confirm API, not an automatic page request.
                base='/api/preparations/'+p['preparation_id'];key=uuid4().hex
                comparison=ok(api.get(base+'/resource-plan-binding',params=dict(candidate_combination_id=message['combination_id']),headers=headers(f[2],actor)))
                assert comparison['comparison']['can_confirm']
                body=dict(combination_id=message['combination_id'],expected_preparation_revision=p['revision'],expected_link_revision=1,expected_comparison_sha256=comparison['comparison']['sha256'],reason='SYNTHETIC separate owner explicitly confirms original current comparison')
                confirmed=ok(api.post(base+'/resource-plan-binding/confirm',headers=headers(f[2],actor,key),json=body),201)
                assert confirmed['event']['revision']==2
                external.append(dict(action='EXPLICIT_ORIGINAL_COMPARE_AND_CONFIRM',request_key=key,comparison=comparison,response=confirmed))
                reply=dict(id=message['id'],key=key)
            else:
                assert message['type']=='request';options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_NODE_API_SESSION'
                h={**options['headers'],'Authorization':'Bearer '+f[2][actor]}
                response=api.request(options.get('method','GET'),message['path'],headers=h,content=options.get('body'))
                body=response.json();traffic.append(dict(path=message['path'],method=options.get('method','GET'),key=options.get('headers',{}).get('Idempotency-Key'),status=response.status_code,body=body))
                reply=dict(id=message['id'],status=response.status_code,body=body)
                (out/(params['mode']+'-latest-observed-traffic.json')).write_text(json.dumps(traffic,indent=2)+'\n')
            proc.stdin.write((json.dumps(reply)+'\n').encode());proc.stdin.flush()
        proc.wait(timeout=5);errfile.flush();stderr=errpath.read_text()
        evidence=dict(mode=params['mode'],process_exit=proc.returncode,result=value,traffic=traffic,external_explicit_original_actions=external,stderr=stderr)
        out=Path('.runtime/preview-rules-ui-20261014');out.mkdir(parents=True,exist_ok=True)
        (out/(params['mode']+'-actual-traffic.json')).write_text(json.dumps(evidence,indent=2)+'\n')
        assert proc.returncode==0,stderr
        assert value and value['result']=='PASS' and value['realASGIResponses'] and value['completeOriginalHTML']
        assert all(t['status']<300 for t in traffic)
        return evidence
    finally:
        selector.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        errfile.close()


@pytest.mark.parametrize('mode',['c_normal','c_lost_hold'])
def test_actual_case_alternative_prefill_original_confirmation_and_key_reads(replay,mode):
    r=replay;f=r['f'];p,old_group,old_result=prepare_changed(r,'HTML-'+mode)
    authority=authority_snapshot(f[1]);rows=all_public_rows(f[1])
    with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    start=(now+timedelta(hours=5)).replace(second=0,microsecond=0)
    params=dict(mode=mode,preparation_id=p['preparation_id'],search_from=start.strftime('%Y-%m-%dT%H:%M'),search_until=(start+timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'))
    evidence=bridge(f[3],f,p,params,'fixture-c',readonly_rows=rows)
    assert authority_snapshot(f[1])==authority
    posts=[t for t in evidence['traffic'] if t['method']=='POST']
    assert len(posts)==(5 if mode=='c_normal' else 2)
    assert all('service-case-plan' not in t['path'] for t in posts)
    assert len(evidence['external_explicit_original_actions'])==(1 if mode=='c_normal' else 0)
    group=ok(f[3].get('/api/resource-combinations/'+old_group['id'],headers=headers(f[2],'fixture-c')))['combination']
    assert group['state']=='CANCELLED'


def test_actual_synthetic_rule_read_original_purpose_facts_and_no_business_writes(simulation):
    f,p,engine,adapter,context=simulation;authority=authority_snapshot(f[1]);rows=all_public_rows(f[1])
    dt=datetime.fromisoformat(context.as_of).astimezone(timezone.utc)
    params=dict(mode='b_true',preparation_id=p['preparation_id'],binding_id=context.binding_id,as_of=dt.strftime('%Y-%m-%dT%H:%M'),expected_truth='TRUE')
    with TestClient(create_app(f[0],synthetic_rule_readiness=adapter)) as api:
        evidence=bridge(api,f,p,params,'fixture-a')
    assert all(t['method']=='GET' for t in evidence['traffic'])
    assert all_public_rows(f[1])==rows
    assert authority_snapshot(f[1])==authority
