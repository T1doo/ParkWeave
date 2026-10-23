"""One installed synthetic A completion/B independent reuse,39 original DOM POSTs.

Two sequential90s browser supervisors share one270s work clock and one API/PG.
No API preparation writes, automatic VERIFY, second setup or external business.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,os,re,signal,subprocess,sys,tempfile,time,math
from contextlib import contextmanager
from functools import wraps
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from scripts import guide_installed_browser_once as guide
from scripts.visual_owned_launch import atomic_report,supervise

installed=guide.installed;source=guide.source;tail=guide.tail;base=guide.base;ROOT=guide.ROOT
RUN='32';MODULE='scripts.full_guide_installed_browser_once'
SHOTS={'01-A-local-approved.png','02-A-executor-receipt.png','03-A-five-local-verified.png','04-B-independent-reuse.png'}
TEXTS={'A-local-verified-case.txt','B-unfinished-case.txt'}
PUBLIC=SHOTS|TEXTS|{'failure-guide.png','result.json','installation-redacted.log',installed.WHEEL_NAME}
failed=guide.failed

# Diagnostic metadata only. Never checkpoint the full worker report: it contains
# original request/response bodies and private installation/session paths.
PROGRESS_LIMIT=512*1024
ACTORS={'enterprise','specialist','executor'}
KINDS={'OPEN','CLICK','POST','ROLE','LIST_OPEN','WAIT_READY','WAIT_IDLE','WAIT_VIEW',
       'VERIFY','RESOURCES','DISPATCH_OPEN','COMPLETE','INTAKE','EXPORT','CLOSE'}
SEGMENTS=set('api runs preparations commands request-intent service-selections service-case-plan material-reuse resource-delivery preview plan-approval proposals synthetic-resources holds dispatch service-dispatches executor-receipts local-case catalog mine resources combinations run-access status result events goals goal-results case-record-pack current facts fact-clarifications evidence materials candidates service-selection service-selection-catalog service-capabilities delivery receipts entry receipt-steps'.split())
STAGE=re.compile(r'(?:ADMIT_[AB]|PHASE_[AB]_(?:CHROME_LAUNCH|ORIGINAL_GUIDE|COMPLETE|DOM_(?:VERIFY|APPROVE|REVIEW|CONFIRM|ADD_EVIDENCE|SUBMIT|ACKNOWLEDGE|ACCEPT|REVALIDATE|CLOSE_LOCAL_RECORD|commands|request-intent|material-reuse|service-selections|service-case-plan|preview|holds|proposals|resource-delivery|dispatch))|A_AFTER_B_READ_ONLY)\Z')


def progress_atomic(path,value):
    """A short/failed temporary write must leave the previous snapshot intact."""
    data=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    if len(data)>PROGRESS_LIMIT:raise ValueError('progress size limit')
    fd,name=tempfile.mkstemp(prefix='.partial-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            if stream.write(data)!=len(data):raise OSError('short progress write')
            stream.flush();os.fsync(stream.fileno())
        if Path(name).read_bytes()!=data:raise OSError('truncated progress temporary')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def progress_identity(config):
    value=dict(source_sha=config['report']['source_sha'],run_number=RUN,phase=config['phase'],invocation=config['progress_invocation'])
    assert re.fullmatch('[0-9a-f]{40}',value['source_sha']) and value['phase'] in ('A','B')
    assert re.fullmatch('[0-9a-f]{32}',value['invocation'])
    return value


class Progress:
    def __init__(self,run,config,segment_started):
        self.run=run;self.path=Path(config['progress_path']);self.segment_started=segment_started
        self.value=dict(schema='BROWSER_PARTIAL_PROGRESS_V1',**progress_identity(config),state='PARTIAL',worker_final=False,
            outcome='UNKNOWN',sequence=0,root_elapsed=0,segment_elapsed=0,stage='UNKNOWN',actions=[],requests=[],
            in_flight_actions=[],last_completed_action=None,checkpoint_errors=[])
        self.request_ids={};self.request_refs=[];self.save()
    def save(self):
        try:
            v=self.value;v['sequence']+=1
            v['root_elapsed']=round(time.monotonic()-self.run.started,6);v['segment_elapsed']=round(time.monotonic()-self.segment_started,6)
            stage=self.run.report.get('stage','');v['stage']=stage if STAGE.fullmatch(stage) else 'UNKNOWN'
            assert len(v['actions'])<=1024 and len(v['requests'])<=400
            assert all(x['actor'] in ACTORS|{None} for x in v['actions'])
            progress_atomic(self.path,v)
            self.run.report['progress_reference']=dict(sequence=v['sequence'],sha256=sha256(self.path.read_bytes()).hexdigest(),**{k:v[k] for k in ('phase','invocation','worker_final','outcome')})
        except Exception as e:
            # Preserve the original business error, and fail normal finalization
            # if any diagnostic update failed. Never persist exception text.
            item=dict(error_type=type(e).__name__ if type(e).__name__ in {'AssertionError','TimeoutError','OSError','RuntimeError','ValueError'} else 'OTHER',sequence=self.value['sequence'])
            self.run.report['progress_error_count']=self.run.report.get('progress_error_count',0)+1
            self.run.report['progress_errors']=(self.run.report.get('progress_errors',[])+[item])[-16:]
            self.value['checkpoint_errors']=self.run.report['progress_errors']
    @contextmanager
    def action(self,kind,selector=None,target_actor=None):
        assert kind in KINDS
        rows=self.value['actions'];stack=self.value['in_flight_actions'];n=len(rows)+1
        row=dict(id=n,parent=stack[-1] if stack else None,kind=kind,actor=getattr(self.run,'diagnostic_actor',None),state='IN_FLIGHT',started_root=round(time.monotonic()-self.run.started,6))
        if selector is not None:
            assert isinstance(selector,str) and len(selector)<=1024
            row['selector_sha256']=sha256(selector.encode()).hexdigest()
        if target_actor is not None:
            assert kind=='ROLE' and target_actor in ACTORS
            row['target_actor']=target_actor
        rows.append(row);stack.append(n);self.save()
        try:yield
        except BaseException as e:
            row.update(state='ERROR',error_type=type(e).__name__ if type(e).__name__ in {'AssertionError','TimeoutError','Error','OSError','RuntimeError','ValueError','KeyboardInterrupt'} else 'OTHER');raise
        else:row['state']='RETURNED';self.value['last_completed_action']=n
        finally:row['ended_root']=round(time.monotonic()-self.run.started,6);stack.pop();self.save()
    def request(self,req):
        identity=id(getattr(req,'_impl_obj',req))
        if identity in self.request_ids:return self.request_ids[identity]
        parts=urlsplit(req.url).path.split('/');safe=[];known=True
        for part in parts:
            if not part:safe.append('')
            elif re.fullmatch('[0-9a-fA-F-]{36}',part):safe.append(':id')
            elif part in SEGMENTS:safe.append(part)
            else:safe.append(':redacted');known=False
        method=req.method if req.method in ('GET','POST') else 'OTHER'
        key=req.headers.get('idempotency-key');key=key if isinstance(key,str) and re.fullmatch('[0-9a-f-]{36}',key) else None
        row=dict(id=len(self.value['requests'])+1,action=self.value['in_flight_actions'][-1] if self.value['in_flight_actions'] else None,
            method=method,route='/'.join(safe)[:256],target_sha256=sha256(urlsplit(req.url).path.encode()).hexdigest() if known else None,
            key_sha256=sha256(key.encode()).hexdigest() if key else None,state='OBSERVED',observed_root=round(time.monotonic()-self.run.started,6),
            response_status=None,body_state='UNKNOWN',business_outcome='UNKNOWN')
        self.request_ids[identity]=row;self.request_refs.append(req);self.value['requests'].append(row);self.save();return row
    def update_request(self,req,**fields):
        row=self.request(req);row.update(fields);self.save()
    def finish(self):
        self.value.update(worker_final=True,outcome=self.run.report['status'],state='COMPLETE' if self.run.report['status']=='PASS' else 'PARTIAL');self.save()


def traced(kind):
    def decorate(fn):
        @wraps(fn)
        def call(self,*args,**kwargs):
            progress=getattr(self.run,'progress',None)
            if progress is None:return fn(self,*args,**kwargs)
            with progress.action(kind,args[0] if args and kind in ('POST','WAIT_VIEW') else None,args[0] if args and kind=='ROLE' else None):return fn(self,*args,**kwargs)
        return call
    return decorate


def recover_progress(report,config,final=None,previous=None):
    """Import metadata independently; it cannot replace root errors or authorize B."""
    path=Path(config['progress_path']);data=path.read_bytes()
    assert len(data)<=PROGRESS_LIMIT
    v=json.loads(data);assert v['schema']=='BROWSER_PARTIAL_PROGRESS_V1'
    assert all(v[k]==x for k,x in progress_identity(config).items())
    assert type(v['sequence']) is int and 0<v['sequence']<=16384
    assert all(type(v[k]) in (float,int) and math.isfinite(v[k]) and 0<=v[k]<=360 for k in ('root_elapsed','segment_elapsed'))
    assert len(v['actions'])<=1024 and len(v['requests'])<=400
    assert [x['id'] for x in v['actions']]==list(range(1,len(v['actions'])+1))
    assert [x['id'] for x in v['requests']]==list(range(1,len(v['requests'])+1))
    fingerprint=sha256(data).hexdigest()
    if previous is not None:
        assert v['sequence']>=previous['sequence']
        if v['sequence']==previous['sequence']:assert fingerprint==previous['sha256']
        assert all(v[k]>=previous[k] for k in ('root_elapsed','segment_elapsed'))
    # Only this strict projection crosses into a root/public report. Reject
    # unexpected fields instead of importing arbitrary full-page/session data.
    assert set(v)=={'schema','source_sha','run_number','phase','invocation','state','worker_final','outcome','sequence','root_elapsed','segment_elapsed','stage','actions','requests','in_flight_actions','last_completed_action','checkpoint_errors'}
    assert v['state'] in ('PARTIAL','COMPLETE') and type(v['worker_final']) is bool and v['outcome'] in ('UNKNOWN','FAIL','PASS')
    assert v['stage']=='UNKNOWN' or STAGE.fullmatch(v['stage'])
    for row in v['actions']:
        assert set(row)<={'id','parent','kind','actor','target_actor','state','started_root','ended_root','error_type','selector_sha256'}
        assert row['kind'] in KINDS and row['actor'] in ACTORS|{None} and row['state'] in ('IN_FLIGHT','RETURNED','ERROR')
        assert row['parent'] is None or type(row['parent']) is int and 0<row['parent']<row['id']
        assert ('ended_root' in row)==(row['state']!='IN_FLIGHT')
        if 'target_actor' in row:assert row['kind']=='ROLE' and row['target_actor'] in ACTORS
    for row in v['requests']:
        assert set(row)<={'id','action','method','route','target_sha256','key_sha256','state','observed_root','response_status','body_state','business_outcome','continued_root','response_root','error_type'}
        assert row['method'] in ('GET','POST','OTHER') and row['state'] in ('OBSERVED','AUTHORIZED','CONTINUED','REJECTED','CONTINUE_ERROR')
        assert row['business_outcome']=='UNKNOWN' and row['body_state'] in ('UNKNOWN','OBSERVER_RETURNED','READ_ERROR')
        assert row['action'] is None or type(row['action']) is int and 0<row['action']<=len(v['actions'])
        assert row['response_status'] is None or type(row['response_status']) is int and 100<=row['response_status']<=599
        assert all(part in SEGMENTS|{'',':id',':redacted'} for part in row['route'].split('/')) and len(row['route'])<=256
    for row in v['actions']+v['requests']:
        for key,value in row.items():
            if key.endswith('_sha256'):assert value is None or isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value)
            if key.endswith('_root'):assert type(value) in (int,float) and math.isfinite(value) and 0<=value<=360
            if key=='error_type':assert value in {'AssertionError','TimeoutError','Error','OSError','RuntimeError','ValueError','KeyboardInterrupt','OTHER'}
    assert all(set(x)=={'sequence','error_type'} and type(x['sequence']) is int and 0<x['sequence']<=v['sequence'] and x['error_type'] in {'AssertionError','TimeoutError','OSError','RuntimeError','ValueError','OTHER'} for x in v['checkpoint_errors']) and len(v['checkpoint_errors'])<=16
    assert v['in_flight_actions']==[x['id'] for x in v['actions'] if x['state']=='IN_FLIGHT']
    assert v['last_completed_action'] is None or any(x['id']==v['last_completed_action'] and x['state']=='RETURNED' for x in v['actions'])
    if not v['worker_final']:assert v['state']=='PARTIAL' and v['outcome']=='UNKNOWN'
    if v['worker_final']:assert v['outcome'] in ('PASS','FAIL') and v['state']==('COMPLETE' if v['outcome']=='PASS' else 'PARTIAL')
    if v['outcome']=='PASS':assert v['worker_final'] and v['state']=='COMPLETE' and not v['checkpoint_errors'] and not v['in_flight_actions']
    if final is not None:
        ref=final['progress_reference'];assert all(ref[k]==x for k,x in dict(sequence=v['sequence'],sha256=fingerprint,phase=v['phase'],invocation=v['invocation'],worker_final=v['worker_final'],outcome=v['outcome']).items())
        assert v['worker_final'] and final.get('browser_worker_final')==config['phase'] and final['status']==v['outcome']
        assert not final.get('progress_errors')
    report.setdefault('partial_progress',{})[config['phase']]=v
    return dict(sequence=v['sequence'],sha256=fingerprint,root_elapsed=v['root_elapsed'],segment_elapsed=v['segment_elapsed'])


def snapshot(run):
    """Only this Case's named records. B's legitimate new rows are not compared."""
    result=source.snapshot(run);id=run.record['preparation_id']
    with source.owner(run) as c:
        c.execute('SET TRANSACTION READ ONLY')
        result['case']=c.execute('SELECT * FROM cases WHERE id=%s',(run.record['case_id'],)).fetchone()
        for name in ('preparation_evidence','preparation_events','service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE preparation_id=%s ORDER BY id',(id,)).fetchall() if name not in ('case_local_lifecycles',) else c.execute('SELECT * FROM '+name+' WHERE preparation_id=%s',(id,)).fetchall()
        for name in ('service_dispatch_offers','service_dispatch_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE dispatch_id IN (SELECT id FROM service_dispatches WHERE preparation_id=%s) ORDER BY id',(id,)).fetchall()
        for name in ('service_step_receipts','service_receipt_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE step_id IN (SELECT id FROM service_receipt_steps WHERE preparation_id=%s) ORDER BY id',(id,)).fetchall()
    return json.loads(json.dumps(result,default=str,sort_keys=True))


class Budget(guide.Budget):
    def __init__(self,run):
        super().__init__(run)
        self.posts=len(run.report.get('DOM_write_requests',[]));self.reads=run.report.get('request_budget',{}).get('main_GET',0)
        self.keys={x['key'] for x in run.report.get('DOM_write_requests',[]) if x['key'] is not None}
    def route(self,route):
        req=route.request;url=urlsplit(req.url);origin=urlsplit(self.run.report['origin'])
        progress=getattr(self.run,'progress',None)
        if progress:progress.request(req)
        continue_entered=False
        try:
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.username and not url.password
            assert url.path in ('/','/demo','/favicon.ico') or url.path.startswith('/api/')
            if req.method=='GET':assert self.reads<360;self.reads+=1
            else:
                assert req.method=='POST' and not url.query and not self.readonly and self.queue
                assert self.posts<(30 if self.run.phase=='A' else 39)
                path,action,actor=self.queue[0];body=req.post_data_json
                assert url.path==path and req.headers.get('authorization')=='Bearer '+self.run.tokens[actor]
                assert action is None or body.get('action')==action
                preview=path.endswith('/preview');key=req.headers.get('idempotency-key')
                if preview:assert key is None
                else:
                    assert key and re.fullmatch('[0-9a-f-]{36}',key) and key not in self.keys;self.keys.add(key)
                self.posts+=1;self.queue.pop(0)
                self.run.report.setdefault('DOM_write_requests',[]).append(dict(phase=self.run.phase,path=path,action=action,actor=actor,key=key,preview=preview,body=body))
            if progress:progress.update_request(req,state='AUTHORIZED')
            continue_entered=True
            route.continue_()
            if progress:progress.update_request(req,state='CONTINUED',continued_root=round(time.monotonic()-self.run.started,6))
        except BaseException as e:
            if progress:progress.update_request(req,state='CONTINUE_ERROR' if continue_entered else 'REJECTED',
                error_type=type(e).__name__ if type(e).__name__ in {'AssertionError','TimeoutError','Error','OSError','RuntimeError','ValueError','KeyboardInterrupt'} else 'OTHER')
            self.run.report['violations'].append(dict(method=req.method,path=url.path,error_type=type(e).__name__));route.abort();raise
        finally:
            self.run.report['request_budget']=dict(POST=self.posts,DOM_POST=self.posts,API_PREPARATION_POST=0,main_GET=self.reads,
                readiness_attempts=self.run.ready,GET=self.reads+self.run.ready,ceilings=dict(POST=40,DOM_POST=39,API_PREPARATION_POST=0,main_GET=360,readiness=40,GET=400,business_worker_once=2,browser_supervisor_segments=2))


class Walk(guide.Walk):
    @traced('OPEN')
    def open(self):return super().open()
    @traced('ROLE')
    def role(self,actor):
        assert actor in ACTORS
        # Actor is only the UI selection observed after the original token
        # equality assertion, never a claim of authority for a pending switch.
        value=super().role(actor);self.run.diagnostic_actor=actor;return value
    def click(self,page,selector):
        progress=getattr(self.run,'progress',None)
        if progress is None:return super().click(page,selector)
        with progress.action('CLICK',selector):return super().click(page,selector)
    def observed(self,response):
        progress=getattr(self.run,'progress',None);req=response.request
        if progress:progress.update_request(req,response_status=response.status,response_root=round(time.monotonic()-self.run.started,6))
        try:super().observed(response)
        except BaseException:
            if progress:progress.update_request(req,body_state='READ_ERROR')
            raise
        else:
            if progress:progress.update_request(req,body_state='OBSERVER_RETURNED')
    @traced('WAIT_READY')
    def ready(self):return super().ready()
    @traced('WAIT_VIEW')
    def wait(self,*args,**kwargs):return self.w.wait_for_function(*args,**kwargs)
    @traced('CLOSE')
    def close(self,primary=None):return super().close(primary)
    @traced('POST')
    def post(self,selector,path,*,action=None,status=200):
        self.run.report['current_control']=dict(phase=self.run.phase,selector=selector,path=path,action=action,actor=self.actor)
        self.run.report['stage']='PHASE_'+self.run.phase+'_DOM_'+(action or path.rsplit('/',1)[-1])
        return super().post(selector,path,action=action,status=status)
    @traced('LIST_OPEN')
    def existing(self):
        self.click(self.w,'[data-tab="collaboration"]');self.click(self.w,'#prep-list')
        button=self.w.locator('#prep-items>button').filter(has_text=self.run.record['goal']);self.expect(button).to_have_count(1)
        button.scroll_into_view_if_needed(timeout=15000);button.click();self.ready()
        p=self.w.evaluate('preparationView.preparation')
        assert all(p[k]==self.run.record[v] for k,v in (('id','preparation_id'),('case_id','case_id'),('run_id','run_id')))
    @traced('WAIT_IDLE')
    def idle(self):
        self.wait('()=>!servicePlanPending&&!planApprovalBusy&&!deliveryBusy&&!bundleBusy&&!dispatchAcceptBusy&&!receiptSubmitBusy&&!localCaseRecoveryBusy&&!activeEntryWriteFlow&&entryWriteRequests.size===0&&!originalStoredWritePending()',timeout=30000)
    def shot(self,name,selector,page=None):
        assert name in SHOTS;page=page or self.w;page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        path=self.run.public/name;page.screenshot(path=str(path),mask=[page.locator('#token')] if page is self.w else [page.locator('#sessions')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest(),viewport=page.viewport_size))
    @traced('VERIFY')
    def verify(self,adapter):
        assert self.actor=='enterprise';self.existing();self.click(self.w,'#service-plan-prepare')
        self.wait('(id)=>servicePlanView?.plan_id===id&&!servicePlanPending',arg=self.run.record['plan_id'],timeout=30000)
        self.w.locator('#service-plan-reason').fill('SYNTHETIC 林岚在原入口明确核验本事项'+adapter)
        value=self.post('[data-service-adapter="'+adapter+'"] [data-service-action="VERIFY"]','/api/preparations/'+self.run.record['preparation_id']+'/service-case-plan/commands',action='VERIFY')
        assert next(x for x in value['steps'] if x['adapter_id']==adapter)['state']=='VERIFIED'
        self.run.report.setdefault('explicit_verifications',[]).append(dict(adapter=adapter,receipt=value['command_receipt']))
    @traced('EXPORT')
    def export(self,filename,verified=False,*,private=False):
        posts=self.run.budget.posts;self.click(self.w,'#service-plan-prepare');self.wait('()=>servicePlanView?.plan_id&&!servicePlanPending',timeout=30000)
        plan=self.w.evaluate('(fields)=>Object.fromEntries(fields.map(k=>[k,servicePlanView[k]]))',list(source.PLAN_FIELDS))
        assert plan['plan_id']==self.run.record['plan_id']
        assert [s['state'] for s in plan['steps']]==(['VERIFIED']*5 if verified else ['PENDING']+['BLOCKED']*4)
        self.click(self.w,'#goal-results-read');self.wait('()=>goalResultView!==null',timeout=30000);value=self.w.evaluate('goalResultView')
        tail.truth(value,self.run.record,['LOCAL_OUTPUT_VERIFIED']*5 if verified else ['AWAITING_OWNER_VERIFICATION']+['WAITING_DEPENDENCY']*4)
        self.click(self.w,'#case-record-pack-generate');self.wait('()=>caseRecordPackView!==null&&!caseRecordPackBusy',timeout=30000)
        text=self.w.locator('#case-record-pack-text').input_value();pack=guide.unpack(text,value)
        with self.w.expect_download(timeout=30000) as download:self.click(self.w,'#case-record-pack-download')
        assert download.value.failure() is None
        target=(self.run.private/'A-after-B-case.txt') if private else self.run.public/filename
        download.value.save_as(target);assert target.read_bytes()==text.encode() and len(text.encode())<=128*1024 and self.run.budget.posts==posts
        for secret in self.run.tokens.values():assert secret not in text and secret[:12] not in text
        self.run.report.setdefault('exports',[]).append(dict(phase=self.run.phase,file=None if private else filename,case=self.run.record['case_id'],goal_results=value,plan=plan,pack=pack,sha256=sha256(text.encode()).hexdigest(),bytes=len(text.encode()),business_POSTs=0))
        return text,value,plan
    @traced('INTAKE')
    def intake(self,reuse=False):
        w=self.w;run=self.run;self.click(w,'[data-tab="service"]');self.click(w,'#prep-catalog')
        self.guide.locator('#scenario').select_option('again' if reuse else 'first');w.locator('#prep-reviewer').select_option('ordinary-demo-specialist');self.click(self.guide,'#fill-goal')
        goal=w.locator('#prep-goal').input_value();run.budget.authorize(('/api/runs',None,'enterprise'),('/api/preparations',None,'enterprise'))
        with w.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/runs',timeout=30000) as created:self.click(w,'#prep-create button')
        assert created.value.status==202;installed.worker_once(run,0 if run.phase=='A' else 1);self.ready();assert not run.budget.queue
        p=w.evaluate('preparationView.preparation');run.record=dict(preparation_id=p['id'],case_id=p['case_id'],run_id=p['run_id'],goal=goal);path='/api/preparations/'+p['id']
        self.click(w,'#plan-prepare');self.click(self.guide,'#fill-request');self.post('#request-save',path+'/request-intent');self.click(w,'#plan-materials');self.ready()
        if reuse:
            assert w.evaluate('preparationView.current_materials.length')==0
            self.click(w,'#material-reuse-read');self.wait('()=>materialReuseView?.items.length===1',timeout=30000)
            item=w.evaluate('materialReuseView.items[0]');assert item['source_preparation_id']==run.report['records']['A']['preparation_id']
            w.locator('#material-reuse-source').select_option(item['source_evidence_id']);self.click(w,'#material-reuse-preview');self.wait('()=>materialReuseView?.source_preview',timeout=30000)
            w.locator('#material-reuse-purpose').check();w.locator('#material-reuse-reason').fill('SYNTHETIC 林岚明确同用途复制原生目录，本次新诉求独立审核')
            copied=self.post('#material-reuse-confirm',path+'/material-reuse',status=201);self.ready()
            proof=copied['material_reuse'];material=w.evaluate('preparationView.current_materials.find(x=>x.slot==="material_outline")')
            assert copied['preparation_id']==run.record['preparation_id'] and copied['state']=='IN_PREPARATION'
            assert proof['source_preparation_id']==item['source_preparation_id'] and proof['source_evidence_id']==item['source_evidence_id']
            assert proof['target_evidence_id']==material['id'] and material['id']!=item['source_evidence_id'] and proof['requires_independent_review'] is True
            assert material['version']==1 and sha256(material['text'].encode()).hexdigest()==material['source_sha256']==item['source_evidence_sha256']==proof['target_sha256']
            run.report['reuse']=dict(source=item,original_response=copied,actual_new_material=material)
        for button in (('#fill-need',) if reuse else ('#fill-need','#fill-outline')):
            self.click(self.guide,button);self.post('#prep-evidence button',path+'/commands',action='ADD_EVIDENCE');self.ready()
        self.role('specialist');self.existing();w.locator('#prep-reason').fill('SYNTHETIC 周禾独立核对本次新资料')
        reviewed=self.post('#prep-review',path+'/commands',action='REVIEW');self.ready()
        self.role('enterprise');self.existing();w.locator('#prep-reason').fill('SYNTHETIC 林岚独立确认本次新资料')
        confirmed=self.post('#prep-confirm',path+'/commands',action='CONFIRM');self.ready()
        events=[]
        with source.owner(run) as c:
            c.execute('SET TRANSACTION READ ONLY')
            for action,actor,response in (('REVIEW','ordinary-demo-specialist',reviewed),('CONFIRM','ordinary-demo-enterprise',confirmed)):
                request=next(x for x in run.report['DOM_write_requests'] if x['phase']==run.phase and x['action']==action)
                rows=c.execute('SELECT id,actor_id,request_key,action,payload FROM preparation_events WHERE preparation_id=%s AND request_key=%s',(run.record['preparation_id'],request['key'])).fetchall()
                assert len(rows)==1 and rows[0]['actor_id']==actor and rows[0]['action']==action and rows[0]['payload']==response
                assert response['preparation_id']==run.record['preparation_id'] and response['case_id']==run.record['case_id'] and response['run_id']==run.record['run_id']
                events.append(rows[0])
        run.report.setdefault('independent_material_decisions',{})[run.phase]=json.loads(json.dumps(events,default=str))
        self.click(w,'#service-plan-prepare');self.wait('()=>servicePlanView!==null',timeout=30000)
        self.click(w,'#service-selection-read');self.wait('()=>serviceSelectionCatalog!==null&&!serviceSelectionBusy',timeout=30000)
        selected=self.post('#service-selection-generate',path+'/service-selections',status=201)
        assert selected['producer']['mode']=='NO_MODEL' and selected['producer']['real_model_calls']==0
        w.locator('#service-selection-confirm').check();w.locator('#service-plan-reason').fill('SYNTHETIC 林岚明确采纳本次新候选，不继承其他Case核验')
        plan=self.post('#service-plan-adopt',path+'/service-case-plan',status=201);run.record['plan_id']=plan['plan_id']
        assert plan['candidate_consumption']['candidate_id']==selected['candidate_id'] and not any(e['action']=='VERIFY' for e in plan['events'])
        run.report.setdefault('records',{})[run.phase]=deepcopy(run.record)
        run.report.setdefault('candidates',{})[run.phase]=dict(candidate_id=selected['candidate_id'],candidate_sha256=selected['candidate_sha256'],plan_id=plan['plan_id'])
    @traced('RESOURCES')
    def resources(self):
        w=self.w;self.click(w,'[data-tab="resource"]');self.click(w,'#resource-catalog');self.wait('()=>bundleActor!==null',timeout=30000)
        ids=w.locator('#resource-select option').evaluate_all('rows=>rows.map(r=>r.value)');assert len(ids)==2
        now=datetime.now(timezone.utc);holds=[]
        for n,rid in enumerate((ids[0],ids[1],ids[0])):
            start=now+timedelta(hours=1 if n<2 else 4);end=start+timedelta(hours=1)
            w.locator('#resource-select').select_option(rid);w.locator('#resource-start').fill(start.strftime('%Y-%m-%dT%H:%M'));w.locator('#resource-end').fill(end.strftime('%Y-%m-%dT%H:%M'))
            w.locator('#resource-quantity').fill('1');w.locator('#resource-ttl').fill('300');w.locator('#resource-purpose').fill('SYNTHETIC 原页面本地演示占位'+str(n))
            q=self.post('#resource-preview','/api/synthetic-resources/'+rid+'/preview');assert q['available'] is True
            held=self.post('#resource-hold','/api/synthetic-resources/'+rid+'/holds',status=201);holds.append(held['hold']['id'])
        self.click(w,'#resource-mine');self.wait('()=>!bundleBusy',timeout=30000)
        for id in holds:w.locator('[data-combination-hold="'+id+'"]').check()
        w.locator('#delivery-case').fill(self.run.record['preparation_id']);path='/api/preparations/'+self.run.record['preparation_id']
        quote=self.post('#delivery-preview',path+'/resource-delivery/preview');assert quote['context']['plan_id']==self.run.record['plan_id']
        proposed=self.post('#plan-approval-propose',path+'/plan-approval/proposals',status=201);item=proposed['items'][-1];assert item['state']=='PROPOSED'
        approved=self.post('#plan-approval-approve',path+'/plan-approval/commands',action='APPROVE');assert approved['items'][-1]['id']==item['id'] and approved['items'][-1]['state']=='APPROVED'
        self.shot('01-A-local-approved.png','#plan-approval-panel')
        delivered=self.post('#delivery-confirm',path+'/resource-delivery',status=201)
        assert delivered['receipt']['plan_approval']['scope']=='LOCAL_CASE_RESOURCE_APPROVAL_V1' and delivered['receipt']['plan_approval']['id']==item['id'] and delivered['link']['revision']==1
        self.run.report['local_delivery']=dict(approval_id=item['id'],holds=holds,receipt=delivered['receipt'])
    @traced('DISPATCH_OPEN')
    def dispatch(self,id):
        self.click(self.w,'[data-tab="collaboration"]');self.click(self.w,'#dispatch-list')
        item=self.w.locator('#dispatch-items>button').filter(has_text=id);self.expect(item).to_have_count(1);item.click()
        self.wait('(id)=>dispatchView?.dispatch_id===id',arg=id,timeout=30000)
    @traced('COMPLETE')
    def complete(self):
        self.verify('P1');self.resources();self.verify('P2');path='/api/preparations/'+self.run.record['preparation_id'];w=self.w
        self.role('specialist');self.existing();self.click(w,'#dispatch-prepare')
        self.expect(w.locator('#dispatch-executor option')).to_have_count(1);w.locator('#dispatch-executor').select_option('ordinary-demo-executor');w.locator('#dispatch-offer-reason').fill('SYNTHETIC 周禾明确分派本事项')
        offered=self.post('#dispatch-offer-button',path+'/dispatch',status=201)
        self.role('executor');self.dispatch(offered['dispatch_id']);w.locator('#dispatch-decision-reason').fill('SYNTHETIC 许辰本人明确接责')
        accepted=self.post('#dispatch-accept','/api/service-dispatches/'+offered['dispatch_id']+'/commands',action='ACCEPT');self.run.report['accepted_dispatch']=accepted
        self.role('enterprise');self.verify('P3');self.role('executor');self.dispatch(offered['dispatch_id']);self.click(w,'#dispatch-receipt')
        w.locator('#receipt-text').fill('SYNTHETIC 许辰为虚构云杉企业整理本次巡检办理记录；无外部履约。');w.locator('#receipt-source').fill('SYNTHETIC 青禾园本地原办理记录')
        receipt_path='/api/executor-receipts/'+accepted['receipt_step_id']+'/commands';self.post('#receipt-submit-button',receipt_path,action='SUBMIT')
        self.shot('02-A-executor-receipt.png','#receipt-current')
        self.role('enterprise');self.click(w,'[data-tab="collaboration"]');self.click(w,'#receipt-list')
        item=w.locator('#receipt-items>button').filter(has_text=accepted['receipt_step_id']);self.expect(item).to_have_count(1);item.click()
        self.wait('(id)=>receiptView?.step.id===id',arg=accepted['receipt_step_id'],timeout=30000);w.locator('#receipt-reason').fill('SYNTHETIC 林岚本人明确核对原回执全文')
        self.post('#receipt-ack',receipt_path,action='ACKNOWLEDGE');self.verify('P4');self.existing();self.click(w,'#local-case-prepare')
        self.wait('()=>localCaseView?.can_revalidate===true',timeout=30000)
        w.locator('#local-case-reason').fill('SYNTHETIC 林岚本人明确重新校验本轮本地记录');self.post('#local-case-validate',path+'/local-case/commands',action='REVALIDATE')
        w.locator('#local-case-reason').fill('SYNTHETIC 林岚明确关闭本地记录，不证明真实履约');self.post('#local-case-close',path+'/local-case/commands',action='CLOSE_LOCAL_RECORD');self.verify('P5')


def phase_flow(run,browser):
    walk=Walk(run,browser,1200 if run.phase=='A' else 390);error=None
    try:
        run.report['stage']='PHASE_'+run.phase+'_ORIGINAL_GUIDE';run.progress.save();walk.open();walk.intake(reuse=run.phase=='B')
        if run.phase=='A':
            walk.complete();original=walk.export('A-local-verified-case.txt',True);walk.shot('03-A-five-local-verified.png','#goal-results-status');walk.font('A_FIVE_VERIFIED')
            assert run.budget.posts==30;run.report['A_sealed_snapshot']=snapshot(run)
            run.report['A_export_signature']=dict(sha256=sha256(original[0].encode()).hexdigest(),goal_results=original[1],plan=original[2])
        else:
            a=run.report['records']['A'];b=run.report['records']['B']
            assert all(a[k]!=b[k] for k in ('preparation_id','case_id','run_id','plan_id','goal'))
            assert run.report['candidates']['A']['candidate_id']!=run.report['candidates']['B']['candidate_id']
            walk.export('B-unfinished-case.txt');walk.shot('04-B-independent-reuse.png','#goal-results-status');walk.font('B_UNFINISHED')
            assert run.budget.posts==39;run.budget.readonly=True;run.record=deepcopy(a);run.report['stage']='A_AFTER_B_READ_ONLY';run.progress.save()
            walk.existing();original=walk.export('A-local-verified-case.txt',True,private=True);signature=run.report['A_export_signature']
            assert original[1]==signature['goal_results'] and original[2]==signature['plan'] and sha256(original[0].encode()).hexdigest()==signature['sha256']
            after=snapshot(run);assert after==run.report['A_sealed_snapshot']
            run.report['A_after_B']=dict(named_projection_after=after,goal_plan_TXT_equal=True,business_POSTs=0,
                excluded_B_rows='B Case,Run,preparation,evidence/events,candidate,plan are legitimate distinct new records;not wholeDB comparison')
    except BaseException as e:error=e;failed(run.report,e);run.progress.save();raise
    finally:walk.close(error)


def browser_worker(config,started):
    run=SimpleNamespace(**config)
    for k in ('private','public','harness','state','python'):setattr(run,k,Path(getattr(run,k)))
    run.tokens={k:v for k,v in json.loads((run.state/'sessions.json').read_text()).items() if k in ('enterprise','specialist','executor')};run.budget=Budget(run);report=run.report
    run.progress=Progress(run,config,started)
    def alarm(*_):raise TimeoutError('85s segment operation reached cleanup reserve')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(max(1,int(85-(time.monotonic()-started))))
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            report['stage']='PHASE_'+run.phase+'_CHROME_LAUNCH';run.progress.save()
            try:browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=config['chrome_env'],timeout=15000)
            except BaseException as e:failed(report,e);atomic_report(Path(config['browser_result']),report);raise
            try:report['chrome_version']=browser.version;base.resource.verify_sandbox(browser,report);phase_flow(run,browser)
            except BaseException as e:failed(report,e);raise
            finally:
                try:browser.close();report.setdefault('browser_closes',{})[run.phase]='CLOSED'
                except BaseException as e:report.setdefault('browser_cleanup_errors',[]).append(type(e).__name__);failed(report,e);raise
        assert run.budget.posts==(30 if run.phase=='A' else 39) and not report['violations'] and not report['page_errors']
        commands=report['DOM_write_requests'];previews=[x for x in commands if x['preview']];keys=[x['key'] for x in commands if not x['preview']]
        assert len(previews)==4 and all(x['key'] is None and x['phase']=='A' for x in previews)
        assert len(keys)==len(set(keys))==(26 if run.phase=='A' else 35)
        assert sum(x['phase']=='A' for x in commands)==30 and sum(x['phase']=='B' for x in commands)==(0 if run.phase=='A' else 9)
        assert not report.get('progress_errors')
        report.update(status='PASS',stage='PHASE_'+run.phase+'_COMPLETE')
    except BaseException as e:failed(report,e);raise
    finally:
        signal.alarm(0);report.setdefault('browser_segment_seconds',{})[run.phase]=time.monotonic()-started
        report['browser_worker_final']=run.phase;run.progress.finish()
        if report.get('progress_errors') and report['status']=='PASS':failed(report,RuntimeError('partial checkpoint failed'))
        atomic_report(Path(config['browser_result']),report)


def supervisor(config_path):
    config=json.loads(Path(config_path).read_text());directory=Path(config['private'])/('browser-supervision-'+config['phase']);directory.mkdir(mode=0o700)
    result=supervise([sys.executable,'-B','-m',MODULE,'--browser-worker',str(config_path)],env=dict(os.environ),cwd=ROOT,directory=directory,started=time.monotonic())
    atomic_report(directory/'owned.json',result)
    return 0 if result['status']=='CLEANUP_CONFIRMED' and result['operation_status']=='PASS' else 1


def main():
    os.umask(0o077);started=time.monotonic();report=dict(scope='INSTALLED_FULL_NO_MODEL_A_AND_INDEPENDENT_REUSE_B',status='NOT_RUN',stage='HOST_GATE',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None);progress_configs={};progress_seen={}
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number=RUN);run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-full-guide-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700)
        installed.installation(run,installed.current_wheel(run));env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            d=run.private/name;d.mkdir(mode=0o700);env[key]=str(d)
        env=guide.installed_font_environment(env,run.private/'fontconfig',report);run.budget=SimpleNamespace(internal_reads=0)
        with installed.server(run):
            with source.owner(run) as c:
                c.execute('SET TRANSACTION READ ONLY');report['empty_business_tables']={t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('runs','cases','preparations','service_dispatches','service_receipt_steps','run_assignments')};assert not any(report['empty_business_tables'].values())
            for phase,reserve in (('A',235),('B',145)):
                installed.require_work(run,reserve);report.update(status='RUNNING',stage='ADMIT_'+phase)
                report.setdefault('phase_admissions',[]).append(dict(phase=phase,elapsed=time.monotonic()-started,reserved_seconds=reserve,root_limit=270))
                result=run.private/('browser-result-'+phase+'.json');path=run.private/('browser-config-'+phase+'.json')
                cfg=dict(started=started,phase=phase,report=report,ready=run.budget.internal_reads,chrome_env=env,browser_result=str(result),
                    progress_path=str(run.private/('browser-partial-'+phase+'.json')),progress_invocation=uuid4().hex,
                    **{k:str(getattr(run,k)) for k in ('private','public','harness','state','python')});path.write_text(json.dumps(cfg));progress_configs[phase]=dict(cfg,report=dict(report))
                with (run.private/('browser-supervisor-'+phase+'.log')).open('w') as log:
                    child=subprocess.run([sys.executable,'-B','-m',MODULE,'--browser-supervisor',str(path)],cwd=ROOT,env=dict(os.environ),stdout=log,stderr=log,timeout=100)
                final=json.loads(result.read_text()) if result.exists() else None
                if final is not None:report.update(final)
                owned=json.loads((run.private/('browser-supervision-'+phase)/'owned.json').read_text());report.setdefault('owned_browsers',{})[phase]=owned
                progress_seen[phase]=recover_progress(report,progress_configs[phase],final)
                assert child.returncode==0 and owned['operation_status']=='PASS' and owned['bound_processes_exited'] and not owned['errors'] and not owned['signals']
                assert report.get('browser_worker_final')==phase and report['status']=='PASS'
        installed.collect_installation(run,complete=False);attest=report['process_installation_attestations']
        assert set(attest)=={'setup-attestation','api-attestation','worker-0-attestation','worker-1-attestation'}
        assert all(len(v)==2 and all(x['wheel_sha256']==report['installation']['wheel_sha256'] and x['isolated'] and not x['PYTHONPATH'] for x in v) for v in attest.values())
        report['work_completion_seconds']=time.monotonic()-started;assert report['work_completion_seconds']<=270
        report.update(status='PASS',stage='COMPLETE')
    except BaseException as e:failed(report,e)
    finally:
        # Even subprocess/JSON/owned-state failures must retain the last durable
        # partial without replacing their original error or cleanup evidence.
        for phase,cfg in progress_configs.items():
            try:
                owned=Path(cfg['private'])/('browser-supervision-'+phase)/'owned.json'
                if owned.exists():report.setdefault('owned_browsers',{})[phase]=json.loads(owned.read_text())
            except BaseException as e:base.finalization_failure(report,e)
            final=None
            try:
                result=Path(cfg['browser_result']);final=json.loads(result.read_text()) if result.exists() else None
            except BaseException as e:base.finalization_failure(report,e)
            try:progress_seen[phase]=recover_progress(report,cfg,final,progress_seen.get(phase))
            except BaseException as e:base.finalization_failure(report,e)
        if hasattr(run,'harness'):
            try:installed.collect_installation(run,complete=False)
            except BaseException as e:base.finalization_failure(report,e)
        if run.public is not None:
            try:
                installed.publish_logs(run)
                with (run.public/'installation-redacted.log').open('ab') as log:
                    for phase in ('A','B'):
                        for path in (run.private/('browser-supervisor-'+phase+'.log'),run.private/('browser-supervision-'+phase)/'worker-output.log'):
                            if not path.exists():continue
                            data=path.read_bytes();assert len(data)<=256*1024
                            for secret in run.secrets:data=data.replace(secret.encode(),b'[REDACTED_SYNTHETIC_SESSION]').replace(secret[:12].encode(),b'[REDACTED_SYNTHETIC_SESSION]')
                            log.write(('CAPTURED_COMPONENT '+str(path.relative_to(run.private))+'\n').encode()+data+b'\n')
            except BaseException as e:base.finalization_failure(report,e)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--browser-supervisor':raise SystemExit(supervisor(sys.argv[2]))
    if len(sys.argv)==3 and sys.argv[1]=='--browser-worker':
        hand=json.loads(sys.stdin.buffer.readline(4096));assert hand['parent_pid']==os.getppid() and hand['worker_pid']==os.getpid() and 0<=time.monotonic()-hand['started']<85
        browser_worker(json.loads(Path(sys.argv[2]).read_text()),hand['started'])
    else:raise SystemExit(main())
