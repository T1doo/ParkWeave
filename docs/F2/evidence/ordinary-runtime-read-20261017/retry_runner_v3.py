"""Same frozen test invocation; file-only PG log capture, no database lifecycle references."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
root=Path('/workspace/ParkWeave');out=root/'.runtime/runtime-read';freeze=json.loads((out/'freeze.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==freeze['source_sha']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
base=Path('/tmp/parkweave-runtime-read-final-v3')
assert not base.exists(),'new owned test output only; do not overwrite a prior run'
assert not (out/'final-v3-writer').exists()
log=out/'final-v3.log';assert not log.exists()
argv=[str(root/'.venv/bin/python'),'-m','pytest',*freeze['modules'],'-q','--basetemp='+str(base),'--junitxml='+str(out/'final-v3.xml')]
source=base/'parkweave-pg0/data/log';saved=out/'final-v3-postgres.log';last=None;copies=0
meta={'development_profile':json.loads((out/'editable-profile.json').read_text()),'evidence_env':{k:os.environ.get(k) for k in ['PARKWEAVE_WRITER_EVIDENCE_DIR','PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR']},'source_sha':freeze['source_sha'],'argv':argv,'monitor':'file-only copy of this owned data/log; no pgserver import, connection, SQL, lifecycle or test modification','monitor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'final-v3-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
with log.open('xb') as sink:
 child=subprocess.Popen(argv,cwd=root,stdout=sink,stderr=subprocess.STDOUT)
 meta['pytest_pid']=child.pid
 (out/'final-v3-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
 while child.poll() is None:
  try:
   st=source.stat();mark=(st.st_size,st.st_mtime_ns)
   if mark!=last:
    raw=source.read_bytes();saved.write_bytes(raw);last=mark;copies+=1
  except FileNotFoundError:pass
  time.sleep(.5)
 result=child.wait()
meta.update(exit_code=result,log_copies=copies,pg_log_saved=saved.exists())
(out/'final-v3-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(meta))
sys.exit(result)
