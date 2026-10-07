"""Cached Chromium acceptance for the local review hub and isolated candidates.

Run from the existing browser-cache fixture; never connects product PG or network.
Requires an explicitly started review launcher at --base-port.
"""
from pathlib import Path
import argparse,json,os,subprocess,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--base-port',type=int,default=8770);p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);a=p.parse_args();root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
command=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-review-path','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args):
    r=subprocess.run(command+list(args),capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached local browser operation failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if pred(x):return x
        time.sleep(.1)
    raise AssertionError('review browser timeout '+expr)
def click(selector):
    wait('!document.querySelector('+json.dumps(selector)+').disabled',lambda x:x is True)
    value("(()=>{window.reviewClicks=0;const b=document.querySelector("+json.dumps(selector)+");b.addEventListener('click',()=>reviewClicks++,{once:true});b.scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i');browser('click',selector);browser('snapshot','-i')
    # Navigation resets the document; command buttons must deliver exactly once.
    if selector not in ('#open-rules','#open-access'):assert value('reviewClicks')==1

def role(actor):browser('select','#actor',actor);return wait('view',lambda x:isinstance(x,dict))
def act(action,state):
    rev=value('view.revision');click('[data-action='+action+']');return wait('view',lambda x:isinstance(x,dict) and x['revision']>rev and x['state']==state)
def capture(name,target):
    value("(()=>{document.querySelector("+json.dumps(target)+").scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/name))
hub=f'http://127.0.0.1:{a.base_port}/';a.screenshots.mkdir(parents=True,exist_ok=False);metrics=[]
def open_hub():
    browser('open',hub);return wait('review',lambda x:isinstance(x,dict) and len(x['stages'])==6)
def main():
    x=open_hub();assert x['isolated_mock_enabled'] and all(s['state']=='VERIFIED_COMMITTED_EVIDENCE' for s in x['stages'])
    seals={s['id']:s['actual_sha256'] for s in x['stages']};cases={s['case_id'] for s in x['stages'] if s['case_id']!='NOT_RECORDED'};assert len(cases)>=3 and all(not s['same_case_chain'] for s in x['stages'])
    assert '不是同一新事项' in value("document.querySelector('#boundary').textContent") and len(x['original_plan_gaps'])==7
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append({'page':'hub',**m});capture('hub-'+str(width)+'.png','#boundary')
    click('#refresh');wait('review',lambda z:isinstance(z,dict));browser('reload');wait('review',lambda z:isinstance(z,dict));x=open_hub();assert {s['id']:s['actual_sha256'] for s in x['stages']}==seals
    click('#open-rules');wait('view',lambda z:isinstance(z,dict));assert value('view.state')=='NOT_CREATED'
    act('SAVE','DRAFT');act('SUBMIT','REVIEW_REQUESTED');role('prep-specialist-fixture-a');act('REVIEW','REVIEWED');role('mock-publisher');r=act('PUBLISH','PUBLISHED');assert len(r['history'])==4 and not r.get('actual_publication_written',False)
    for width in (390,320):
        browser('set','viewport',str(width),'844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append({'page':'rules',**m});capture('rules-'+str(width)+'.png','#candidate-banner')
    browser('reload');wait('view',lambda z:isinstance(z,dict));assert value('view.history.length')==4
    open_hub();click('#open-access');wait('view',lambda z:isinstance(z,dict));assert value('view.state')=='NOT_REQUESTED'
    act('REQUEST','REQUESTED');role('mock-run-access-approver');act('APPROVE','APPROVED');role('mock-run-executor');click('#probe');wait("document.querySelector('#mock-run-snapshot').textContent",lambda s:s.startswith('SYNTHETIC mock-run-a'))
    for width in (390,320):
        browser('set','viewport',str(width),'844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append({'page':'access',**m});capture('access-'+str(width)+'.png','#candidate-banner')
    browser('select','#run','mock-run-b');wait("document.querySelector('#error').textContent",lambda s:'拒绝' in s);assert value('view') is None and value("document.querySelector('#mock-run-snapshot').textContent")==''
    browser('select','#run','mock-run-a');wait('view',lambda z:isinstance(z,dict));role('mock-run-owner');act('REVOKE','REVOKED');role('mock-run-executor');assert not value('view.candidate_access_available') and value('cachedProbe') is None;capture('access-revoked.png','#status')
    browser('reload');wait('view',lambda z:isinstance(z,dict));assert value('view.history.length')==3
    x=open_hub();click('#refresh');wait('review',lambda z:isinstance(z,dict));assert {s['id']:s['actual_sha256'] for s in value('review.stages')}==seals and not x['product_state_written']
    assert not browser('errors')
    a.report.write_text(json.dumps({'clean_hub_open':True,'repeated_open_and_reload':True,'native_links_to_both_candidates':True,'historical_cases_distinct':True,'historical_sources_unchanged_after_mock':True,'rules_history_after_reload':4,'access_history_after_reload':3,'cross_run_b_denied':True,'revocation_clears_mock_access':True,'same_case_business_chain':False,'product_database_connected':False,'actual_assignment_written':False,'credentials_created':False,'viewport_checks':metrics,'model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
