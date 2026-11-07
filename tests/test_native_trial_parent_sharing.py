"""Real Windows sharing on an owned empty directory, no product/DB/DPAPI run."""
import ctypes as C
import os
import pytest
from scripts.windows_ci.native_acceptance_storage import ROOT_ACCESS,FILE_ACCESS


@pytest.mark.skipif(os.name!='nt',reason='actual Windows handle sharing required')
def test_readonly_retained_marker_allows_pgdata_anchor_but_still_denies_delete(tmp_path):
    kernel=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
    create=kernel.CreateFileW
    create.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p]
    create.restype=C.c_void_p
    close=kernel.CloseHandle;close.argtypes=[C.c_void_p];close.restype=C.c_int32
    invalid=C.c_void_p(-1).value
    handles=[]
    path=tmp_path/'owned-empty-marker';path.mkdir()
    def opened(access,share):
        handle=create(str(path),access,share,None,3,0x02000000|0x00200000,None)
        error=C.get_last_error()
        if handle not in (None,invalid):handles.append(handle)
        return handle,error
    def closed(handle):
        assert close(handle);handles.remove(handle)
    try:
        # Reproduce run 19's share conflict with the old marker access mask.
        old,error=opened(FILE_ACCESS,1);assert old not in (None,invalid),error
        blocked,error=opened(0x120081,3)
        assert blocked==invalid and error==32
        closed(old)
        # Exact new marker rights admit the original PGDATA read/list anchor.
        marker,error=opened(ROOT_ACCESS,1);assert marker not in (None,invalid),error
        anchor,error=opened(0x120081,3);assert anchor not in (None,invalid),error
        # A different open still cannot acquire DELETE or write-data access.
        for access in (0x10000,0x2):
            blocked,error=opened(access,7)
            assert blocked==invalid and error==32
        closed(anchor);closed(marker)
        assert list(path.iterdir())==[]
    finally:
        for handle in reversed(handles):assert close(handle)
