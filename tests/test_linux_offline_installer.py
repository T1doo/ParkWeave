"""Real ordinary files/Git and lifecycle protocol; no PG or Windows execution."""
from hashlib import sha256
import json,subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.linux_local import manage


def payload(root):
    root.mkdir(mode=0o700);raw=b'owned software fixture'
    (root/'install.py').write_bytes(raw)
    value=dict(schema='parkweave-linux-offline-candidate/1',scope='LINUX_SYNTHETIC_ONLY',usable_product=False,
        source_commit='a'*40,branch='dev/local-product-runtime-20261028',files={'install.py':dict(bytes=len(raw),sha256=sha256(raw).hexdigest())})
    (root/'candidate.json').write_text(json.dumps(value));return value


def test_manifest_refuses_changed_actual_bytes_before_runtime(tmp_path):
    media=tmp_path/'media';value=payload(media)
    assert manage.manifest(media)==value
    (media/'install.py').write_bytes(b'changed')
    with pytest.raises(manage.Refused,match='PAYLOAD_HASH_MISMATCH'):manage.manifest(media)


def test_git_source_mismatch_refuses_before_creating_venv_or_executing_backend(tmp_path):
    repository=tmp_path/'repository';repository.mkdir()
    def git(*args):return subprocess.run(['git',*args],cwd=repository,check=True,capture_output=True)
    git('init','-b','dev/local-product-runtime-20261028')
    (repository/'README').write_text('Owned harmless source fixture')
    git('add','README');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
    root=tmp_path/'installation';root.mkdir(mode=0o700);(root/'media').mkdir()
    git('bundle','create',str(root/'media/source.bundle'),'refs/heads/dev/local-product-runtime-20261028')
    with pytest.raises(manage.Refused,match='SOURCE_ID_MISMATCH'):
        manage.runtime(root,dict(branch='dev/local-product-runtime-20261028',source_commit='0'*40))
    assert (root/'application/source/README').exists() and not (root/'application/venv').exists()


def test_uninstall_preserves_modified_or_unrelated_application_files(tmp_path,monkeypatch):
    root=tmp_path/'owned';root.mkdir(mode=0o700);payload(root/'media');(root/'data').mkdir(mode=0o700)
    app=root/'application';app.mkdir(mode=0o700);file=app/'owned';file.write_text('software')
    manage.save(root,'application-inventory.json',manage.inventory(app))
    manage.save(root,'installation.json',dict(schema='parkweave-linux-user-installation/1',software='INSTALLED',setup='NOT_STARTED',source_commit='a'*40,state_dir=None))
    file.write_text('USER CONTRIBUTION MUST BE RETAINED')
    monkeypatch.setattr(manage,'__file__',str(root/'ParkWeave.py'))
    with pytest.raises(manage.Refused,match='APPLICATION_CHANGED_KEEP_ALL_FILES'):
        manage.execute(SimpleNamespace(command='uninstall'))
    assert file.read_text()=='USER CONTRIBUTION MUST BE RETAINED' and (root/'data').is_dir()
    assert manage.state(root)['software']=='INSTALLED'


def test_interrupted_setup_does_not_kill_child_or_erase_pending_state(tmp_path,monkeypatch):
    root=tmp_path/'owned';root.mkdir(mode=0o700);payload(root/'media');(root/'data').mkdir(mode=0o700)
    manage.save(root,'installation.json',dict(schema='parkweave-linux-user-installation/1',software='INSTALLED',setup='NOT_STARTED',source_commit='a'*40,state_dir=None))
    calls=[]
    class Child:
        def __init__(self,*args,**kwargs):calls.append('spawn')
        def communicate(self):raise KeyboardInterrupt()
        def wait(self,timeout):calls.append(('wait',timeout));raise subprocess.TimeoutExpired('owned-protocol-child',timeout)
    monkeypatch.setattr(manage.subprocess,'Popen',Child);monkeypatch.setattr(manage,'__file__',str(root/'ParkWeave.py'))
    with pytest.raises(manage.Refused,match='SETUP_CHILD_EXIT_UNKNOWN_NO_RETRY'):
        manage.execute(SimpleNamespace(command='setup'))
    assert manage.state(root)['setup']=='PENDING' and calls==['spawn',('wait',30)]
    with pytest.raises(manage.Refused,match='SETUP_ALREADY_ATTEMPTED_NO_RETRY'):
        manage.execute(SimpleNamespace(command='setup'))
    assert calls==['spawn',('wait',30)]


@pytest.mark.parametrize('output,created,code,expected',[(b'',False,1,'NOT_STARTED'),(b'\n',False,1,'PENDING'),(b'',True,1,'PENDING'),(b'',False,0,'PENDING')])
def test_only_confirmed_empty_precreate_refusal_allows_new_explicit_setup(tmp_path,monkeypatch,output,created,code,expected):
    root=tmp_path/'owned';root.mkdir(mode=0o700);payload(root/'media');(root/'data').mkdir(mode=0o700)
    manage.save(root,'installation.json',dict(schema='parkweave-linux-user-installation/1',software='INSTALLED',setup='NOT_STARTED',source_commit='a'*40,state_dir=None))
    class Child:
        returncode=code
        def __init__(self,*args,**kwargs):
            if created:(root/'data/pw-owned').mkdir()
        def communicate(self):return output,None
    monkeypatch.setattr(manage.subprocess,'Popen',Child);monkeypatch.setattr(manage,'__file__',str(root/'ParkWeave.py'))
    with pytest.raises(manage.Refused):manage.execute(SimpleNamespace(command='setup'))
    assert manage.state(root)['setup']==expected


@pytest.mark.parametrize('matching',[True,False])
def test_explicit_sample_setup_forwards_profile_and_never_accepts_material_receipt(tmp_path,monkeypatch,matching):
    root=tmp_path/'owned';root.mkdir(mode=0o700);payload(root/'media');(root/'data').mkdir(mode=0o700)
    manage.save(root,'installation.json',dict(schema='parkweave-linux-user-installation/1',software='INSTALLED',setup='NOT_STARTED',source_commit='a'*40,state_dir=None))
    calls=[]
    class Child:
        returncode=0
        def __init__(self,command,**kw):
            calls.append(command);(root/'data/pw-sample').mkdir(mode=0o700)
        def communicate(self):
            return json.dumps(dict(installed='LOCAL_SYNTHETIC_COLLABORATION_ONLY' if matching else 'LOCAL_SYNTHETIC_MATERIAL_ONLY',state_dir=str(root/'data/pw-sample'))).encode()+b'\n',None
    monkeypatch.setattr(manage.subprocess,'Popen',Child);monkeypatch.setattr(manage,'__file__',str(root/'ParkWeave.py'))
    if matching:manage.execute(SimpleNamespace(command='setup',sample_collaboration=True))
    else:
        with pytest.raises(manage.Refused,match='SETUP_NOT_CONFIRMED_KEEP_STATE'):
            manage.execute(SimpleNamespace(command='setup',sample_collaboration=True))
    assert calls[0][-1]=='--sample-collaboration'
    assert manage.state(root)['setup']==('COMPLETE' if matching else 'PENDING')
