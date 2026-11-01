"""Actual installed-wheel API/PG/two continuous workers; no model or browser.

Fresh explicitly SYNTHETIC demo identities are created only by its original
setup entry. Every business/source/approval action afterwards is an HTTP POST;
owner SQL is READ ONLY snapshot/authority observation, never a success writer.
This tests the existing ordinary demo, not Windows/protected product acceptance.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts import local_approval_installed_browser_once as old
from scripts import local_source_restart_installed_browser_once as source

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='installed Linux integration only')


class APIBudget:
    """This API-only scenario: <=41 writes and <=200 reads, readiness <=40.

No browser phase or extra request allowance is borrowed from a different run.
The existing 270s work deadline and 360s outer tail remain unchanged.
"""
    def __init__(self,report):
        self.report=report;self.posts=self.reads=self.internal_reads=0
    def count(self,method,path,phase):
        assert path.startswith('/') and '?' not in path
        if method=='POST':self.posts+=1;assert self.posts<=41
        else:assert method in ('GET','HEAD');self.reads+=1;assert self.reads<=200
        assert self.internal_reads<=40
        self.report['request_budget']=dict(POST=self.posts,GET_HEAD=self.reads,
            readiness=self.internal_reads,limits=dict(POST=41,GET_HEAD=200,readiness=40))


@contextmanager
def generation(run,tag):
    with source.server(run,tag):
        env=json.loads((run.harness/'application-env.json').read_text())
        assert 'PYTHONPATH' not in env and not any(k.endswith('_API_TOKEN') for k in env)
        role='worker-'+tag;fact=dict(role=role,generation=tag)
        run.report.setdefault('continuous_workers',[]).append(fact)
        primary=None;child=None
        with (run.private/(role+'.log')).open('w') as log:
            try:
                child=subprocess.Popen([str(run.python),'-I','-B',str(run.harness/'entry.py'),
                    'worker',role,'--continuous'],cwd=run.harness,env=env,stdout=log,stderr=log)
                fact['pid']=child.pid
                yield
                assert child.poll() is None,'normal worker must remain live through generation'
            except BaseException as error:primary=error;raise
            finally:
                if child is not None:
                    try:
                        if child.poll() is None:child.terminate()
                        child.wait(timeout=10);fact['exit_code']=child.returncode
                        assert child.returncode==0,'owned worker stop was not a normal acknowledged exit'
                    except BaseException as error:
                        fact['cleanup_error_type']=type(error).__name__
                        if primary is not None:raise BaseExceptionGroup('Original business and owned worker stop failed',[primary,error]) from None
                        raise


def call(run,suffix='',body=None,**kw):return source.call(run,suffix,body,**kw)


def run_case(run,label):
    result=old.api_call(run,'/api/runs',dict(goal=label),expected=202)
    end=min(run.started+270,time.monotonic()+10)
    while time.monotonic()<end:
        row=old.api_call(run,'/api/runs/'+result['run_id'])
        if row['state']=='SUCCEEDED':return result['run_id']
        assert row['state'] not in ('FAILED','CANCELLED')
        time.sleep(.1)
    raise AssertionError('normal continuous worker did not process the explicit request')


def material(run,actor,action,**fields):
    parent=call(run)['preparation']
    return call(run,'/commands',dict(action=action,expected_revision=parent['revision'],**fields),actor=actor)


def snapshot(run):
    result=source.snapshot(run)
    with source.owner(run) as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        from scripts.ordinary_synthetic_demo import authority
        result['authority']=authority(connection)
    return result


def first_business(run):
    # The original preparation helper's one-shot worker is unnecessary here:
    # a real continuous installed worker already runs. Its same public API
    # sequence is written explicitly so no worker/identity/source is substituted.
    run_id=run_case(run,'SYNTHETIC 安装态资源审批与来源采纳')
    p=old.api_call(run,'/api/preparations',dict(run_id=run_id,service_id='synthetic-material-preparation',
        service_version=1,reviewer_id='ordinary-demo-specialist'),expected=201)
    run.record=dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=run_id)
    p=call(run,'/request-intent',dict(expected_preparation_revision=p['revision'],
        request_text='SYNTHETIC 独立资料与资源关联诉求',required_goals=source.GOALS))
    for slot in ('need_summary','material_outline'):
        material(run,'enterprise','ADD_EVIDENCE',slot=slot,text='SYNTHETIC '+slot,
            source_kind='USER_STATEMENT',source_label='SYNTHETIC original source')
    material(run,'specialist','REVIEW',reason='SYNTHETIC 独立专员审核')
    material(run,'enterprise','CONFIRM',reason='SYNTHETIC 企业确认')
    p=call(run)['preparation'];capabilities=call(run,'/service-capabilities')
    candidate=call(run,'/service-selections',dict(expected_preparation_revision=p['revision'],
        expected_source_sha256=capabilities['source_sha256'],
        expected_capability_catalog_sha256=capabilities['capability_catalog_sha256']),expected=201)
    assert candidate['producer']['mode']=='NO_MODEL' and candidate['producer']['real_model_calls']==0
    plan=call(run,'/service-case-plan',dict(expected_preparation_revision=p['revision'],
        expected_request_revision=capabilities['request_revision'],expected_plan_revision=0,
        expected_source_sha256=capabilities['source_sha256'],required_goals=source.GOALS,
        reason='SYNTHETIC 明确采纳本次NO_MODEL方案',candidate_id=candidate['candidate_id'],
        expected_candidate_sha256=candidate['candidate_sha256'],
        expected_verification_sha256=candidate['verification_sha256']),expected=201)
    run.record['plan_id']=plan['plan_id'];source.step(run,'P1')
    source.new_holds(run);holds=run.record['new_holds']
    _,body=source.quote_body(run,holds);item=source.api_approval(run,body)
    first=call(run,'/resource-delivery',{**body,'approval_id':item['id']},expected=201)
    source.step(run,'P2');run.old_delivery=first;run.old_approval=item
    run.report['first_plan_candidate']=dict(id=candidate['candidate_id'],producer=candidate['producer'])
    run.report['first_snapshot']=snapshot(run)
    return body


def source_continuation(run):
    view=call(run,'/opportunities')
    imported=call(run,'/opportunities/commands',dict(action='IMPORT',expected_revision=view['revision'],
        expected_source_sha256=view['source_sha256'],reason='SYNTHETIC 导入待核对的材料来源提示',
        entry=dict(family_id=str(uuid4()),generation=1,kind='LOCAL_CASE_DATA',catalog_version=1,
            title='SYNTHETIC 材料版本变化待审',note='SYNTHETIC 仅提示，不是批准或事实')))
    card=imported['current']['cards'][0]
    unchanged=call(run,'/opportunities/'+card['id']+'/plan-revision')
    assert not unchanged['can_adopt'] and 'NO_ACTUAL_SOURCE_CHANGE' in unchanged['blocking_reasons']
    material(run,'enterprise','REOPEN',reason='SYNTHETIC 明确修订原始资料')
    material(run,'enterprise','ADD_EVIDENCE',slot='need_summary',text='SYNTHETIC actual revised requirement',
        source_kind='USER_STATEMENT',source_label='SYNTHETIC revised source v2')
    material(run,'specialist','REVIEW',reason='SYNTHETIC 专员审核新版本')
    material(run,'enterprise','CONFIRM',reason='SYNTHETIC 企业确认新版本')
    view=call(run,'/opportunities')
    refreshed=call(run,'/opportunities/commands',dict(action='REFRESH',expected_revision=view['revision'],
        expected_source_sha256=view['source_sha256'],reason='SYNTHETIC 读取实际材料变化'))
    card=refreshed['current']['cards'][0];preview=call(run,'/opportunities/'+card['id']+'/plan-revision')
    assert preview['can_adopt'],preview['blocking_reasons']
    adoption_key=str(uuid4());adopted=call(run,'/service-case-plan',preview['adoption'],key=adoption_key,expected=201)
    run.report['source_adoption']=dict(key=adoption_key,preview=preview,receipt=adopted['command_receipt'])
    source.step(run,'P1')  # Materials changed: the old P1 is not claimed preserved.
    source.new_holds(run)
    _,body=source.quote_body(run,run.record['new_holds'],1)
    before=snapshot(run)
    call(run,'/resource-delivery',{**body,'approval_id':run.old_approval['id']},expected=409)
    assert snapshot(run)==before
    revoked=source.api_approval(run,body);ledger=call(run,'/plan-approval')
    decision=dict(action='REVOKE',approval_id=revoked['id'],expected_revision=ledger['revision'],
        expected_binding_sha256=revoked['binding_sha256'],reason='SYNTHETIC 本人明确撤销本次资源批准')
    before=snapshot(run)
    call(run,'/plan-approval/commands',decision,actor='specialist',expected=403)
    assert snapshot(run)==before
    call(run,'/plan-approval/commands',decision)
    before=snapshot(run)
    call(run,'/resource-delivery',{**body,'approval_id':revoked['id']},expected=409)
    assert snapshot(run)==before
    item=source.api_approval(run,body);key=str(uuid4())
    run.new_delivery=call(run,'/resource-delivery',{**body,'approval_id':item['id']},key=key,expected=201)
    source.step(run,'P2')
    run.report['before_restart_snapshot']=snapshot(run)
    initial=run.report['first_snapshot']['preparation'];current=run.report['before_restart_snapshot']['preparation']
    assert current['service_case_plan']['id']==initial['service_case_plan']['id']
    assert current['service_case_plan']['events'][:len(initial['service_case_plan']['events'])]==initial['service_case_plan']['events']
    assert current['local_resource_approvals']['events'][:3]==initial['local_resource_approvals']['events']
    assert run.report['before_restart_snapshot']['authority']==run.report['first_snapshot']['authority']
    run.report['before_restart_approval']=call(run,'/plan-approval')
    run.report['before_restart_source_plan']=call(run,'/service-case-plan')
    run.report['before_restart_materials']=call(run)
    run.report['before_restart_opportunities']=call(run,'/opportunities')
    run.report['receipts_before_restart']=[run.old_delivery['receipt'],run.new_delivery['receipt']]


def test_installed_resource_approval_and_api_source_adoption_survive_full_service_restart(tmp_path):
    directory=tmp_path/'actual-installed';directory.mkdir(mode=0o700)
    report=dict(status='NOT_RUN',stage='INSTALL',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=old.base.ROOT,text=True).strip(),
        scope='INSTALLED_LINUX_ORDINARY_SYNTHETIC_API_NOT_BROWSER_OR_WINDOWS',responses=[],real_model_calls=0,
        direct_owner_SQL_after_setup='READ_ONLY_SNAPSHOTS_ONLY',identity_reset=False,screenshots=[],violations=[])
    run=SimpleNamespace(started=time.monotonic(),report=report,secrets=[],private=directory,public=directory/'public')
    wheelhouse=os.environ.get('PARKWEAVE_TEST_WHEELHOUSE')
    if wheelhouse:run.wheelhouse=Path(wheelhouse)
    run.public.mkdir();run.budget=APIBudget(report)
    report['planned_POSTs']=dict(first_business=18,source_and_reapproval=22,second_worker_new_request=1,total=41)
    previous=os.umask(0o077)
    try:
        old.installation(run,old.current_wheel(run))
        sessions=json.loads((run.state/'sessions.json').read_text())
        run.tokens['other-enterprise']=sessions['second_enterprise']
        with generation(run,'first'):
            first_business(run);assert run.budget.posts==18
            source_continuation(run);assert run.budget.posts==40
        source.cold_gate(run)
        with generation(run,'restarted'):
            report['stage']='COLD_READ_ONLY_ORIGINAL_RECORDS';posts=run.budget.posts
            assert snapshot(run)==report['before_restart_snapshot']
            assert call(run,'/plan-approval')==report['before_restart_approval']
            assert call(run,'/service-case-plan')==report['before_restart_source_plan']
            assert call(run)==report['before_restart_materials']
            assert call(run,'/opportunities')==report['before_restart_opportunities']
            call(run,'/plan-approval',actor='other-enterprise',expected=403)
            for delivery in (run.old_delivery,run.new_delivery):
                recovered=call(run,'/resource-delivery/recovery/'+delivery['delivery_binding']['request_key'])
                assert recovered['receipt']==delivery['receipt']
            assert snapshot(run)==report['before_restart_snapshot']
            adoption=report['source_adoption']
            recovered=call(run,'/service-case-plan/command-recovery',key=adoption['key'])
            assert recovered['status']=='COMMITTED' and recovered['read_only'] and recovered['historical_only']
            assert recovered['automatically_replayed'] is False
            assert all(recovered['event'][k]==v for k,v in adoption['receipt'].items())
            assert run.budget.posts==posts
            report['cold_original_record_POSTs']=run.budget.posts-posts
            # Explicit separate user request proves the second continuous
            # worker executes; it never replays a previous approval/adoption.
            report['second_worker_new_request']=run_case(run,'SYNTHETIC 重启后独立处理请求')
            assert snapshot(run)==report['before_restart_snapshot']
        source.collect(run,complete=False)
        attest=report['process_installation_attestations'];expected={'setup-attestation':2,'api-attestation':4,'worker-first-attestation':2,'worker-restarted-attestation':2}
        assert {k:len(v) for k,v in attest.items()}==expected
        for values in attest.values():
            assert all(v['wheel_sha256']==report['installation']['wheel_sha256'] and v['verified_package_files']==len(report['installation']['package_files']) and v['isolated'] and not v['PYTHONPATH'] for v in values)
        assert attest['worker-first-attestation'][0]['pid']!=attest['worker-restarted-attestation'][0]['pid']
        assert [w['exit_code'] for w in report['continuous_workers']]==[0,0]
        report['status']='PASS_INSTALLED_API_SOURCE_APPROVAL_FULL_SERVICE_RESTART'
    finally:
        os.umask(previous)
        report['elapsed_seconds']=round(time.monotonic()-run.started,3)
        # Private test report only. Never publish fixture session files/logs.
        from scripts.ordinary_resource_browser_once import redact
        (directory/'result.json').write_text(redact(report,run.secrets)+'\n')
