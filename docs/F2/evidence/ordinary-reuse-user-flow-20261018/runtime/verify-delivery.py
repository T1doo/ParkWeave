from pathlib import Path
import hashlib,json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/ordinary-reuse-user-flow-20261018';branch='dev/f2-material-reuse-dom-20261018';push=json.loads((r/'push-result.json').read_text());freeze=json.loads((r/'frozen-freeze.json').read_text());prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential'];env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
def remote(label):
 p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/(label+'.txt')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr);assert p.returncode==0
 return {ref:sha for sha,ref in (line.split() for line in p.stdout.splitlines())}
initial={ref:sha for sha,ref in (line.split() for line in (r/'baseline-remote.txt').read_text().splitlines())};refs=remote('post-push-remote');head=git('rev-parse','HEAD');target='refs/heads/'+branch
assert push['status']=='PROCESS_COMPLETED' and push['exit_code']==0 and push['delivery_sha']==head
assert refs[target]==head and len(refs)==len(initial)+1
assert all(refs.get(ref)==sha for ref,sha in initial.items())
p=subprocess.run(prefix+['fetch','origin',target+':refs/remotes/origin/'+branch],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'explicit-fetch.stdout').write_text(p.stdout);(r/'explicit-fetch.stderr').write_text(p.stderr);assert p.returncode==0
counts=git('rev-list','--left-right','--count','HEAD...refs/remotes/origin/'+branch);assert counts.split()==['0','0']
assert git('branch','--show-current')==branch and not git('status','--porcelain')
assert git('config','--get-all','remote.origin.fetch')=='+refs/heads/main:refs/remotes/origin/main'
for name in ('src','tests','scripts','pyproject.toml',*freeze['contracts']):assert git('rev-parse','HEAD:'+name)==git('rev-parse',freeze['source_sha']+':'+name),name
assert subprocess.run(['git','merge-base','--is-ancestor',freeze['source_sha'],'HEAD'],cwd=root).returncode==0
assert subprocess.run(['git','merge-base','--is-ancestor','db1084100a2477bbff3da8b49287c755dbc83c1b','HEAD'],cwd=root).returncode==0
result=dict(delivery_sha=head,tested_source_sha=freeze['source_sha'],source_tree=git('rev-parse','HEAD:src'),tests_tree=git('rev-parse','HEAD:tests'),branch=branch,remote_before_heads=len(initial),remote_after_heads=len(refs),remote_added={ref:sha for ref,sha in refs.items() if ref not in initial},old_remote_refs_changed=[],main=refs['refs/heads/main'],main_unchanged=refs['refs/heads/main']==initial['refs/heads/main'],explicit_remote_tracking_ref='refs/remotes/origin/'+branch,ahead_behind=[0,0],clean_worktree=True,fetch_config_unchanged=True,upstream_setting_attempted=False,source_tests_scripts_contracts_match_tested_freeze=True,normal_push=True,force=False,deployment=False,automatic_push_retries=0,default_network_and_existing_credential_helper_only=True)
(r/'delivery-and-remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
