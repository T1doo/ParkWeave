import json,os,sys,time
from pathlib import Path
from unittest.mock import patch
from scripts import visual_owned_launch as m
scenario=sys.argv[1];root=Path(sys.argv[2]);worker=Path(__file__).with_name('fixture_worker.py');state=root/'worker-state.json'
argv=[sys.executable,'-B',str(worker),scenario,str(state),sys.argv[3]]
kw=dict(env=dict(os.environ),cwd='/workspace/ParkWeave',directory=root,started=time.monotonic(),overall_seconds=4,work_seconds=1.2,term_seconds=.3,kill_seconds=.4,minimum_operation_seconds=.05)
if scenario=='pidfd_denied':
 with patch.object(m.os,'pidfd_open',side_effect=PermissionError(13,'injected preflight denial')):r=m.supervise(argv,**kw)
elif scenario=='enumeration_failure':
 count=[0];original=m.snapshot
 def fault():
  count[0]+=1
  if count[0]>1:raise OSError(5,'injected enumeration failure')
  return original()
 argv[3]='stubborn'
 with patch.object(m,'snapshot',side_effect=fault):r=m.supervise(argv,**kw)
elif scenario=='signal_denied':
 argv[3]='short_orphan'
 with patch.object(m.signal,'pidfd_send_signal',side_effect=PermissionError(13,'injected signal denial')):r=m.supervise(argv,**kw)
else:r=m.supervise(argv,**kw)
if state.exists():r['preserved_checkpoint']=json.loads(state.read_text())
print(json.dumps(r))
