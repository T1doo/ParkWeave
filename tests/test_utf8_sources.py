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
        called.append(command);Path(command[command.index('--junitxml')+1]).write_bytes(b'<testsuite><testcase classname="test_foundation" name="test_observed"/></testsuite>');return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(current.subprocess,'run',run)
    with pytest.raises(SystemExit) as refused:old.main()
    assert refused.value.code==1 and not called
    rejected=json.loads((tmp_path/'result.json').read_bytes())
    assert rejected['acceptance_failure']=={'stage':'ACCEPTANCE_BINDINGS','reason':'ACCEPTANCE_BINDINGS_INVALID','category':'UnicodeDecodeError'}
    assert rejected['coverage_complete'] is False and rejected['execution_exit_code']==1
    with pytest.raises(SystemExit) as done:current.main()
    assert done.value.code==0 and len(called)==1
    result=json.loads((tmp_path/'result.json').read_bytes());assert result['execution_exit_code']==0 and result['whole_AT_EX']=='NOT_RUN'
    # Existing source content really cannot be read in that Windows fallback codec.
    with pytest.raises(UnicodeDecodeError):(ROOT/'docs/验收规格.json').read_bytes().decode('cp1252')


@pytest.mark.parametrize('legacy,expected',[(True,500),(False,200)])
def test_actual_chinese_UI_http_under_non_utf8_path_default(tmp_path,monkeypatch,legacy,expected):
    api_path=ROOT/'src/parkweave/api.py'
    source=api_path.read_text(encoding='utf-8')
    if legacy:
        target="""with_name("web.html").read_text(encoding='utf-8')"""
        assert target in source
        source=source.replace(target,'with_name("web.html").read_text()')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    import threading
    import uvicorn
    import parkweave.api  # Load infrastructure before the exact web-file codec simulation.
    web=api_path.with_name('web.html');original=Path.open
    def fallback(path,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
        if path==web and 'b' not in mode and encoding in (None,'locale'):encoding='cp1252'
        return original(path,mode,buffering,encoding,errors,newline)
    monkeypatch.setattr(Path,'open',fallback)
    m=types.ModuleType('parkweave.encoding_api');m.__package__='parkweave';m.__file__=str(api_path)
    exec(compile(source,m.__file__,'exec'),m.__dict__)
    server=uvicorn.Server(uvicorn.Config(m.create_app(object()),host='127.0.0.1',port=port,log_level='critical'))
    failures=[]
    def serve():
        try:server.run()
        except BaseException as error:failures.append(error)
    thread=threading.Thread(target=serve,daemon=True);thread.start()
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));response=None
        for _ in range(100):
            try:response=opener.open('http://127.0.0.1:'+str(port)+'/',timeout=1);break
            except urllib.error.HTTPError as error:response=error;break
            except OSError:
                if not thread.is_alive():raise AssertionError('owned encoding HTTP server exited')
                time.sleep(.05)
        assert response is not None and not failures
        with response:
            assert response.status==expected
            if not legacy:
                assert response.headers['Content-Type']=='text/html; charset=utf-8'
                assert response.read()==web.read_bytes()
    finally:
        server.should_exit=True;thread.join(timeout=10)
        assert not thread.is_alive() and not failures
