from pathlib import Path
import json,hashlib,sys
from scripts.windows_ci import source_bytes
root=Path.cwd();head=sys.argv[2];hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'tests').glob('test_*.py')}
original=source_bytes._git;calls=[]
def observe(root,args,data=None):
 result=original(root,args,data);record=dict(args=args,returned_bytes=len(result))
 if args==['cat-file','--batch']:
  paths=[x.split(':',1)[1] for x in data.decode().splitlines()];record.update(paths=paths,body_bytes=sum((root/p).stat().st_size for p in paths))
 calls.append(record);return result
source_bytes._git=observe;source_bytes.verify_head_test_sources(root,head,hashes)
result=dict(head=head,files=len(hashes),aggregate_bytes=sum((root/p).stat().st_size for p in hashes),calls=calls,hashes=hashes,all_paths_checked=True,source_binding_passed=True,acceptance_runner_invoked=False)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('hashes','calls')}))
