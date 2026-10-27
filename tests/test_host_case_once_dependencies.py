"""Offline lock/command regressions; no installation or OS log writes."""
from copy import deepcopy
from email.message import EmailMessage
import hashlib,json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from scripts.host_case_once import dependencies as d,controller as c
from test_host_case_once_candidate import no_physical_actions,context

LOCKS=Path(__file__).resolve().parents[1]/'scripts/host_case_once'

def test_locked_target_complete_extra_and_version_constraints():
    rows=d.load(LOCKS);by={r['name']:r for r in rows}
    env=default_environment();env.update(python_version='3.12',python_full_version='3.12.3',sys_platform='linux',
        platform_system='Linux',platform_machine='x86_64',implementation_name='cpython',platform_python_implementation='CPython')
    for row in rows:
        edges=set()
        for text in row['requires_dist']:
            req=Requirement(text)
            if req.marker is None or any(req.marker.evaluate({**env,'extra':x}) for x in (['','binary'] if row['name']=='psycopg' else [''])):
                name=canonicalize_name(req.name);assert name in by and by[name]['version'] in req.specifier;edges.add(name)
        assert edges==set(row['dependencies'])
    assert 'psycopg-binary' in by and len(rows)==19


def test_pip_download_hashes_full_target_then_install_offline_no_discovery(tmp_path):
    download,install=d.pip_commands(LOCKS,tmp_path/'wheels',tmp_path/'site')
    for command in (download,install):
        assert '--require-hashes' in command and '--no-deps' in command and '--isolated' in command
        assert command[command.index('-r')+1]==str(LOCKS/'requirements.lock')
    assert '--platform' in download and 'manylinux_2_17_x86_64' in download
    assert '--no-index' in install and '--find-links' in install and '--no-compile' in install
    assert '--index-url' not in install and '--extra-index-url' not in download


def synthetic_wheels(tmp_path):
    value=json.loads((LOCKS/'dependencies.lock.json').read_text());wheels=tmp_path/'wheels';wheels.mkdir()
    for row in value['packages']:
        metadata=('Name: '+row['name']+'\nVersion: '+row['version']+'\n'+
            ''.join('Requires-Dist: '+r+'\n' for r in row['requires_dist'])+'\n').encode()
        p=wheels/row['filename']
        with ZipFile(p,'w') as z:z.writestr(row['name']+'.dist-info/METADATA',metadata)
        row['bytes']=p.stat().st_size;row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    (tmp_path/'dependencies.lock.json').write_text(json.dumps(value))
    (tmp_path/'requirements.lock').write_text(''.join(r['name']+'=='+r['version']+' --hash=sha256:'+r['sha256']+'\n' for r in value['packages']))
    return wheels


def test_offline_verification_accepts_exact_closed_synthetic_set(tmp_path):
    assert d.verify(tmp_path,synthetic_wheels(tmp_path))==19


@pytest.mark.parametrize('change',['tampered','missing','extra','symlink'])
def test_offline_verifier_refuses_changed_set_before_install(tmp_path,change):
    wheels=synthetic_wheels(tmp_path);p=next(wheels.iterdir())
    if change=='tampered':p.write_bytes(p.read_bytes()+b'SYNTHETIC_TAMPER')
    elif change=='missing':p.unlink()
    elif change=='extra':(wheels/'unexpected.whl').write_bytes(b'SYNTHETIC')
    else:
        target=tmp_path/'original';p.rename(target);p.symlink_to(target)
    with pytest.raises(ValueError):d.verify(tmp_path,wheels)


def test_unhashed_requirement_or_missing_closure_refused(tmp_path):
    wheels=synthetic_wheels(tmp_path)
    (tmp_path/'requirements.lock').write_text('fastapi>=0\n')
    with pytest.raises(ValueError,match='HASHED'):d.verify(tmp_path,wheels)


@pytest.mark.parametrize('machine',['aarch64','i686'])
def test_unsupported_arch_refused_before_download(monkeypatch,machine):
    monkeypatch.setattr(d.platform,'machine',lambda:machine)
    with pytest.raises(PermissionError):d.supported_host()


def test_identity_commands_disable_existing_lastlog_faillog_initialization(monkeypatch):
    controller=c.Controller(context());commands=[];groups={};users={}
    def getuser(name):
        if name=='postgres':return SimpleNamespace(pw_uid=10,pw_gid=10,pw_name=name)
        if name not in users:raise KeyError(name)
        return users[name]
    def getgroup(name):
        if name not in groups:raise KeyError(name)
        return groups[name]
    def tool(args):
        commands.append(args)
        if args[0].endswith('groupadd'):
            groups[args[-1]]=SimpleNamespace(gr_gid=500+len(groups),gr_mem=['pwci_api','pwci_writer'])
        else:users[args[-1]]=SimpleNamespace(pw_uid=600+len(users),pw_gid=groups[args[-1]].gr_gid,pw_name=args[-1])
    monkeypatch.setattr(c.pwd,'getpwnam',getuser);monkeypatch.setattr(c.grp,'getgrnam',getgroup)
    monkeypatch.setattr(controller,'tool',tool);controller.identities()
    actual=[x for x in commands if x[0].endswith('useradd')]
    assert len(actual)==2
    for args,name in zip(actual,['pwci_api','pwci_writer']):
        assert args==['/usr/sbin/useradd','--system','--no-log-init','--no-create-home','--home-dir','/nonexistent',
            '--gid',name,'--groups','pwci_ipc','--shell','/usr/sbin/nologin',name]
