"""Compiler inventory guards. Small synthetic archives, not official tool execution."""
import hashlib
import zipfile
import pytest
from scripts.windows_desktop import build


def fixture_archive(tmp_path,monkeypatch):
    archive=tmp_path/'compiler.zip';root=tmp_path/'compiler';root.mkdir()
    with zipfile.ZipFile(archive,'w') as z:z.writestr('fixture/zig.exe',b'compiler')
    (root/'zig.exe').write_bytes(b'compiler')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(build,'COMPILERS',{digest:('fixture','zip')})
    return archive,root


def test_zip_distribution_rejects_changed_binary_and_extra_file(tmp_path,monkeypatch):
    archive,root=fixture_archive(tmp_path,monkeypatch)
    assert build.verify_compiler(archive,root)[1]=={'zig.exe'}
    (root/'zig.exe').write_bytes(b'changed')
    with pytest.raises(ValueError,match='COMPILER_TREE_DRIFT'):build.verify_compiler(archive,root)
    (root/'zig.exe').write_bytes(b'compiler');(root/'extra.dll').write_bytes(b'extra')
    with pytest.raises(ValueError,match='COMPILER_TREE_EXTRA_OR_MISSING'):build.verify_compiler(archive,root)


def test_distribution_pin_cannot_be_replaced_by_adjacent_hash(tmp_path):
    archive=tmp_path/'unknown.zip';archive.write_bytes(b'not official')
    with pytest.raises(ValueError,match='OFFICIAL_COMPILER_DISTRIBUTION_REQUIRED'):build.verify_compiler(archive,tmp_path)


def test_zip_distribution_refuses_parent_escape(tmp_path,monkeypatch):
    archive=tmp_path/'escape.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('fixture/../escape.exe',b'bad')
    monkeypatch.setattr(build,'COMPILERS',{hashlib.sha256(archive.read_bytes()).hexdigest():('fixture','zip')})
    with pytest.raises(ValueError,match='COMPILER_ARCHIVE_LAYOUT'):build.verify_compiler(archive,tmp_path)
