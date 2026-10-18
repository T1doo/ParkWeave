import hashlib,json,pathlib,sys,time
import pgserver
out=pathlib.Path(sys.argv[1]);mirror=pathlib.Path(sys.argv[2]);servers=[]
original=pgserver.get_server
def observed(data,*args,**kwargs):
 server=original(data,*args,**kwargs)
 pid=server.get_pid()
 servers.append(dict(data=str(pathlib.Path(data).resolve()),pid=pid,cleanup_mode=kwargs.get('cleanup_mode'),started=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]))
 (out/'owned-pg.json').write_text(json.dumps(servers,indent=2)+'\n')
 return server
pgserver.get_server=observed
import pytest
nodes=['tests/test_synthetic_rule_readiness_api.py::test_at22_api_business_date_region_and_reviewed_version_keep_original_history','tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe']
if len(sys.argv)>3 and sys.argv[3]=='static-only':nodes=nodes[1:]
started=time.perf_counter()
code=pytest.main(['-q','-p','no:cacheprovider',*nodes,'--basetemp='+str(mirror.parent/'artifacts'),'--junitxml='+str(out/'results.xml')])
origins={}
for name,module in sorted(sys.modules.items()):
 if name=='parkweave' or name.startswith('parkweave.') or name.startswith('test_') or name=='conftest':
  p=getattr(module,'__file__',None)
  if p:
   p=pathlib.Path(p);relative=str(p.relative_to(mirror));origins[name]=dict(relative=relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(out/'module-origins.json').write_text(json.dumps(origins,sort_keys=True,indent=2)+'\n')
(out/'result.json').write_text(json.dumps(dict(returncode=int(code),seconds=time.perf_counter()-started,nodes=nodes,actual_module_count=len(origins),actual_modules_all_from_mirror=True),indent=2)+'\n')
sys.exit(int(code))
