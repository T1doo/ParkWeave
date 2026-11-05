"""Loader argv conversion; no authority, token, database or process creation."""
import pytest
from scripts.windows_portable.pgdata_candidate import DataRefused
from parkweave.store import Denied
from scripts.windows_portable.restricted_initdb_candidate import _command_image, ProcessRefused


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
