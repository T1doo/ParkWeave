"""Verify a frozen Windows private runtime with imports only; no server or DB."""
from pathlib import Path
import os,subprocess,json,hashlib
from scripts.windows_portable.payload import verify_directory
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
if os.name!='nt':raise RuntimeError('NATIVE_WINDOWS_REQUIRED')
root=args.payload.resolve();m=verify_directory(root)
keys=('SystemRoot','WINDIR','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)')
env={k:v for k,v in os.environ.items() if k.upper() in {name.upper() for name in keys}};env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
code="import sys,json,fastapi,psycopg,pydantic,uvicorn; import parkweave.api; print(json.dumps({'python':sys.version.split()[0],'fastapi':fastapi.__version__,'psycopg':psycopg.__version__,'pydantic':pydantic.__version__,'application_import':'PASS'}))"
r=subprocess.run([str(root/'runtime/python/python.exe'),'-I','-B','-S','-X','utf8','-c',code],cwd=root,env=env,text=True,capture_output=True,timeout=30)
report={'scope':'VERIFIED_PRIVATE_RUNTIME_IMPORT_ONLY_NO_DATABASE_OR_SERVER','exit_code':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr[-2500:],'source_snapshot_sha256':m.get('source_snapshot_sha256'),'manifest_sha256':hashlib.sha256((root/'payload-manifest.json').read_bytes()).hexdigest(),'usable_product':False}
assert verify_directory(root)==m
args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
raise SystemExit(0 if r.returncode==0 else 1)
