"""Real ordinary-directory collisions; all security/runner actions replaced by DI."""
import json,os,stat,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.host_case_once import prepare_once as p
from test_host_case_once_candidate import no_physical_actions,SHA,PARENT
from test_prepare_only_candidate import virtual_prepare
from test_host_case_bootstrap_diagnostics import virtual_bootstrap,VirtualPath,POISON


@pytest.mark.parametrize('kind',['directory','symlink','private_collision'])
def test_real_mkdir_collision_does_not_adopt_or_write_existing_object(tmp_path,monkeypatch,capsys,kind):
    root=tmp_path/'collision';old=tmp_path/'original'
    old.mkdir();(old/'private').mkdir();sentinel=old/'private/prepare-failure.log';sentinel.write_bytes(b'UNCHANGED_SYNTHETIC_ORIGINAL')
    if kind=='directory':
        root.mkdir();(root/'private').mkdir();(root/'private/prepare-failure.log').write_bytes(b'UNCHANGED_SYNTHETIC_ORIGINAL')
    elif kind=='symlink':root.symlink_to(old,target_is_directory=True)
    original_mkdir=Path.mkdir
    def mkdir(path,*a,**kw):
        original_mkdir(path,*a,**kw) # real mkdir must supply the actual EEXIST.
        if kind=='private_collision' and path==root:
            (root/'private').symlink_to(old/'private',target_is_directory=True)
    monkeypatch.setattr(Path,'mkdir',mkdir)
    class MappedPath:
        def __new__(cls,value):return root if str(value).startswith('/tmp/parkweave-prepare-') else Path(value)
        @staticmethod
        def cwd():return tmp_path
    monkeypatch.setattr(p,'Path',MappedPath)
    monkeypatch.setattr(p.b,'gate',lambda *a,**kw:PARENT)
    monkeypatch.setattr(sys,'flags',SimpleNamespace(isolated=1,no_site=1));monkeypatch.setattr(sys,'dont_write_bytecode',True)
    monkeypatch.setattr(p.signal,'signal',lambda *a:0);monkeypatch.setattr(p.signal,'alarm',lambda *a:0)
    def opened(path,*a,**kw):
        assert str(path)==p.CLAIM,'UNPROVEN_PATH_OPENED'
        return -123
    monkeypatch.setattr(p.os,'open',opened);monkeypatch.setattr(p.os,'write',lambda *a:1);monkeypatch.setattr(p.os,'close',lambda *a:None)
    # Ordinary tmp dirs belong to the test user; model root ownership only in DI.
    real_lstat=Path.lstat
    def lstat(path,*a,**kw):
        s=real_lstat(path,*a,**kw)
        return SimpleNamespace(st_mode=s.st_mode,st_uid=0,st_dev=s.st_dev,st_ino=s.st_ino)
    monkeypatch.setattr(Path,'lstat',lstat)
    def refuse(*a):raise AssertionError('UNPROVEN_DIRECTORY_ADOPTED')
    monkeypatch.setattr(p,'failure_log',refuse);monkeypatch.setattr(p.b,'prepare',refuse)
    assert p.run(SHA)==1
    capture=capsys.readouterr();assert not capture.err
    result=json.loads(capture.out)
    assert result['failure_logs']=='UNAVAILABLE' and not result['cleanup']
    assert result['diagnostics'][0]['check_id']==('B_PRIVATE_DIR' if kind=='private_collision' else 'B_ROOT')
    assert sentinel.read_bytes()==b'UNCHANGED_SYNTHETIC_ORIGINAL'
    if kind=='directory':assert (root/'private/prepare-failure.log').read_bytes()==b'UNCHANGED_SYNTHETIC_ORIGINAL'
    if kind=='symlink':assert root.is_symlink() and os.readlink(root)==str(old)


@pytest.mark.parametrize('changed',['root_inode','root_owner','root_mode','private_inode','private_owner','private_mode'])
def test_private_log_rechecks_opened_directory_instances_before_file_creation(monkeypatch,virtual_prepare,changed):
    root=VirtualPath('/SYNTHETIC_ROOT');root.mkdir(mode=0o711);(root/'private').mkdir(mode=0o700)
    original=p.os.fstat
    def fstat(fd):
        s=original(fd);is_private=str(VirtualPath.fdpaths[fd]).endswith('/private')
        if changed.startswith('private')==is_private:
            if changed.endswith('inode'):s.st_ino+=1
            if changed.endswith('owner'):s.st_uid=1000
            if changed.endswith('mode'):s.st_mode|=0o022
        return s
    monkeypatch.setattr(p.os,'fstat',fstat)
    with pytest.raises(PermissionError):p.failure_log(root,(1,2),(1,2),POISON.encode())
    assert '/SYNTHETIC_ROOT/private/prepare-failure.log' not in VirtualPath.nodes


def test_private_log_uses_relative_nofollow_exclusive_creation_and_owned_fds(monkeypatch,virtual_prepare):
    root=VirtualPath('/SYNTHETIC_ROOT');root.mkdir(mode=0o711);(root/'private').mkdir(mode=0o700)
    opened=[];closed=[];original=p.os.open
    def open_file(path,flags,*args,**kwargs):
        fd=original(path,flags,*args,**kwargs);opened.append((str(path),flags,args,kwargs,fd));return fd
    monkeypatch.setattr(p.os,'open',open_file);monkeypatch.setattr(p.os,'close',closed.append)
    p.failure_log(root,(1,2),(1,2),POISON.encode())
    assert len(opened)==3 and closed==[row[4] for row in reversed(opened)]
    assert all(row[1]&os.O_NOFOLLOW for row in opened)
    assert opened[1][3]['dir_fd']==opened[0][4] and opened[2][3]['dir_fd']==opened[1][4]
    assert opened[2][1]&os.O_EXCL and opened[2][2]==(0o600,)


@pytest.mark.parametrize('fail_at',[0,1])
def test_log_close_failure_still_attempts_every_remaining_owned_fd(monkeypatch,virtual_prepare,fail_at):
    root=VirtualPath('/SYNTHETIC_ROOT');root.mkdir(mode=0o711);(root/'private').mkdir(mode=0o700)
    opened=[];closed=[];original=p.os.open
    def open_file(*a,**kw):
        fd=original(*a,**kw);opened.append(fd);return fd
    def close(fd):
        index=len(closed);closed.append(fd)
        if index==fail_at:raise OSError(POISON)
    monkeypatch.setattr(p.os,'open',open_file);monkeypatch.setattr(p.os,'close',close)
    with pytest.raises(OSError):p.failure_log(root,(1,2),(1,2),POISON.encode())
    assert closed==list(reversed(opened))
