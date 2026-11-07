import hashlib
import zipfile
from pathlib import Path
import pytest
from scripts.windows_portable.source_snapshot import load_snapshot
from scripts.windows_portable.build import assemble


def snapshot(tmp_path,files):
    path=tmp_path/'source.zip'
    with zipfile.ZipFile(path,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    return path,hashlib.sha256(path.read_bytes()).hexdigest()


def test_snapshot_carries_exact_uncommitted_bytes(tmp_path):
    path,digest=snapshot(tmp_path,{'src/parkweave/web.html':b'current local edits\r\n'})
    assert load_snapshot(path,digest)['src/parkweave/web.html']==b'current local edits\r\n'
    with pytest.raises(ValueError,match='SOURCE_SNAPSHOT_HASH'):load_snapshot(path,'0'*64)


@pytest.mark.parametrize('name',['../outside','scripts/../../outside','src/parkweave/file:stream','.env'])
def test_snapshot_refuses_escape_and_unrelated_inputs(tmp_path,name):
    path,digest=snapshot(tmp_path,{name:b'x'})
    with pytest.raises(ValueError,match='SOURCE_SNAPSHOT_PATH'):load_snapshot(path,digest)


def test_assembler_still_rejects_builder_drift_with_snapshot(tmp_path):
    path,digest=snapshot(tmp_path,{'scripts/windows_portable/build.py':b'different builder'})
    with pytest.raises(Exception,match='BUILDER_SOURCE_DRIFT'):
        assemble(Path.cwd(),digest,tmp_path,tmp_path/'absent-lock',source_snapshot=path)
