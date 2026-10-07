"""Cached real Chromium against separate isolated mock candidate app, no PG connection."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);args=p.parse_args();root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
command=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-rule-candidate','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
    r=subprocess.run(command+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
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
    diagnostics=value("({error:document.querySelector('#error').textContent,actor:document.querySelector('#actor').value,state:view?.state,revision:view?.revision,dates:[document.querySelector('#valid-from').value,document.querySelector('#valid-until').value],editHidden:document.querySelector('#edit').hidden,buttons:[...document.querySelectorAll('[data-action]')].map(b=>[b.dataset.action,b.disabled]),clicks:window.candidateClickActions})")
    raise AssertionError('candidate browser timeout: '+expr+' '+json.dumps(diagnostics,ensure_ascii=False))
def click(selector):
    wait('!document.querySelector('+json.dumps(selector)+').disabled',lambda x:x is True)
    value("(()=>{window.candidateClickActions=[];document.querySelector("+json.dumps(selector)+").addEventListener('click',()=>candidateClickActions.push('CLICK'),{once:true});return true;})()")
    value("(()=>{document.querySelector("+json.dumps(selector)+").scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i')
    browser('click',selector);browser('snapshot','-i')
    assert value('candidateClickActions.length')==1, 'browser did not deliver target click '+selector
def role(actor):
    browser('select','#actor',actor);return wait('view',lambda x:isinstance(x,dict))
def act(action,state):
    rev=value('view.revision');click('[data-action='+action+']');return wait('view',lambda x:isinstance(x,dict) and x['revision']>rev and x['state']==state)
def capture(name,target='#status'):
    value("(()=>{document.querySelector("+json.dumps(target)+").scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
args.screenshots.mkdir(parents=True,exist_ok=False);metrics=[]
def main():
    browser('open','http://127.0.0.1:8766');wait('view',lambda x:isinstance(x,dict));assert value('view.state')=='NOT_CREATED'
    assert '候选流程未启用' in value("document.querySelector('#candidate-banner').textContent")
    act('SAVE','DRAFT');act('SUBMIT','REVIEW_REQUESTED');role('mock-publisher');click('[data-action=PUBLISH]');wait("document.querySelector('#error').textContent",lambda x:'变化' in x);assert value('view.revision')==2 and not value('view.candidate_available')
    role('prep-specialist-fixture-a');act('REVIEW','REVIEWED');assert not value('view.candidate_available') and value('view.releases.length')==0;capture('reviewed-not-candidate-published.png')
    role('mock-publisher');act('PUBLISH','PUBLISHED');assert value('view.candidate_available') and value('view.qualification_truth')=='UNKNOWN';click('#assess');wait('view.assessments.length',lambda n:n==1)
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']>=m['scroll'];metrics.append(m);capture('candidate-published-'+str(width)+'.png','#candidate-banner')
    role('fixture-a');browser('fill','#source-version','2');browser('fill','#source-text','SYNTHETIC source changed for explicit re-review');act('SAVE','DRAFT');assert value('view.assessments[0].state')=='STALE' and value('view.releases[0].state')=='SUPERSEDED';capture('changed-candidate-stale.png','#assessments')
    browser('reload');wait('view',lambda x:isinstance(x,dict));assert value('view.state')=='DRAFT' and value('view.content_version')==2 and value('view.assessments[0].state')=='STALE'
    act('SUBMIT','REVIEW_REQUESTED');act('RETURN_DRAFT','DRAFT');act('SUBMIT','REVIEW_REQUESTED');role('prep-specialist-fixture-a');act('REJECT','REJECTED');role('fixture-a');browser('fill','#source-version','3');browser('fill','#source-text','SYNTHETIC revised after candidate rejection');act('SAVE','DRAFT');act('SUBMIT','REVIEW_REQUESTED');role('prep-specialist-fixture-a');act('REVIEW','REVIEWED');role('mock-publisher');act('PUBLISH','PUBLISHED');act('WITHDRAW','WITHDRAWN');assert not value('view.candidate_available') and value('view.releases[1].state')=='WITHDRAWN';capture('candidate-withdrawn-history.png','#history')
    # Genuine commit then lose reply: stable key gives one candidate event.
    role('fixture-a');browser('fill','#source-version','4');browser('fill','#source-text','SYNTHETIC lost response source');rev=value('view.revision')
    value("(()=>{window.originalCandidateFetch=window.fetch;window.dropCandidate=true;window.fetch=async(p,o)=>{const r=await originalCandidateFetch(p,o);if(String(p).endsWith('/commands')&&dropCandidate){dropCandidate=false;throw Error('SYNTHETIC_LOST_CANDIDATE_REPLY');}return r;};return true;})()")
    click('[data-action=SAVE]');wait("document.querySelector('#error').textContent",lambda x:'LOST_CANDIDATE_REPLY' in x);click('[data-action=SAVE]');wait('view.revision',lambda n:n==rev+1);value("(()=>{window.fetch=originalCandidateFetch;return true;})()")
    # Commit a source change, switch to unauthorised mock scope before its reply.
    browser('fill','#source-version','5');browser('fill','#source-text','SYNTHETIC private late source')
    value("(()=>{window.lateCandidateFetch=window.fetch;window.releaseCandidate=null;window.fetch=async(p,o)=>{const r=await lateCandidateFetch(p,o);if(String(p).endsWith('/commands'))await new Promise(resolve=>releaseCandidate=resolve);return r;};return true;})()")
    click('[data-action=SAVE]');wait('typeof releaseCandidate',lambda x:x=='function');browser('select','#actor','mock-other-org');wait("document.querySelector('#error').textContent",lambda x:'拒绝' in x);value("(()=>{window.fetch=lateCandidateFetch;releaseCandidate();return true;})()");browser('snapshot','-i')
    assert value('view') is None and value("document.querySelector('#sources').textContent")=='' and value("document.querySelector('#source-text').value")=='';role('fixture-a');assert value('view.content_version')==5
    # Expired synthetic source can be saved but cannot be submitted or used.
    value("(()=>{document.querySelector('#valid-until').value='2020-01-01T00:00';document.querySelector('#valid-until').dispatchEvent(new Event('input'));return true;})()");browser('fill','#source-version','6');act('SAVE','DRAFT');assert value('view.availability_reason')=='EXPIRED_SOURCE';click('[data-action=SUBMIT]');wait("document.querySelector('#error').textContent",lambda x:'变化' in x);assert value('view.qualification_truth')=='UNKNOWN';capture('expired-source-unknown.png','#status')
    browser('reload');x=wait('view',lambda x:isinstance(x,dict));assert x['state']=='DRAFT' and x['availability_reason']=='EXPIRED_SOURCE' and len(x['releases'])==2 and not browser('errors')
    args.report.write_text(json.dumps({'namespace':x['namespace'],'deployment_enabled':False,'business_publication':False,'model_calls':0,'budget':0,'review_publish_separate':True,'explicit_mock_scope':True,'unreviewed_publish_rejected':True,'candidate_version_changes_stale_history':True,'submission_return_and_reject':True,'withdraw_preserves_history':True,'lost_committed_response_one_event':True,'late_committed_response_after_cross_scope_switch_hidden':True,'expired_source_unknown_submission_rejected':True,'reload_restores_candidate_history':True,'revision':x['revision'],'content_version':x['content_version'],'history_count':len(x['history']),'release_count':len(x['releases']),'assessment_count':len(x['assessments']),'viewport_checks':metrics},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
