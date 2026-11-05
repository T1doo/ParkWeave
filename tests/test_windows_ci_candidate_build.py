import zipfile
import pytest
from scripts.windows_ci import native_candidate_build as build
from scripts.windows_ci.native_business_window import WindowRefused


def test_compiler_platform_is_explicit_and_closed():
    assert build.compiler_layout('nt')==('zig-x86_64-windows-0.15.2.zip','zig-x86_64-windows-0.15.2/zig.exe')
    assert build.compiler_layout('posix')==('zig-x86_64-linux-0.15.2.tar.xz','zig-x86_64-linux-0.15.2/zig')
    with pytest.raises(WindowRefused):build.compiler_layout('unknown')


@pytest.mark.parametrize('name',['../outside','zig-x86_64-windows-0.15.2/../outside','zig-x86_64-windows-0.15.2/name:stream'])
def test_windows_compiler_archive_refuses_path_escape_before_extraction(tmp_path,name):
    archive=tmp_path/'compiler.zip';destination=tmp_path/'out'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'not executable')
    with pytest.raises(WindowRefused):build.extract_compiler(archive,destination)
    assert not destination.exists()
