"""Injected actual driver failure path; no Chrome/server/font/model execution."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json,os,tempfile,time
from scripts import workspace_visual_browser_once as m
root=Path(tempfile.mkdtemp(prefix='driver-check-',dir=Path(__file__).parent))
class SDK:
 def __enter__(self):return SimpleNamespace(chromium=SimpleNamespace(launch=self.launch))
 def launch(self,**kwargs):
  assert kwargs['chromium_sandbox'] is True and kwargs['timeout']==15000
  raise TimeoutError('synthetic original launch failure')
 def __exit__(self,*args):raise RuntimeError('synthetic later SDK stop error')
class Server:
 def __init__(self,*args):self.server_port=12345
 def serve_forever(self):pass
 def shutdown(self):pass
 def server_close(self):pass
class Thread:
 def __init__(self,*args,**kwargs):pass
 def start(self):pass
 def join(self,**kwargs):pass
 def is_alive(self):return False
m.CHECKPOINT=root/'worker-state.json';m.REPORT=dict(status='RUNNING',stage='START',cleanup_errors=[])
with patch.dict(os.environ,{'RUNNER_TEMP':str(root)}),patch.object(m.base,'require_hosted',return_value='214fc8b07afa2d541b9b49d010a78f7537e7eb78'),patch.object(m,'installed_font_environment',side_effect=lambda env,*args:env),patch.object(m,'sync_playwright',return_value=SDK()),patch.object(m,'ThreadingHTTPServer',Server),patch.object(m.threading,'Thread',Thread),patch.object(m.socket,'create_connection',side_effect=ConnectionRefusedError):
 code=m.run_flow(time.monotonic())
r=json.loads(m.CHECKPOINT.read_text())
assert code==1 and r['status']=='FAIL'
assert r['error_type']=='TimeoutError' and r['error']=='synthetic original launch failure'
assert r['later_errors']==[{'type':'RuntimeError','error':'synthetic later SDK stop error'}]
assert r['worker_final'] and any(e['stage']=='CHROME_SANDBOX' and e['error_type']=='TimeoutError' for e in r['phase_timeline'])
print(json.dumps({'status':'PASS','injected_driver_primary_preserved':True,'later_error_preserved':True,'worker_final_checkpoint':True,'actual_browser_runs':0,'actual_servers_started':0,'CI_runs':0},indent=2))
