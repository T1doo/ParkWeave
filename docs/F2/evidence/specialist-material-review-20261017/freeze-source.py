from pathlib import Path
import json,subprocess,hashlib,datetime,collections
r=Path('/workspace/ParkWeave');p=r/'.runtime/specialist-material-review'
sha=lambda b:hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=r,text=True)
assert git('status','--porcelain')==''
files=git('ls-files','src','tests','scripts','pyproject.toml','requirements*.txt').splitlines()
f=dict(base_sha='5a1771aa337b00c4366c46a40752d1442e8ebf22',source_sha=git('rev-parse','HEAD').strip(),branch=git('branch','--show-current').strip(),files={s:sha((r/s).read_bytes()) for s in files},modules=json.loads((p/'modules.json').read_text()),contract_sha256=sha((r/'docs/F2/SpecialistMaterialReviewContract-20261017.md').read_bytes()),recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
assert len(files)==len(set(files))
(p/'freeze.json').write_text(json.dumps(f,indent=2)+'\n')
argv=['.venv/bin/python','-m','pytest',*f['modules'],'--collect-only','-q'];result=subprocess.run(argv,cwd=r,capture_output=True,text=True);(p/'final-collection.txt').write_text(result.stdout);(p/'final-collection.stderr').write_text(result.stderr);assert result.returncode==0
nodes=[line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line];assert len(nodes)==len(set(nodes))
(p/'final-nodes.json').write_text(json.dumps(nodes,indent=2)+'\n');counts=dict(collections.Counter(s.split('::')[0] for s in nodes))
(p/'collection-invocation.json').write_text(json.dumps(dict(source_sha=f['source_sha'],argv=argv,exit_code=result.returncode,unique=len(nodes),modules=counts),indent=2)+'\n')
print(json.dumps(dict(source_sha=f['source_sha'],source_inputs=len(files),unique=len(nodes),module_unique=counts)))
