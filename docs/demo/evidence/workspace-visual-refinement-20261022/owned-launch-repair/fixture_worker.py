import json,os,signal,subprocess,sys,time
from pathlib import Path
hand=json.loads(sys.stdin.buffer.readline(4096));assert hand['worker_pid']==os.getpid() and hand['parent_pid']==os.getppid()
scenario=sys.argv[1]
if scenario=='normal':raise SystemExit(0)
if scenario=='orphan':
 subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);raise SystemExit(1)
if scenario=='double_fork_setsid':
 pid=os.fork()
 if pid==0:
  os.setsid();pid=os.fork()
  if pid:os._exit(0)
  signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30);os._exit(0)
 os._exit(1)
if scenario=='stubborn':
 signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)
if scenario=='primary_checkpoint':
 from scripts.visual_owned_launch import atomic_report
 atomic_report(Path(sys.argv[2]),{'status':'FAIL','stage':'CHROME_LAUNCH_SIMULATED','error_type':'InjectedLaunchTimeout','error':'original primary failure','worker_final':False})
 print('untrusted log pid='+sys.argv[3],flush=True)
 signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)
if scenario=='short_orphan':
 subprocess.Popen([sys.executable,'-c','import time;time.sleep(.4)']);raise SystemExit(1)

if scenario=='term_fork':
 def late(*_):
  child=os.fork()
  if child==0:
   os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30);os._exit(0)
  os._exit(1)
 signal.signal(signal.SIGTERM,late);time.sleep(30)
