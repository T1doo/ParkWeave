"""Loader argv conversion; no authority, token, database or process creation."""
import pytest
from scripts.windows_portable.pgdata_candidate import DataRefused
from parkweave.store import Denied
from scripts.windows_portable.restricted_initdb_candidate import _command_image, ProcessRefused
from scripts.windows_portable.windows_process_handles import loader_image


RELATIVE = 'runtime/postgresql/bin/initdb.exe'


@pytest.mark.parametrize('root', ['C:/owned/instance', 'E:/园合 工作台/实例'])
def test_image_matches_same_pgdata_pinned_installation(root):
    image = '\\\\?\\' + (root + '/' + RELATIVE).replace('/', '\\')
    assert _command_image(root + '/data/postgresql', RELATIVE, image) == root + '/' + RELATIVE


@pytest.mark.parametrize('data,relative,image', [
    ('C:/owned/instance/data/postgresql', RELATIVE, '\\\\?\\C:\\other\\runtime\\postgresql\\bin\\initdb.exe'),
    ('C:/owned/instance/data/postgresql', 'runtime/postgresql/bin/postgres.exe', '\\\\?\\C:\\owned\\instance\\runtime\\postgresql\\bin\\postgres.exe'),
    ('C:/owned/instance/data/other', RELATIVE, '\\\\?\\C:\\owned\\instance\\runtime\\postgresql\\bin\\initdb.exe'),
    ('C:/owned/../instance/data/postgresql', RELATIVE, '\\\\?\\C:\\instance\\runtime\\postgresql\\bin\\initdb.exe'),
    ('C:/owned/instance/data/postgresql', RELATIVE, '\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\initdb.exe'),
    ('C:/owned/instance/data/postgresql', RELATIVE, '\\\\server\\share\\initdb.exe'),
    ('C:/owned/instance/data/postgresql', RELATIVE, 'C:\\owned\\instance\\runtime\\postgresql\\bin\\initdb.exe'),
    ('C:/owned/instance/data/postgresql', RELATIVE, '\\\\?\\C:\\owned\\instance\\runtime\\postgresql\\bin\\initdb.exe:stream'),
])
def test_path_mismatch_or_noncanonical_representation_is_refused(data, relative, image):
    with pytest.raises((ProcessRefused, DataRefused, Denied)):
        _command_image(data, relative, image)


@pytest.mark.parametrize('relative', ['runtime/postgresql/bin/postgres.exe', 'runtime/python/python.exe'])
def test_other_pinned_runtime_images_use_same_held_installation(relative):
    root='\\\\?\\E:\\园合 工作台\\实例'
    image=root+'\\'+relative.replace('/','\\')
    assert loader_image(root,relative,image)=='E:/园合 工作台/实例/'+relative


@pytest.mark.parametrize('relative,image', [
    ('../other.exe', '\\\\?\\C:\\owned\\other.exe'),
    ('runtime/python/python.exe', '\\\\?\\D:\\owned\\runtime\\python\\python.exe'),
    ('runtime/python/python.exe', '\\\\?\\C:\\other\\runtime\\python\\python.exe'),
    ('runtime/python/python.exe:stream', '\\\\?\\C:\\owned\\runtime\\python\\python.exe:stream'),
])
def test_loader_path_cannot_escape_or_change_pinned_installation(relative,image):
    with pytest.raises((ProcessRefused,DataRefused,Denied)):
        loader_image('\\\\?\\C:\\owned',relative,image)
