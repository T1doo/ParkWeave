from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
root=Path.cwd();base=root/'.runtime/template-local-migration-20261014';stage=base/'wheel-stage';stage.mkdir(exist_ok=True)
shutil.copyfile(root/'pyproject.toml',stage/'pyproject.toml')
shutil.copytree(root/'src/parkweave',stage/'src/parkweave',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
args=[str(root/'.venv/bin/python'),'-m','pip','wheel','--no-deps','--no-build-isolation','--no-index','--wheel-dir',str(base/'wheels'),str(stage)]
with (base/'wheel.log').open('w') as out:code=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT).returncode
(base/'wheel.exit').write_text(str(code)+'\n');assert code==0
wheel=next((base/'wheels').glob('*.whl'))
expected={str(p.relative_to(root/'src')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src/parkweave').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
with zipfile.ZipFile(wheel) as z:actual={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('parkweave/') and not n.endswith('/')}
missing=sorted(expected.keys()-actual.keys());extra=sorted(actual.keys()-expected.keys());changed=sorted(n for n in expected.keys()&actual.keys() if expected[n]!=actual[n])
report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),wheel=wheel.name,wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),package_files=len(expected),missing=missing,extra=extra,changed=changed,offline=True,exit_code=code)
(base/'wheel-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert not(missing or extra or changed)
