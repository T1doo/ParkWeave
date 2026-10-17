"""Verify actual normal development delivery, all frozen inputs and inherited F2."""
from pathlib import Path
import subprocess,json,hashlib,datetime,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/material-version-compare';OUT=ROOT/'docs/F2/evidence/material-version-compare-20261017'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True)
def refs(s):return {ref:sha for sha,ref in (line.split() for line in s.splitlines())}
def sha(b):return hashlib.sha256(b).hexdigest()
f=json.loads((R/'freeze.json').read_text());head=git('rev-parse','HEAD').strip();branch=git('branch','--show-current').strip();source=f['source_sha']
assert branch==f['branch'] and git('status','--porcelain')==''
assert all(sha((ROOT/p).read_bytes())==h for p,h in f['files'].items())
subprocess.run(['git','merge-base','--is-ancestor',source,head],check=True,cwd=ROOT)
delta=git('diff','--name-only',source,head).splitlines();assert delta and all(p=='README.md' or p.startswith('docs/') for p in delta)
remote=git('ls-remote','--heads','origin');(R/'remote-after.txt').write_text(remote);before=refs((R/'remote-before.txt').read_text());after=refs(remote);target='refs/heads/'+branch
assert after[target]==head and all(after.get(ref)==s for ref,s in before.items()) and set(after)-set(before)=={target}
assert git('rev-list','--left-right','--count',head+'...'+after[target]).split()==['0','0']
old=json.loads((R/'inherited-evidence-blobs.json').read_text())
for p,blob in old.items():
 b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob
pairs=json.loads((OUT/'public-pairs.json').read_text())
for pair in pairs:assert sha((ROOT/pair['original']).read_bytes())==pair['original_sha256'] and sha((ROOT/pair['exported']).read_bytes())==pair['exported_sha256']
counts={suffix:0 for suffix in ('.json','.xml','.png')}
for p in OUT.rglob('*'):
 if not p.is_file():continue
 if p.suffix=='.json':
  def unique(xs):
   out={}
   for k,v in xs:
    assert k not in out
    out[k]=v
   return out
  json.loads(p.read_bytes(),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('non-JSON number')))
 if p.suffix=='.xml':ET.fromstring(p.read_bytes())
 if p.suffix=='.png':assert p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
 if p.suffix in counts:counts[p.suffix]+=1
gate=json.loads((OUT/'gate.json').read_text())
report=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_sha=f['base_sha'],source_sha=source,delivery_sha=head,actual_remote_sha=after[target],branch=branch,HEAD_to_actual_remote_left_right=[0,0],worktree_porcelain='',source_to_delivery_only_docs_evidence=True,source_to_delivery_files=delta,source_inputs=len(f['files']),source_drift=0,inherited_F2_git_blobs_checked=len(old),inherited_F2_drift=0,old_heads_checked=len(before),old_heads_changed=[],remote_heads_after=len(after),main_sha=after['refs/heads/main'],public_pairs_rehashed=len(pairs),archive_parse_counts=counts,final_unique=gate['final']['unique'],new_unique=gate['new_unique'],independent_review='exact frozen source; separate pure in-memory probes never added to final unique count',parent_prior_admission='c399 limited synthetic pack +179 evidence; parent did not rehash all316 pairs; compare300 cap',main_changed=False,forced_push=False,deployed=False,Actions_queries=0,real_model_called=False,new_credentials_security_permissions_costs=False,complete_project=False,not_run=gate['not_run'])
(R/'delivery-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('source_sha','delivery_sha','actual_remote_sha','HEAD_to_actual_remote_left_right','worktree_porcelain','old_heads_checked','old_heads_changed','remote_heads_after','main_sha','inherited_F2_git_blobs_checked','public_pairs_rehashed','archive_parse_counts')}))
