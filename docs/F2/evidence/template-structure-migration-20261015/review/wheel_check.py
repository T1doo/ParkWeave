from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = sys.argv[1]
wheel_dir = OUT/'final-wheel'
wheel_dir.mkdir(exist_ok=False)
build_source = OUT/'wheel-source'
build_source.mkdir(exist_ok=False)
shutil.copy2(ROOT/'pyproject.toml', build_source/'pyproject.toml')
shutil.copytree(ROOT/'src/parkweave', build_source/'src/parkweave',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
command = [sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
           '--no-index', '.', '-w', str(wheel_dir)]
with (OUT/'final-wheel-build.log').open('wb') as log:
    run = subprocess.run(command, cwd=build_source, stdout=log, stderr=subprocess.STDOUT)
(OUT/'final-wheel-build.exit').write_text(str(run.returncode)+'\n')
if run.returncode:
    raise SystemExit(run.returncode)
wheels = list(wheel_dir.glob('*.whl'))
assert len(wheels) == 1
files = {str(p.relative_to(ROOT/'src')): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted((ROOT/'src/parkweave').rglob('*'))
         if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')}
with zipfile.ZipFile(wheels[0]) as z:
    packaged = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()
                if n.startswith('parkweave/') and not n.endswith('/')}
differences = {p: [files.get(p), packaged.get(p)] for p in files.keys() | packaged.keys()
               if files.get(p) != packaged.get(p)}
report = dict(source_sha=SOURCE, scope='offline wheel bytes only; no install/deploy',
              wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
              source_files=len(files), wheel_files=len(packaged), differences=differences,
              exact=not differences, source_file_sha256=files)
(OUT/'final-wheel-review.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='source_file_sha256'}))
raise SystemExit(0 if not differences else 1)
