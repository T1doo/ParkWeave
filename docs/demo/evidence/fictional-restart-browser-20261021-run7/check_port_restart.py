"""Bounded local loopback causal regression; no API/PG/browser/model or CI."""
import ast
import errno
import json
from pathlib import Path
import socket
import subprocess
from scripts import ordinary_synthetic_demo as demo

BASELINE='cd42c06ecd2a1094ef48000afb302c47e5ebd77a'
source=subprocess.check_output(['git','show',BASELINE+':scripts/ordinary_synthetic_demo.py'],text=True)
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='check_port')
space=dict(socket=socket,Denied=demo.Denied)
exec(compile(ast.Module(body=[node],type_ignores=[]),'exact_baseline_check_port','exec'),space)
old=space['check_port']
report=dict(scope='LOCAL_SOCKET_CAUSAL_REGRESSION_NOT_RUN7_ERRNO',baseline_sha=BASELINE,
    API_started=False,PG_started=False,browser_started=False,model_calls=0,CI_started=False,
    actual_run7_errno_known=False)
with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];listener.listen(1)
    with socket.create_connection(('127.0.0.1',port),timeout=2) as peer:
        accepted,_=listener.accept()
        with accepted:
            accepted.settimeout(2)
            accepted.shutdown(socket.SHUT_WR)
            assert peer.recv(1)==b''
            peer.shutdown(socket.SHUT_WR)
            assert accepted.recv(1)==b''
    listener.close()
    try:old(port)
    except OSError as error:
        assert error.errno==errno.EADDRINUSE
        report['baseline_stopped_listener_TIME_WAIT']='FAIL_EXPECTED_EADDRINUSE'
    else:raise AssertionError('baseline counterexample absent')
    demo.check_port(port)
    report['fixed_stopped_listener_TIME_WAIT']='PASS'
    with socket.socket() as live:
        live.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        live.bind(('127.0.0.1',port));live.listen(1)
        try:demo.check_port(port)
        except OSError as error:
            assert error.errno==errno.EADDRINUSE
            report['fixed_active_listener']='REFUSED_EXPECTED_EADDRINUSE'
        else:raise AssertionError('active listener shared')
        with socket.create_connection(('127.0.0.1',port),timeout=2):pass
        report['active_listener_preserved']=True
output=Path(__file__).with_name('port-restart-regression.json')
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
