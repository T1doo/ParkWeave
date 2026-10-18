from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path.cwd();D=R/'.runtime/local-synthetic-experience-package-20261018';S='33bf2efa125e5d3b7b59e30b3ea153b9d58a113a';BASE='7699c112e7a200a26734a274b3a7fc1852f4eca9';BRANCH='dev/f2-local-synthetic-experience-package-20261018';MAIN='31e7acb7e53bb1ab6465b9daae59de28757f7583'
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True).strip()
assert git('branch','--show-current')==BRANCH and not git('status','--porcelain')
HEAD=git('rev-parse','HEAD');assert HEAD!=S
Z=R/'deliverables/local-synthetic-demo/ParkWeave-LOCAL-SYNTHETIC-33bf2efa125e.zip';assert hashlib.sha256(Z.read_bytes()).hexdigest()=='a6bdbe2846415d585653d92668faca2784328667f06f652c275b8c3b20736b9b'
for ancestor in [BASE,S,'db1084100a2477bbff3da8b49287c755dbc83c1b']:assert subprocess.run(['git','merge-base','--is-ancestor',ancestor,HEAD],cwd=R).returncode==0
for p in ['src','tests','scripts','pyproject.toml','docs/验收规格.json','docs/F1/ATBindings.json','docs/F1/DataLedger.md','docs/F2/AT32SourceDisclosureCase-20261018.json']:
 assert git('rev-parse',HEAD+':'+p)==git('rev-parse',S+':'+p),p
assert git('remote','get-url','origin')=='https://github.com/T1doo/ParkWeave.git'
assert git('config','--get-all','remote.origin.fetch')=='+refs/heads/main:refs/remotes/origin/main'
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ['GIT_CURL_VERBOSE','GH_DEBUG']};env['GIT_TERMINAL_PROMPT']='0';prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
def refs(text):return {ref:sha for sha,ref in (line.split() for line in text.splitlines())}
def remote(name):
 p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=R,env=env,capture_output=True,text=True,timeout=45);(D/(name+'.txt')).write_text(p.stdout);(D/(name+'.stderr')).write_text(p.stderr);assert p.returncode==0;return refs(p.stdout)
before=remote('pre-push-remote');initial=refs((D/'baseline-remote.txt').read_text());assert before==initial and len(before)==114 and before['refs/heads/main']==MAIN and before['refs/heads/dev/f3-at21-synthetic-readiness-20261018']==BASE and 'refs/heads/'+BRANCH not in before
argv=prefix+['push','origin','HEAD:refs/heads/'+BRANCH];start=time.monotonic()
try:
 p=subprocess.run(argv,cwd=R,env=env,capture_output=True,text=True,timeout=120);code,state,out,err=p.returncode,'COMPLETED',p.stdout,p.stderr
except subprocess.TimeoutExpired as e:
 code,state=None,'UNCERTAIN_TIMEOUT';out=e.stdout or b'';err=e.stderr or b'';out=out.decode(errors='replace') if isinstance(out,bytes) else out;err=err.decode(errors='replace') if isinstance(err,bytes) else err
(D/'push.stdout').write_text(out);(D/'push.stderr').write_text(err)
push=dict(delivery_sha=HEAD,tested_source_sha=S,branch=BRANCH,exit_code=code,state=state,elapsed_seconds=time.monotonic()-start,argv=argv,force=False,main_targeted=False,deployed=False,credential_config_changed=False)
(D/'push-result.json').write_text(json.dumps(push,indent=2)+'\n');print(json.dumps(push))
after=remote('post-push-remote');expected={**before,'refs/heads/'+BRANCH:HEAD}
# Check an uncertain result before considering any further action. Never automatically retry push.
assert after==expected,'unexpected remote outcome; preserve results and do not retry'
assert code==0,'remote state known, process outcome needs reporting'
ref='refs/remotes/origin/'+BRANCH;p=subprocess.run(prefix+['fetch','origin','refs/heads/'+BRANCH+':'+ref],cwd=R,env=env,capture_output=True,text=True,timeout=60);(D/'explicit-fetch.stdout').write_text(p.stdout);(D/'explicit-fetch.stderr').write_text(p.stderr);assert p.returncode==0
diff=git('rev-list','--left-right','--count','HEAD...'+ref);assert diff.split()==['0','0'];assert git('rev-parse',ref)==HEAD and not git('status','--porcelain')
assert git('config','--get-all','remote.origin.fetch')=='+refs/heads/main:refs/remotes/origin/main'
result=dict(delivery_sha=HEAD,tested_source_sha=S,baseline_sha=BASE,branch=BRANCH,remote_heads_before=len(before),remote_heads_after=len(after),added={'refs/heads/'+BRANCH:HEAD},changed_existing_heads={},main_sha=MAIN,main_unchanged=True,ahead=0,behind=0,worktree_clean=True,db108_is_ancestor=True,source_tests_scripts_unchanged=True,explicit_fetch_exit_code=p.returncode,fetch_config_unchanged=True,unknown_lock_preserved=(R/'.git/codex-index-refresh.lock').exists())
(D/'delivery-and-remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
