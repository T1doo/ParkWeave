from pathlib import Path
import json, subprocess, hashlib, gzip
r=Path.cwd();rt=r/'.runtime/case-pg-vertical-20261013';ind=r/'.runtime/catalog-only-independent-20261013/vertical-54b1594';out=rt/'sol-archive-review';checks={}
def h(b):return hashlib.sha256(b).hexdigest()
def manifest(base):
 m=json.loads((base/'manifest.json').read_text())
 for f in m['files']:
  b=(base/f['path']).read_bytes();assert len(b)==f['bytes'] and h(b)==f['sha256'],f['path']
 actual={str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()};assert actual=={f['path'] for f in m['files']}|{'manifest.json'}
 assert len(m['files'])==m['count'] and sum(f['bytes'] for f in m['files'])==m['total_bytes']
 return {'count':m['count'],'total_bytes':m['total_bytes'],'manifest_sha256':h((base/'manifest.json').read_bytes()),'all_hash_bytes_match':True,'unlisted_files':[]}
a=r/'docs/F2/evidence/case-pg-vertical-acceptance-20261013';c=r/'docs/F2/evidence/case-pg-vertical-candidate-20261013'
checks['acceptance_manifest']=manifest(a);checks['candidate_manifest']=manifest(c)
exports=[]
for f in json.loads((a/'manifest.json').read_text())['files']:
 p=f['path'];src=rt/Path(p).name if p.startswith('root/') else ind/Path(p).name if p.startswith('independent-existing/') else None
 if src:
  data=(a/p).read_bytes()
  if p.endswith('.gz') and not src.exists():data=gzip.decompress(data);src=Path(str(src)[:-3])
  assert data==src.read_bytes(),p;exports.append(p)
checks['acceptance_exports']={'count':len(exports),'runtime_byte_equal':True,'paths':exports}
n=0
for rel in json.loads((ind/'safe-copy-list.json').read_text())['files']:
 assert (c/'independent'/rel).read_bytes()==(ind/rel).read_bytes(),rel;n+=1
for folder in ['first-pure','second-pure']:
 for p in (rt/folder).rglob('*'):
  if p.is_file():assert (c/'root'/p.relative_to(rt)).read_bytes()==p.read_bytes();n+=1
for v in json.loads((c/'originals.json').read_text()):
 raw=gzip.decompress((c/v['path']).read_bytes());assert len(raw)==v['original_bytes'] and h(raw)==v['original_sha256'] and raw==(rt/v['original_path']).read_bytes();n+=1
checks['historical_exports']={'checked':n,'first_second_failures_and_startup_failure_byte_equal':True,'lossless_gzip_originals_checked':4}
s='54b15947f89eb1ba7524edb1119133d37ebc5326';p='a52ad8c7101bbea12fc6a95904d3d5e19f3f30e1';e='b38bab37a072ee7db3d28bbd9aeb291d467e564f'
def git(*args):return subprocess.check_output(['git',*args])
assert git('rev-parse','HEAD').decode().strip()==e and git('show','-s','--format=%P',e).decode().strip()==p and git('show','-s','--format=%P',p).decode().strip()==s
assert git('diff','--name-only',p,e).decode().splitlines()==['scripts/case_pg_vertical/approval.json']
before=json.loads((ind/'source-before.json').read_text())['files'];after=json.loads((ind/'source-after.json').read_text())['files'];assert before==after and len(before)==445
for path,sha in before.items():
 assert h(git('show',s+':'+path))==sha and h(git('show',p+':'+path))==sha
 if path!='scripts/case_pg_vertical/approval.json':assert h(git('show',e+':'+path))==sha and h((r/path).read_bytes())==sha
assert all(x.startswith('docs/F2/') for x in git('diff','--name-only',s,p).decode().splitlines())
checks['commit_chain']={'source':s,'parent':p,'execution':e,'source_parent_docs_only':True,'execution_approval_only':True,'source_parent_files_equal':445,'execution_worktree_nonapproval_files_equal':444}
b=json.loads((rt/'actual-tool-bundle.json').read_text());assert b['run_original']==(rt/'actual-run-original.json').read_text() and b['job_log_original']==(rt/'actual-job-original.log').read_text() and b['jobs']==json.loads((rt/'actual-jobs.json').read_text())
run=json.loads(b['run_original']);jobs=b['jobs']['jobs'];summary=json.loads((rt/'actual-public-summary.json').read_text());line=(rt/'actual-public-summary-original-line.log').read_text();assert line in b['job_log_original'] and json.loads(line[line.index('{'):])==summary
assert run['id']==38341687876 and run['run_number']==run['run_attempt']==1 and run['conclusion']=='success' and run['head_sha']==e and run['repository']['private'] is False
assert len(jobs)==1 and jobs[0]['id']==115113871538 and jobs[0]['run_id']==run['id'] and jobs[0]['conclusion']=='success'
rows=json.loads((r/'scripts/case_pg_vertical/selection.json').read_text());assert len(rows)==len(summary['tests'])==27 and all(v=='PASS' for v in summary['tests'].values()) and len(summary['stages'])==7 and all(v=='PASS' for v in summary['stages'].values()) and summary['source_sha']==p
assert json.loads((a/'test-results.json').read_text())==[dict(v,outcome=summary['tests'][v['id']]) for v in rows]
checks['actual_run']={'id':run['id'],'job':jobs[0]['id'],'run_attempt':1,'run_number':1,'conclusion':'success','exact_tests':27,'separate_stages':7,'source_sha':p,'head_sha':e,'summary_log_line_bundle_and_jobs_agree':True}
projection=json.loads((rt/'actual-run-projection.json').read_text());assert projection['raw_response_sha256']==h(b['run_original'].encode())
for key in ['id','workflow_id','path','event','head_branch','head_sha','run_number','run_attempt','status','conclusion','created_at','updated_at','run_started_at','html_url']:assert projection[key]==run[key]
checks['git_state']={'branch':git('branch','--show-current').decode().strip(),'status':git('status','--porcelain').decode().splitlines()}
(out/'checks.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in checks.items() if k not in ['acceptance_exports','git_state']},indent=2))
