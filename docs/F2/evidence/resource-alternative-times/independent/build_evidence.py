import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/tmp/parkweave-alternative-times-independent-review')
REPO=Path('/workspace/ParkWeave');DEST=ROOT/'deliverable'
FINAL='f9bf9b76b512eb98ce23f92beba2fc4327e0b8a1'
BASE='a954bf6811e395d7515181f8bad8dd8f12d1cd7c'
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert git('rev-parse','HEAD')==FINAL and git('status','--porcelain=v1')==''
files=['conftest.py','test_alternatives_independent.py','test_alternatives_vm_independent.py','alternatives_vm_independent.js','final-f9bf9b76.log','final-f9bf9b76.xml','REVIEW.md','REVIEW-3e.md','build_evidence.py']
DEST.mkdir(exist_ok=True)
for name in files:shutil.copyfile(ROOT/name,DEST/name)
(DEST/'historical-3e').mkdir(exist_ok=True)
for p in (ROOT/'historical-3e').iterdir():shutil.copyfile(p,DEST/'historical-3e'/p.name)
def counts(name):
    suites=list(ET.parse(ROOT/name).getroot().iter('testsuite'))
    return {k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']}
changed=git('diff','--name-only',BASE,FINAL,'--','src','pyproject.toml').splitlines()
allowed=['src/parkweave/api.py','src/parkweave/resource_holds.py','src/parkweave/web.html']
assert sorted(changed)==allowed
protected={}
for p in git('ls-tree','-r','--name-only',BASE,'src','pyproject.toml').splitlines():
    if p in allowed:continue
    before=git('rev-parse',BASE+':'+p);after=git('rev-parse',FINAL+':'+p)
    assert before==after
    protected[p]={'base_blob':before,'final_blob':after}
v={'source_sha':FINAL,'direct_parent':git('rev-parse',FINAL+'^'),'business_base':BASE,
   'head_before_execution':FINAL,'head_after_execution':FINAL,'worktree_clean':True,
   'final_independent_counts':counts('final-f9bf9b76.xml'),'final_split':{'owned_pg_asgi':22,'offline_node_vm':16},
   'historical_3e_counts':counts('final-3e0c51ea.xml'),'historical_note':'Separate source; handler success did not sign actual controls; root integrated failure retained by root. Independent runs had no failures.',
   'runtime_changed_files':changed,'protected_identical_git_blobs':protected,
   'browser_started':False,'http_listener_started':False,'external_network_used':False,'repo_git_writes':False,
   'actual_lock_wait_assertion':'pg_stat_activity.wait_event_type == Lock before owner commit; reply revision/rules committed and DB clock >= immediately-before-unlock clock',
   'scan_limit_100_triggered':False,'actual_maximum_grid_candidates_tested':96}
(DEST/'verification.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
manifest={'source_sha':FINAL,'files':{str(p.relative_to(DEST)):digest(p) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='manifest.json'}}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'manifest':str(DEST/'manifest.json'),'manifest_sha256':digest(DEST/'manifest.json'),'final_counts':v['final_independent_counts'],'protected_runtime_files':len(protected)}))
