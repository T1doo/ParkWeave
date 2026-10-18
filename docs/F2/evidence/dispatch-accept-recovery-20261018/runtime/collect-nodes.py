from pathlib import Path
import os,sys,json,subprocess,time,re
from parkweave.process_env import minimal_environment
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018';plan=json.load(open(r/'final-v2-plan.json'));modules=plan['shards']['A']+plan['shards']['B']
old=r/'final-v2-collection.log'
module_counts={m.group(1):int(m.group(2)) for m in re.finditer(r'^(tests/[^\n]+\.py): (\d+)$',old.read_text(),re.M)}
(r/'collection-format-correction.json').write_text(json.dumps(dict(first_parser_status='WRONG_QUIET_FORMAT',first_raw_actual_module_counts=module_counts,first_raw_actual_collected=sum(module_counts.values()),first_metadata_reported_parser_nodes=0,executed_tests=0,source_or_test_changed=False,first_log_and_metadata_unchanged=True),indent=2)+'\n')
argv=[sys.executable,'-B','-m','pytest','--collect-only','-q','-p','no:cacheprovider','--rootdir='+str(root),*modules]
env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(str(root/p) for p in ['tests','src','.']),PYTHONDONTWRITEBYTECODE='1')
start=time.time();p=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True)
(r/'final-v2-node-collection.log').write_text(p.stdout+p.stderr);ids=[x for x in p.stdout.splitlines() if x.startswith('tests/') and '::' in x]
result=dict(source_sha=plan['source_sha'],argv=argv,cwd=str(root),exit_code=p.returncode,elapsed_seconds=time.time()-start,collected_count=len(ids),unique=len(set(ids)),test_nodes=ids,kind='COLLECTION_ONLY',executed_tests=0)
(r/'final-v2-node-collection.json').write_text(json.dumps(result,indent=2)+'\n');assert p.returncode==0 and len(ids)==len(set(ids))==sum(module_counts.values())>0;print({k:v for k,v in result.items() if k not in ['test_nodes','argv']})
