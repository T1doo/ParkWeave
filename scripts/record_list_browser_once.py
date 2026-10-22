"""Exact hosted run10: real read-only list UI over owned synthetic initial data."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit

from scripts import fictional_park_browser_once as base

PRIVATE=base.ROOT/'.runtime/record-list-browser-once'
NAMES=frozenset(f'{n:02}-{kind}-{width}.png' for n,kind,width in
    [(1,'preparation',390),(2,'dispatch',390),(3,'receipt',390),
     (4,'preparation',1200),(5,'dispatch',1200),(6,'receipt',1200)])|{'07-read-denied.png'}
PUBLIC_FILES=NAMES|{'result.json'}


def require_time(run,seconds=45):
    assert time.monotonic()+seconds<=run.started+270,'list work reservation exhausted;cleanup/finalization retained'


def geometry(page,button):
    button.scroll_into_view_if_needed(timeout=15000)
    return button.evaluate("""e=>{const b=e.getBoundingClientRect(),s=e.querySelector('.record-reference'),r=document.createRange();r.selectNodeContents(s);
      const hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);
      return {viewport:innerWidth,document:document.documentElement.scrollWidth,x:b.x,right:b.right,
       height:b.height,lines:[...r.getClientRects()].map(x=>({x:x.x,right:x.right})),
       hit:!!hit&&(hit===e||e.contains(hit)),reference:s.textContent};}""")


def verify_geometry(row,width):
    assert row['viewport']==width and row['document']<=width
    assert row['height']>0 and row['x']>=-1 and row['right']<=width+1 and row['hit']
    assert row['lines'] and all(x['x']>=-1 and x['right']<=width+1 for x in row['lines'])
    if width==390:assert len(row['lines'])>=2,'full reference did not wrap in390px viewport'


def perform(run,ordinary,tmp_path):
    from playwright.sync_api import expect
    from test_case_step_assignments import prepared,ok
    from test_service_dispatches import offer,command
    from ordinary_case_step_support import ordinary_api
    from service_release_acceptance_support import authority_snapshot,case_history
    from scripts.fictional_park_restart_browser_once import verify_rendered_font
    f,_=ordinary
    report=run.report;report['stage']='SYNTHETIC_INITIAL_DATA'
    records=[]
    for _ in range(2):
        require_time(run)
        p=prepared(f,label='SYNTHETIC 同名资料办理')
        d=ok(offer(f,p)[0],201);d=ok(command(f,d,'ACCEPT'))
        assert d['current_offer']['state']=='ACCEPTED'
        r=ok(f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers={'Authorization':'Bearer '+f[2]['fixture-a']}))
        assert r['step']['state']=='AWAITING_RECEIPT'
        records.append(dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],
            dispatch_id=d['dispatch_id'],receipt_step_id=d['receipt_step_id']))
    assert all(records[0][key]!=records[1][key] for key in records[0])
    report.update(records=records,initial_data='Owned existing SYNTHETIC fixture/API commands before browser;not browser intake or formal source',
        lists=[],font_observations=[],denials=[],browser_writes=0)
    authority=authority_snapshot(f[1]);before=[case_history(f[1],r['preparation_id']) for r in records]
    run.secrets.extend(f[2].values())
    with ordinary_api(f,tmp_path/'api') as api:
        origin=str(api.base_url).rstrip('/');report['origin']=origin
        context=run.browser.new_context(viewport=dict(width=390,height=1000),service_workers='block')
        boundary=base.Boundary(origin,report);context.route('**/*',boundary.route)
        context.on('response',lambda response:report['responses'].append(dict(stage=report['stage'],method=response.request.method,path=urlsplit(response.url).path,status=response.status)))
        context.on('page',lambda page:page.on('pageerror',lambda error:report['page_errors'].append(str(error))))
        page=context.new_page();page.set_default_timeout(15000)
        def shot(name):
            assert name in NAMES
            path=run.public/name;page.screenshot(path=str(path),mask=[page.locator('#token')],timeout=10000)
            report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest()))
        def listing(kind):
            page.locator('[data-tab="collaboration"]').click()
            path={'preparation':'/api/preparations','dispatch':'/api/service-dispatches','receipt':'/api/executor-receipts'}[kind]
            prefix={'preparation':'prep','dispatch':'dispatch','receipt':'receipt'}[kind]
            with page.expect_response(lambda r:urlsplit(r.url).path==path and r.request.method=='GET') as response:
                page.locator('#'+prefix+'-list').click()
            assert response.value.status==200
            items=response.value.json()['items'];assert len(items)==2 and items[0]['goal']==items[1]['goal']
            if kind!='dispatch':assert items[0]['state']==items[1]['state']
            expect(page.locator('#'+prefix+'-items button')).to_have_count(2,timeout=15000)
            return prefix,items
        try:
            response=page.goto(origin,wait_until='load')
            assert response.status==200 and response.body()==(base.ROOT/'src/parkweave/web.html').read_bytes()
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            page.locator('#token').fill(f[2]['fixture-a'])
            for width in (390,1200):
                page.set_viewport_size(dict(width=width,height=1000))
                for kind in ('preparation','dispatch','receipt'):
                    require_time(run);report['stage']=f'{kind.upper()}_{width}'
                    prefix,items=listing(kind)
                    row=dict(kind=kind,width=width,items=items,buttons=[],opened=[]);report['lists'].append(row)
                    id_key={'preparation':'preparation_id','dispatch':'dispatch_id','receipt':'receipt_step_id'}[kind]
                    for record in records:
                        button=page.locator('#'+prefix+'-items button').filter(has_text=record[id_key])
                        expect(button).to_have_count(1)
                        proof=geometry(page,button);row['buttons'].append(proof);verify_geometry(proof,width)
                        assert record[id_key] in proof['reference']
                        if kind=='preparation':assert record['case_id'] in proof['reference']
                        if kind=='dispatch':assert record['preparation_id'] in proof['reference']
                    if width==390:
                        selected=report['installed_CJK_font'];selected['visible_node_font_usage']=[];selected['rendering_observed']=False
                        observation=dict(stage=report['stage'],complete=False,nodes=[]);report['font_observations'].append(observation)
                        try:verify_rendered_font(page,report);observation['complete']=True
                        finally:
                            observation['nodes']=deepcopy(selected.get('visible_node_font_usage',[]))
                            selected['rendering_observation_scope']='Actual390px list viewport text-node parents only;not all683 pixel acceptance'
                    number={(390,'preparation'):1,(390,'dispatch'):2,(390,'receipt'):3,(1200,'preparation'):4,(1200,'dispatch'):5,(1200,'receipt'):6}[width,kind]
                    shot(f'{number:02}-{kind}-{width}.png')
                    for record in records:
                        require_time(run)
                        prefix,_=listing(kind)
                        button=page.locator('#'+prefix+'-items button').filter(has_text=record[id_key])
                        proof=geometry(page,button);verify_geometry(proof,width)
                        target={'preparation':'/api/preparations/'+record['preparation_id'],
                            'dispatch':'/api/preparations/'+record['preparation_id']+'/dispatch',
                            'receipt':'/api/executor-receipts/'+record['receipt_step_id']}[kind]
                        with page.expect_response(lambda r:urlsplit(r.url).path==target and r.request.method=='GET') as observed:button.click()
                        assert observed.value.status==200
                        if kind=='preparation':
                            page.wait_for_function('id=>preparationView?.preparation.id===id&&preparationReadReady()',arg=record['preparation_id'])
                            view=page.evaluate('({preparation_id:preparationView.preparation.id,case_id:preparationView.preparation.case_id,run_id:preparationView.preparation.run_id})')
                        elif kind=='dispatch':
                            page.wait_for_function('id=>dispatchView?.dispatch_id===id',arg=record['dispatch_id'])
                            view=page.evaluate('({dispatch_id:dispatchView.dispatch_id,preparation_id:dispatchView.preparation_id,case_id:dispatchView.case_id,run_id:dispatchView.run_id})')
                        else:
                            page.wait_for_function('id=>receiptView?.step.id===id',arg=record['receipt_step_id'])
                            view=page.evaluate('({receipt_step_id:receiptView.step.id,preparation_id:receiptView.step.preparation_id,case_id:receiptView.step.case_id,run_id:receiptView.step.run_id})')
                        assert all(view[k]==v for k,v in record.items() if k in view)
                        row['opened'].append(dict(target=target,status=200,view=view,geometry=proof))
            assert authority_snapshot(f[1])==authority
            assert [case_history(f[1],r['preparation_id']) for r in records]==before
            require_time(run,45)
            # Explicit owned synthetic negative fixture change; no new Grant or
            # role, no restoration, no browser/API business write.
            report['stage']='READ_REVOKED_SAME_IDENTITY'
            with f[1].connect() as c:
                changed=c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ' AND active RETURNING principal_id").fetchall()
                assert len(changed)==1
            report['fixture_revocation']='One existing synthetic owner READ grant revoked after positive reads;no restoration'
            original_token=page.locator('#token').input_value()
            with page.expect_response(lambda r:urlsplit(r.url).path=='/api/executor-receipts/'+records[-1]['receipt_step_id']) as denial:
                page.locator('#receipt-refresh').click()
            assert denial.value.status==403
            assert page.locator('#token').input_value()==original_token
            expect(page.locator('#receipt-detail')).to_be_hidden()
            for prefix in ('prep','dispatch','receipt'):expect(page.locator('#'+prefix+'-items')).to_be_empty()
            expect(page.locator('#receipt-current')).to_be_empty()
            assert page.evaluate('preparationView===null&&dispatchView===null&&receiptView===null')
            report['denials'].append(dict(kind='SAME_IDENTITY_CURRENT_READ_REVOCATION',status=403,private_views_and_lists_cleared=True,identity_changed=False))
            page.set_viewport_size(dict(width=390,height=1000));page.locator('#page-feedback').scroll_into_view_if_needed();shot('07-read-denied.png')
            assert [case_history(f[1],r['preparation_id']) for r in records]==before
            report['declared_business_history_unchanged']=True
            assert not report['violations'] and not report['page_errors']
            assert all(x['method'] in ('GET','HEAD') for x in report['responses'])
            report['stage']='READ_ONLY_LISTS_AND_REVOCATION_COMPLETE'
            require_time(run,0)
            report['work_completion_seconds']=round(time.monotonic()-run.started,3)
        except BaseException:
            try:
                path=run.public/'failure-list-browser.png';page.screenshot(path=str(path),mask=[page.locator('#token')],timeout=10000)
            except BaseException as error:report['failure_screenshot_error']=type(error).__name__
            raise
        finally:context.close()
    report['API_process_observation']=json.loads((tmp_path/'api/process.json').read_text())
    assert report['API_process_observation'][-1]['owned_child_exit'] is not None
    with socket.socket() as s:assert s.connect_ex((urlsplit(origin).hostname,urlsplit(origin).port))==111
    report['API_listener_refused_after_owned_stop']=True


def main():
    import pytest
    os.umask(0o077)
    report=dict(status='NOT_RUN',scope='REAL_BROWSER_SAME_NAMED_SYNTHETIC_LISTS',stage='HOST_GATE',
        screenshots=[],responses=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False)
    class Run:
        def pytest_configure(self,config):config._record_list_browser=self
        @pytest.hookimpl(hookwrapper=True)
        def pytest_fixture_setup(self,fixturedef,request):
            outcome=yield
            if fixturedef.argname=='pg' and not outcome.excinfo:self.pg=outcome.get_result()
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self,item,call):
            outcome=yield
            if outcome.get_result().failed and call.excinfo is not None:
                report.setdefault('pytest_failures',[]).append(dict(when=call.when,error_type=call.excinfo.typename,
                    error=str(call.excinfo.value),frames=[dict(file=str(frame.path),line=frame.lineno+1,name=frame.name) for frame in call.excinfo.traceback]))
    run=Run();run.report=report;run.secrets=[];run.public=None;run.pg=None;run.started=time.monotonic()
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='10')
        PRIVATE.mkdir(mode=0o700,parents=True,exist_ok=False)
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            path=PRIVATE/name;path.mkdir(mode=0o700);env[key]=str(path)
        from scripts.fictional_park_restart_browser_once import installed_font_environment
        report['stage']='INSTALLED_CJK_PREFLIGHT'
        env=installed_font_environment(env,PRIVATE/'installed-fonts',report)
        from playwright.sync_api import sync_playwright
        report['stage']='CHROME_SANDBOX'
        with sync_playwright() as pw:
            with pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=env) as browser:
                run.browser=browser;report.update(real_browser=True,chrome_version=browser.version)
                base.resource.verify_sandbox(browser,report)
                report['stage']='PYTEST_FIXTURE_AND_PAGE_WALK'
                with (PRIVATE/'pytest.stdout').open('w') as out,(PRIVATE/'pytest.stderr').open('w') as err,redirect_stdout(out),redirect_stderr(err):
                    code=pytest.main(['-q','--tb=short','--disable-warnings','--basetemp',str(PRIVATE/'pytest'),str(base.ROOT/'tests/test_record_list_actual_browser.py')],plugins=[run])
                report['focused_pytest_exit']=int(code)
                assert code==0,'focused browser test failed;original private pytest output retained'
        report['status']='PASS'
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        if run.pg is not None:
            try:
                report['cleanup_stage']='OWNED_FIXTURE_POSTGRES_STOP'
                process=run.pg._postmaster_info.process
                run.pg.cleanup()
                assert not (run.pg.pgdata/'postmaster.pid').exists()
                import psutil
                assert not process.is_running() or process.status()==psutil.STATUS_ZOMBIE
                report['owned_fixture_postgres_stopped']=True
            except BaseException as error:base.finalization_failure(report,error)
    report['seconds']=round(time.monotonic()-run.started,3)
    return base.finish_report(report,run.secrets,run.public,started=run.started,allowed_names=PUBLIC_FILES)


if __name__=='__main__':raise SystemExit(main())
