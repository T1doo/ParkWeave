from pathlib import Path
import hashlib,json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018';branch='dev/f2-collaboration-dom-20261018';prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0'
p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'post-push-remote.txt').write_text(p.stdout);(r/'post-push-remote.stderr').write_text(p.stderr);assert p.returncode==0
actual={ref:sha for sha,ref in (line.split() for line in p.stdout.splitlines())};before={ref:sha for sha,ref in (line.split() for line in (r/'baseline-remote.txt').read_text().splitlines())};target='refs/heads/'+branch;head=git('rev-parse','HEAD');assert actual.get(target)==head
changed=[ref for ref,sha in before.items() if actual.get(ref)!=sha];added=sorted(set(actual)-set(before));removed=sorted(set(before)-set(actual));assert not changed and not removed and added==[target]
p=subprocess.run(prefix+['fetch','origin',target+':refs/remotes/origin/'+branch],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'fetch-target.stdout').write_text(p.stdout);(r/'fetch-target.stderr').write_text(p.stderr);assert p.returncode==0
subprocess.run(['git','branch','--set-upstream-to=origin/'+branch,branch],cwd=root,check=True,capture_output=True,text=True)
diff=git('rev-list','--left-right','--count','HEAD...origin/'+branch);assert diff=='0\t0' and not git('status','--porcelain')
freeze=json.loads((r/'verified-freeze.json').read_text());expected=json.loads((r/'verified-inputs.json').read_text());assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in expected.items())
new={}
for line in subprocess.check_output(['git','ls-tree','-rz','HEAD','--','docs/F2/evidence/original-collaboration-dom-20261018'],cwd=root).split(b'\0'):
    if line:
        meta,name=line.split(b'\t',1);path=name.decode();blob=meta.split()[2].decode();data=(root/path).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob;new[path]=blob
result=dict(delivery_sha=head,tested_source_sha=freeze['source_sha'],branch=branch,actual_remote_target_sha=actual[target],head_count_before=len(before),head_count_after=len(actual),added=added,changed_existing=changed,removed=removed,main_before=before['refs/heads/main'],main_after=actual['refs/heads/main'],ahead_behind=diff,clean=True,frozen_inputs=len(expected),input_drift=[],new_evidence_Git_blobs_actual_bytes_verified=len(new),unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists(),force=False,main_targeted=False,deployed=False,real_models=0,verified_utc_epoch=time.time())
(r/'delivery-and-remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
