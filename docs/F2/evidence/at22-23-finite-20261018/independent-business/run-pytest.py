from pathlib import Path
from hashlib import sha256
import json,os,sys,time
out=Path(sys.argv[1]);mirror=Path(sys.argv[2]);base=mirror.parent
assert os.geteuid()!=0
import pgserver
servers=[];original=pgserver.get_server
def write(name,value):(out/name).write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
def observed(data,*args,**kwargs):
 server=original(data,*args,**kwargs);pid=server.get_pid();p=Path('/proc')/str(pid)/'stat'
 stat=p.read_text().rsplit(')',1)[1].split()
 record={'data':str(Path(data).resolve()),'pid':pid,'cleanup_mode':kwargs.get('cleanup_mode'),'started':stat[19],'state_at_start':stat[0]}
 assert Path(record['data']).is_relative_to(base)
 servers.append(record);write('owned-pg.json',servers)
 return server
pgserver.get_server=observed
import pytest
nodes=json.loads((out/'expected-nodes.json').read_text())['nodes']
class Observation:
 def __init__(self):self.collected=[];self.reports=[]
 def pytest_collection_finish(self,session):
  self.collected=[i.nodeid for i in session.items];write('actual-collected-nodes.json',{'ids':self.collected})
 def pytest_runtest_logreport(self,report):
  self.reports.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'duration_seconds':report.duration})
  write('phase-reports.json',{'reports':self.reports})
observer=Observation()
argv=['-q','-p','no:cacheprovider','--rootdir='+str(mirror),'--basetemp='+str(base/'artifacts'),'--junitxml='+str(out/'results.xml'),*nodes]
write('pytest-argv.json',{'args':argv,'cwd':str(Path.cwd()),'euid':os.geteuid()})
started=time.perf_counter();code=pytest.main(argv,plugins=[observer]);elapsed=time.perf_counter()-started
origins={}
for name,module in sorted(sys.modules.items()):
 if name=='parkweave' or name.startswith('parkweave.') or name.startswith('test_') or name in ('conftest','owned_connection_diagnostics','parkweave_acceptance') or name=='scripts' or name.startswith('scripts.'):
  path=getattr(module,'__file__',None)
  if path:
   path=Path(path).resolve();relative=path.relative_to(mirror).as_posix()
   origins[name]={'relative':relative,'sha256':sha256(path.read_bytes()).hexdigest()}
write('module-origins.json',origins)
for index,server in enumerate(servers):
 log=Path(server['data'])/'log'
 if log.is_file():(out/('owned-pg-'+str(index)+'-before-atexit.log')).write_bytes(log.read_bytes())
write('pytest-result.json',{'source_sha':'3c0ba9bb816b270116ddcca771829443dac6dd1e','returncode':int(code),'elapsed_seconds':elapsed,'collected_ids':observer.collected,'phase_reports':observer.reports,'actual_module_count':len(origins),'actual_modules_all_from_mirror':True,'python_version':sys.version,'python_executable':sys.executable,'pytest_version':pytest.__version__})
sys.exit(int(code))
