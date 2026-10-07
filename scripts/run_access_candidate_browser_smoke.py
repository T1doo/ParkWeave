"""Real cached Chromium, separate single-Run Mock app on local port 8767."""
from pathlib import Path
import argparse,json,os,subprocess,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);args=p.parse_args();root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert cached
command=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-run-access-candidate','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args):
    r=subprocess.run(command+list(args),capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached browser operation failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if pred(x):return x
        time.sleep(.1)
    raise AssertionError('candidate browser timeout '+expr+' '+json.dumps(value("({actor:document.querySelector('#actor').value,state:view?.state,error:document.querySelector('#error').textContent})"),ensure_ascii=False))
def click(selector):
    wait('!document.querySelector('+json.dumps(selector)+').disabled',lambda x:x is True)
    value("(()=>{window.deliveredCandidateClicks=0;const b=document.querySelector("+json.dumps(selector)+");b.addEventListener('click',()=>deliveredCandidateClicks++,{once:true});b.scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('deliveredCandidateClicks')==1
def role(actor):browser('select','#actor',actor);return wait('view',lambda x:isinstance(x,dict))
def act(action,state):
    rev=value('view.revision');click('[data-action='+action+']');return wait('view',lambda x:isinstance(x,dict) and x['revision']>rev and x['state']==state)
def capture(name,target='#candidate-banner'):
    value("(()=>{document.querySelector("+json.dumps(target)+").scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
def api_status(actor,path,body,key=None):
    return value("(async()=>{const r=await fetch("+json.dumps(path)+",{method:'POST',headers:"+json.dumps({'Content-Type':'application/json','X-Mock-Actor':actor,**({'Idempotency-Key':key} if key else {})})+",body:JSON.stringify("+json.dumps(body)+")});await r.json();return r.status;})()")
BASE='/api/run-access/park-a/org-a/mock-run-a';OWNER='mock-run-owner';APPROVER='mock-run-access-approver';TARGET='mock-run-executor';args.screenshots.mkdir(parents=True,exist_ok=False);metrics=[]
def main():
    browser('open','http://127.0.0.1:8767');wait('view',lambda x:isinstance(x,dict));assert value('view.state')=='NOT_REQUESTED'
    browser('select','#target','mock-other-executor');click('[data-action=REQUEST]');wait("document.querySelector('#error').textContent",lambda x:'拒绝' in x);assert value('view') is None
    click('#refresh');wait('view',lambda x:isinstance(x,dict));assert value('view.revision')==0;browser('select','#target',TARGET);act('REQUEST','REQUESTED');capture('pending-independent-approval.png','#status')
    browser('select','#actor','prep-specialist-fixture-a');wait("document.querySelector('#error').textContent",lambda x:'拒绝' in x);assert value('view') is None and value("document.querySelector('#binding').textContent")==''
    role(APPROVER)
    value("(()=>{window.originalAccessFetch=window.fetch;window.lastAccessApproval=null;window.fetch=async(p,o)=>{if(String(p).endsWith('/commands')&&JSON.parse(o.body).action==='APPROVE')lastAccessApproval={body:JSON.parse(o.body),key:o.headers['Idempotency-Key']};return originalAccessFetch(p,o);};return true;})()")
    act('APPROVE','APPROVED');approval=value('lastAccessApproval');value("(()=>{window.fetch=originalAccessFetch;return true;})()");role(TARGET);click('#probe');wait("document.querySelector('#mock-run-snapshot').textContent",lambda x:x.startswith('SYNTHETIC mock-run-a'));old=value('cachedProbe');click('#cached-probe')
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append(m);capture('approved-read-'+str(width)+'.png')
    capture('exact-run-binding-and-probe.png','#binding')
    browser('select','#run','mock-run-b');wait("document.querySelector('#error').textContent",lambda x:'拒绝' in x);assert value('view') is None and value("document.querySelector('#mock-run-snapshot').textContent")==''
    assert api_status(TARGET,'/api/run-access/park-a/org-a/mock-run-b/probe',old)==403
    browser('select','#run','mock-run-a');wait('view',lambda x:isinstance(x,dict));role(OWNER);act('REVOKE','REVOKED');role(TARGET)
    assert api_status(TARGET,BASE+'/probe',old)==403 and api_status(APPROVER,BASE+'/commands',approval['body'],approval['key'])==409
    assert not value('view.candidate_access_available') and value('cachedProbe') is None;capture('revoked-cached-context-refused.png','#status')
    role(OWNER);act('REQUEST','REQUESTED');role(APPROVER);act('REJECT','REJECTED');role(OWNER);act('REQUEST','REQUESTED');act('CANCEL','CANCELLED')
    # One committed request with a lost response, then the same key restores it.
    value("(()=>{window.originalAccessFetch=window.fetch;window.dropAccessReply=true;window.fetch=async(p,o)=>{const r=await originalAccessFetch(p,o);if(String(p).endsWith('/commands')&&dropAccessReply){dropAccessReply=false;throw Error('SYNTHETIC_LOST_ACCESS_REPLY');}return r;};return true;})()")
    rev=value('view.revision');click('[data-action=REQUEST]');wait("document.querySelector('#error').textContent",lambda x:'LOST_ACCESS_REPLY' in x);click('[data-action=REQUEST]');wait('view.revision',lambda n:n==rev+1);value("(()=>{window.fetch=originalAccessFetch;return true;})()");act('CANCEL','CANCELLED')
    # A committed response arriving after a tenant switch cannot restore private data.
    value("(()=>{window.lateAccessFetch=window.fetch;window.releaseAccessReply=null;window.fetch=async(p,o)=>{const r=await lateAccessFetch(p,o);if(String(p).endsWith('/commands'))await new Promise(resolve=>releaseAccessReply=resolve);return r;};return true;})()")
    click('[data-action=REQUEST]');wait('typeof releaseAccessReply',lambda x:x=='function');browser('select','#actor','mock-other-owner');wait("document.querySelector('#error').textContent",lambda x:'拒绝' in x);value("(()=>{window.fetch=lateAccessFetch;releaseAccessReply();return true;})()");browser('snapshot','-i')
    assert value('view') is None and value("document.querySelector('#binding').textContent")=='' and value("document.querySelector('#history').textContent")=='';role(OWNER);act('CANCEL','CANCELLED')
    # A short real-time deadline; the browser clears its cached view on expiry.
    value("(()=>{const n=new Date();document.querySelector('#valid-from').value=n.toISOString().slice(0,19);document.querySelector('#valid-until').value=new Date(n.getTime()+16000).toISOString().slice(0,19);return true;})()")
    act('REQUEST','REQUESTED');role(APPROVER);act('APPROVE','APPROVED');role(TARGET);click('#probe');wait('cachedProbe',lambda x:isinstance(x,dict));expiring=value('cachedProbe')
    wait("document.querySelector('#mock-run-snapshot').textContent",lambda x:x=='',timeout=22);assert value('cachedProbe') is None and value("document.querySelector('#probe').disabled")
    assert api_status(TARGET,BASE+'/probe',expiring)==403;click('#refresh');x=wait('view',lambda x:isinstance(x,dict));assert x['availability_reason']=='EXPIRED_APPROVAL' and not x['candidate_access_available'];capture('expired-cache-cleared.png','#status')
    browser('reload');wait('view',lambda x:isinstance(x,dict));role(TARGET);x=value('view');assert x['availability_reason']=='EXPIRED_APPROVAL' and len(x['history'])==13 and len(x['leases'])==2 and not browser('errors')
    args.report.write_text(json.dumps({'namespace':x['namespace'],'deployment_enabled':False,'actual_assignment_written':False,'actual_run_access':False,'model_calls':0,'budget':0,'independent_approval':True,'material_reviewer_has_no_access_approval':True,'cross_tenant_request_denied_without_write':True,'cross_run_probe_denied':True,'revoked_cached_probe_denied':True,'old_approval_replay_denied':True,'cancel_reject_and_history_preserved':True,'lost_committed_response_single_event':True,'late_cross_tenant_response_hidden':True,'expiry_clears_cached_snapshot_and_denies_probe':True,'reload_restores_audit':True,'revision':x['revision'],'history_count':len(x['history']),'lease_count':len(x['leases']),'viewport_checks':metrics},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
