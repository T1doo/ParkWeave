"""Actual fresh API and owned PG restart reject every dedicated Approval write."""
from pathlib import Path
from uuid import uuid4,UUID
import json,os,socket,pytest
from playwright.sync_api import sync_playwright
from parkweave.process_env import minimal_environment
from parkweave.store import Denied
from test_catalog_approval_restart import own_case,start_api,identity
from test_catalog_approval_coordination import setup
from test_service_plan_approval import approved,ledger
from test_case_resource_delivery import submit,effects
from test_service_case_steps import verified
from test_preparation import headers
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/new-api-writeoff')

def test_actual_new_api_and_owned_pg_restart_dedicated_propose_approve_revoke_stay_off(own_case):
    f,pg=own_case;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);key=uuid4().hex
    assert submit(f,p,{**data,'approval_id':item['id']},key).status_code==201;verified(f,p,'P2')
    original=ledger(f,p);before=identity(f);old_pg_pid=pg.get_pid();api_pids=[];status_sets=[]
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    OUT.mkdir(parents=True,exist_ok=True);base='http://127.0.0.1:'+str(port)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page()
        try:
            for restart in [False,True]:
                if restart:
                    from pgserver._commands import pg_ctl
                    pg_ctl(['-w','-m','fast','stop'],pgdata=pg.pgdata,user=pg.system_user,timeout=10,env=minimal_environment(os.environ));assert not (pg.pgdata/'postmaster.pid').exists();pg.ensure_postgres_running()
                    with pytest.raises(Denied):bridge.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']))
                with (OUT/('actual-new-api-'+str(restart)+'.log')).open('w') as log:
                    proc=start_api(f,page,port,log);api_pids.append(proc.pid)
                    try:
                        page.goto(base);prefix=base+'/api/preparations/'+p['preparation_id'];auth=headers(f[2]);statuses=[]
                        for suffix in ['/resource-delivery/recovery/'+key,'/service-case-plan','/goal-results']:
                            assert page.request.get(prefix+suffix,headers=auth).status==200
                        assert page.request.get(prefix+'/plan-approval',headers=auth).status==403
                        assert not page.request.get(base+'/api/plan-approval/status',headers=auth).json()['enabled']
                        request=dict(expected_revision=3,delivery=data)
                        statuses.append(page.request.post(prefix+'/plan-approval/proposals',headers=headers(f[2],key=uuid4().hex),data=request).status)
                        for action in ['APPROVE','REVOKE']:
                            command=dict(action=action,approval_id=item['id'],expected_revision=3,expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC explicit negative '+action)
                            statuses.append(page.request.post(prefix+'/plan-approval/commands',headers=headers(f[2],key=uuid4().hex),data=command).status)
                        assert statuses==[403,403,403];status_sets.append(statuses)
                        assert ledger(f,p)==original and effects(f)==[1,3,1,1,1] and f[2]['fixture-a'] not in page.evaluate('JSON.stringify({...localStorage})')
                    finally:proc.terminate();proc.wait(timeout=5)
            after=identity(f);assert api_pids[0]!=api_pids[1] and old_pg_pid!=pg.get_pid()
            assert before['postmaster_start']!=after['postmaster_start'] and before['system_identifier']==after['system_identifier'] and before['database_oid']==after['database_oid']
            (OUT/'actual-new-api-writeoff.json').write_text(json.dumps({'different_api_pids':True,'api_pids':api_pids,'pg_restarted':True,'old_pg_pid':old_pg_pid,'new_pg_pid':pg.get_pid(),'pg_start_changed':True,'system_identifier_unchanged':True,'database_oid_unchanged':True,'dedicated_propose_approve_revoke_statuses':status_sets,'old_cap_after_pg_restart':'DENIED','consumed_recovery_p2_goal_read_200':True,'ledger_retained':True,'effects':[1,3,1,1,1],'nonce_reissued':False},indent=2)+'\n')
        finally:browser.close()
