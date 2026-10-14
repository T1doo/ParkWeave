from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
root=Path('/workspace/parkweave-at-review-20261014')
base=root/'.runtime/at-independent';manifest=json.loads((base/'frozen-source.json').read_text())
stage=base/'final-wheel-stage';stage.mkdir()
files={name:sha for name,sha in manifest['sha256'].items() if name.startswith('src/parkweave/')}
for name in [*files,'pyproject.toml']:
 p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
out=base/'final-wheel';out.mkdir()
cmd=['/workspace/ParkWeave/.venv/bin/python','-c','import setuptools.build_meta as b; print(b.build_wheel('+repr(str(out))+'))']
run=subprocess.run(cmd,cwd=stage,text=True,capture_output=True)
(base/'final-wheel.log').write_text(run.stdout+run.stderr);(base/'final-wheel.exit').write_text(str(run.returncode)+'\n')
assert run.returncode==0,run.stderr
wheel=next(out.glob('*.whl'))
with zipfile.ZipFile(wheel) as z:
 names={n for n in z.namelist() if n.startswith('parkweave/') and not n.endswith('/')}
 expected={n[4:] for n in files};missing=sorted(expected-names);extra=sorted(names-expected)
 changed=[name for name,sha in files.items() if name[4:] in names and hashlib.sha256(z.read(name[4:])).hexdigest()!=sha]
 result=dict(source_commit=manifest['source_commit'],files=len(files),missing=missing,extra=extra,changed=changed,wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),result='PASS' if not(missing or extra or changed) else 'FAIL')
 (base/'final-wheel-evidence.json').write_text(json.dumps(result,indent=2))
 assert result['result']=='PASS',result
 print(json.dumps(result))
