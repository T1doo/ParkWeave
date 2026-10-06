"""CP1252 fallback simulation only; never change host locale or child OS whitelist."""
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request
import pytest
from parkweave.process_env import minimal_environment

ROOT=Path(__file__).resolve().parents[1]


def cp1252_default(monkeypatch):
    original=Path.open
    def open_path(path,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
        if 'b' not in mode and encoding in (None,'locale'):encoding='cp1252'
        return original(path,mode,buffering,encoding,errors,newline)
    monkeypatch.setattr(Path,'open',open_path)


def acceptance_module(legacy=False):
    path=ROOT/'scripts/run_acceptance.py';m=types.ModuleType('encoding_acceptance');m.__file__=str(path)
    source=path.read_text(encoding='utf-8')
    if legacy:
        target="(ROOT/'docs/验收规格.json').read_text(encoding='utf-8')"
        assert target in source
        source=source.replace(target,"(ROOT/'docs/验收规格.json').read_text()")
    exec(compile(source,str(path),'exec'),m.__dict__);return m


def test_acceptance_old_default_cp1252_failure_and_current_utf8_specs_report(tmp_path,monkeypatch):
    old=acceptance_module(True);current=acceptance_module();called=[];cp1252_default(monkeypatch)
    monkeypatch.setattr(sys,'argv',['run_acceptance','--report',str(tmp_path/'result.json')])
    def run(command,**kwargs):
        called.append(command);Path(command[command.index('--junitxml')+1]).write_bytes(b'<testsuites/>');return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(current.subprocess,'run',run)
    with pytest.raises(UnicodeDecodeError):old.main()
    assert not called
    with pytest.raises(SystemExit) as done:current.main()
    assert done.value.code==0 and len(called)==1
    result=json.loads((tmp_path/'result.json').read_bytes());assert result['execution_exit_code']==0 and result['whole_AT_EX']=='NOT_RUN'
    # Existing source content really cannot be read in that Windows fallback codec.
    with pytest.raises(UnicodeDecodeError):(ROOT/'docs/验收规格.json').read_bytes().decode('cp1252')


@pytest.mark.parametrize('legacy,expected',[(True,500),(False,200)])
def test_actual_chinese_UI_http_under_non_utf8_path_default(tmp_path,legacy,expected):
    api_path=ROOT/'src/parkweave/api.py'
    source=api_path.read_text(encoding='utf-8')
    if legacy:
        target="""with_name("web.html").read_text(encoding='utf-8')"""
        assert target in source
        source=source.replace(target,'with_name("web.html").read_text()')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    code='''import sys,types
from pathlib import Path
sys.path.insert(0,''' + repr(str(ROOT/'src'))+''')
original=Path.open
def fallback(path,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
    if 'b' not in mode and encoding in (None,'locale'):encoding='cp1252'
    return original(path,mode,buffering,encoding,errors,newline)
Path.open=fallback
m=types.ModuleType('parkweave.encoding_api');m.__package__='parkweave';m.__file__='''+repr(str(api_path))+'''
exec(compile('''+repr(source)+''',m.__file__,'exec'),m.__dict__)
import uvicorn
uvicorn.run(m.create_app(object()),host='127.0.0.1',port='''+str(port)+''',log_level='error')
'''
    log=(tmp_path/'owned-http.log').open('wb');proc=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,env=minimal_environment(__import__('os').environ),stdout=log,stderr=log)
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));response=None
        for _ in range(100):
            try:response=opener.open('http://127.0.0.1:'+str(port)+'/',timeout=1);break
            except urllib.error.HTTPError as error:response=error;break
            except OSError:
                if proc.poll() is not None:raise AssertionError('owned encoding HTTP server exited')
                time.sleep(.05)
        assert response is not None
        with response:
            assert response.status==expected
            if not legacy:
                assert response.headers['Content-Type']=='text/html; charset=utf-8'
                assert response.read()==(ROOT/'src/parkweave/web.html').read_bytes()
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
        log.close()
