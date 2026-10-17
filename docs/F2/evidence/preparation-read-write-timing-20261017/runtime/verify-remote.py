from pathlib import Path
import subprocess,json
root=Path('/workspace/ParkWeave');r=root/'.runtime/preparation-read-write-timing'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
def refs(text):return {line.split()[1]:line.split()[0] for line in text.splitlines()}
before=refs((r/'pre-push-remote.txt').read_text());initial=refs((r/'pre-freeze-remote.txt').read_text());raw=git('ls-remote','--heads','origin');(r/'post-push-remote.txt').write_text(raw+'\n');after=refs(raw)
head=git('rev-parse','HEAD');target='refs/heads/'+git('branch','--show-current');delta={p:{'before':before.get(p),'after':after.get(p)} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)};pre_delta={p:{'before':initial.get(p),'after':before.get(p)} for p in sorted(initial.keys()|before.keys()) if initial.get(p)!=before.get(p)}
result=dict(delivery_sha=head,source_sha='25c64f1dd4bb2ca9a79be88650d3a1b410c4bef5',remote_sha=after[target],exact_head_remote_difference=git('rev-list','--left-right','--count','HEAD...'+after[target]),remote_head_count_before=len(before),remote_head_count_after=len(after),pre_freeze_to_pre_push_delta=pre_delta,remote_changed=delta,main_before=before['refs/heads/main'],main_after=after['refs/heads/main'],working_tree=git('status','--porcelain'),unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists())
(r/'remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert after[target]==head and set(delta)=={target} and not result['working_tree'] and result['main_before']==result['main_after'] and not pre_delta
