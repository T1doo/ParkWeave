"""Shared process helpers must not require a Linux-only database package."""
import subprocess
import sys
from pathlib import Path


def test_shared_process_helper_import_and_platform_refusal_without_pgserver():
    root=Path(__file__).resolve().parents[1]
    code=r'''
import builtins,sys
sys.path.insert(0,'tests')
original=builtins.__import__
def checked(name,*args,**kwargs):
    if name=='pgserver':raise AssertionError('Linux database dependency imported')
    return original(name,*args,**kwargs)
builtins.__import__=checked
from ordinary_case_step_support import stop_children
from scripts import linux_fixture_server as demo
from parkweave.store import Denied
assert 'pgserver' not in sys.modules
sys.platform='win32'
def forbidden(*args,**kwargs):raise AssertionError('Temporary database directory created')
demo.tempfile.mkdtemp=forbidden
try:
    with demo.demo_database(True):raise AssertionError('Windows entered Linux database')
except Denied:pass
class Child:
    def __init__(self):self.exit=None;self.stopped=False
    def poll(self):return self.exit
    def terminate(self):self.stopped=True
    def wait(self,timeout):self.exit=0;return 0
child=Child();stop_children([child])
assert child.stopped and child.exit==0
print('SHARED_HELPER_IMPORT_AND_PLATFORM_REFUSAL_OK')
'''
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=root,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='SHARED_HELPER_IMPORT_AND_PLATFORM_REFUSAL_OK'
