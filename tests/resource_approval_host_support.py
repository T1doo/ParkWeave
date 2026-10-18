"""Owned SAME-UID SYNTHETIC transport lab. Never a production host installer.

Positive factory DI replaces only _load_binding's OS installation boundary.
Actual socket inode, process start, SO_PEERCRED, framing, RPC and old business
checks remain in use. No production identity or approval authority is created.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

from parkweave import resource_approval_host_read as host
from parkweave.resource_plan_approval_read import ReadOnlyApprovalProvider
from parkweave.native_run_access_writer import _pid_started
from parkweave.process_env import minimal_environment


def fixture_binding(cfg):
    raw=Path(cfg.binding_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==cfg.binding_sha256
    binding=host.Binding.model_validate(host.strict_json(raw))
    assert binding.source_kind=='SYNTHETIC_CONTRACT_FIXTURE'
    host._endpoint(binding)
    return binding


def fixture_app():
    # Explicit test-only protection DI, not the unmodified production CLI factory.
    host._load_binding=fixture_binding
    from parkweave.api import configured_app
    return configured_app()


@contextmanager
def running_host(directory,source=None,mode='normal'):
    directory.mkdir();bootstrap=directory/'host.fixture-private'
    data=dict(directory=str(directory),mode=mode)
    if source is not None:data.update(source_directory=str(source.path.parent),synthetic_key=source.key.hex())
    bootstrap.write_text(json.dumps(data));bootstrap.chmod(0o600)
    root=Path(__file__).resolve().parents[1]
    env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join([str(root/'tests'),str(root/'src')]),PYTHONDONTWRITEBYTECODE='1')
    log=(directory/'host.log').open('w')
    process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),str(bootstrap)],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        until=time.monotonic()+5
        while not (directory/'binding.json').exists():
            if process.poll() is not None or time.monotonic()>=until:raise AssertionError((directory/'host.log').read_text())
            time.sleep(.01)
        raw=(directory/'binding.json').read_bytes()
        cfg=host.Config(schema_version=host.PROTOCOL,binding_path=str(directory/'binding.json'),binding_sha256=hashlib.sha256(raw).hexdigest())
        binding=host.Binding.model_validate(host.strict_json(raw))
        yield cfg,binding,process
    finally:
        if process.poll() is None:process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        log.close()


def serve(bootstrap):
    cfg=json.loads(Path(bootstrap).read_text());directory=Path(cfg['directory']);mode=cfg['mode']
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    listener.bind(str(directory/'source.sock'));os.chmod(directory/'source.sock',0o660);listener.listen(8)
    s=(directory/'source.sock').lstat()
    binding=host.Binding(schema_version='parkweave-resource-approval-host-binding/1',
        source_id='SYNTHETIC-existing-source',source_kind='SYNTHETIC_CONTRACT_FIXTURE',backend_contract_id='SYNTHETIC-file-head:1',
        api_uid=os.geteuid(),api_gid=os.getegid(),host_uid=os.geteuid(),host_gid=os.getegid(),
        socket_path=str(directory/'source.sock'),socket_device=s.st_dev,socket_inode=s.st_ino,
        host_pid=os.getpid(),host_started=str(_pid_started(os.getpid())),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    raw=binding.model_dump_json().encode();sha=hashlib.sha256(raw).hexdigest()
    calls=directory/'calls.jsonl';counts={'READ_EXISTING':0,'VERIFY_EXISTING':0}
    source=None
    if 'source_directory' in cfg:
        from resource_approval_read_support import SignedFixtureSource
        source=SignedFixtureSource(Path(cfg['source_directory']));source.key=bytes.fromhex(cfg['synthetic_key'])
    def observe(op,lookup):
        counts[op]+=1
        with calls.open('a') as out:out.write(json.dumps(dict(operation=op,approval_id=str(lookup.approval_id) if lookup.approval_id else None,time=time.monotonic()))+'\n')
        if mode=='slow':time.sleep(.55)
    def read(lookup):
        observe('READ_EXISTING',lookup)
        if source is None:return b'{"SYNTHETIC":"existing raw bytes"}'
        if mode=='replace' and counts['READ_EXISTING']==2:
            from datetime import datetime,timezone
            value=source.record();value.update(state='REVOKED',record_revision=2,revoked_at=datetime.now(timezone.utc).isoformat());source.write(value)
        return source.read(lookup)
    def verify(lookup,raw):
        observe('VERIFY_EXISTING',lookup)
        return False if mode=='final_false' and counts['VERIFY_EXISTING']==3 else source.verify(lookup,raw) if source else True
    provider=ReadOnlyApprovalProvider(binding.source_id,read,verify,binding.source_kind)
    dispatcher=host.ReadOnlyDispatcher(provider,binding,sha)
    # Publishing this SAME-UID fixture pin is a test action, not product behavior.
    temp=directory/'binding.pending';temp.write_bytes(raw);temp.rename(directory/'binding.json')
    if mode in ('normal','slow','replace','final_false'):
        host.serve_listener(listener,dispatcher,threading.Event())
    else:
        while True:
            channel,_=listener.accept()
            try:
                raw=host._receive(channel,time.monotonic()+2)
                reply=host.strict_json(dispatcher.dispatch(raw))
                if mode=='nonce':reply['nonce']='0'*32
                elif mode=='request':reply['request_sha256']='0'*64
                elif mode=='pin':reply['binding_sha256']='0'*64
                elif mode=='source':reply['source_id']='other'
                elif mode=='integer':reply['result']=1
                encoded=host._canonical(reply)+b'\n'
                if mode=='duplicate':encoded=b'{"protocol":"x","protocol":"y"}\n'
                elif mode=='truncated':encoded=encoded[:-1]
                elif mode=='oversize':encoded=b'x'*(host.MAX_FRAME+1)+b'\n'
                elif mode=='slowloris':
                    for byte in encoded:
                        channel.sendall(bytes([byte]));time.sleep(.1)
                    continue
                channel.sendall(encoded)
            except (OSError,ValueError):pass
            finally:channel.close()


if __name__=='__main__':serve(sys.argv[1])
