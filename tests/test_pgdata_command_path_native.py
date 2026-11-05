"""Original read-only PGDATA path pin on owned empty dirs, no capability issued.

Does not call the PGDATA constructor/create/scan, grant machinery, initdb,
credentials or service identities. A metadata-only stand-in supplies volume ID.
"""
import ctypes as C
import os
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.windows_portable import pgdata_candidate as pg
from scripts.windows_portable.fixed_windows_journal import NativeFixedLeaseAPI
from scripts.windows_ci.native_acceptance_storage import ROOT_ACCESS,FILE_ACCESS


@pytest.mark.skipif(os.name!='nt',reason='original Windows path-pin APIs required')
def test_original_path_pin_reproduces_old_parent_conflict_and_accepts_readonly_marker(tmp_path):
    api=NativeFixedLeaseAPI()
    marker=tmp_path/'owned-marker';root=marker/'trial-instance'/'data'/'postgresql'
    root.mkdir(parents=True)
    create=api.readonly.create
    invalid=C.c_void_p(-1).value
    def opened(path,access,share):
        h=create(str(path),access,share,None,3,0x02000000|0x00200000,None)
        assert h not in (None,invalid),C.get_last_error()
        return h
    def pin(access,expect_conflict):
        parent=opened(marker,access,1)
        target=object.__new__(pg._NewDataTarget)
        target.api=api;target.deadline=time.monotonic()+20
        target.handles=[];target.last_native=None
        try:
            target.root=opened(root,0x120081,3);target.handles.append(target.root)
            info=api.info(target.root)
            target.lease=SimpleNamespace(fs=SimpleNamespace(root_id=(info.volume,info.identity)))
            identity=target._identity(target.root,directory=True)
            guid_path=api.final_path(target.root)
            if expect_conflict:
                with pytest.raises(pg.DataRefused):target._pin_command_path(identity,guid_path)
                assert target.last_native['code']==0xc0000043
                assert target.last_native['handle_output']=='EMPTY'
            else:
                path,chain=target._pin_command_path(identity,guid_path)
                assert Path(path)==root and chain[-1][1]==identity
                assert api.final_path(chain[-1][0])==guid_path
                # Requery every held identity/descriptor exactly as _verify does.
                for handle,expected,descriptor in chain:
                    assert target._identity(handle,directory=True)==expected
                    assert api.descriptor(handle)==descriptor
        finally:
            for handle in reversed(target.handles):api.close(handle)
            api.close(parent)
    pin(FILE_ACCESS,True)
    pin(ROOT_ACCESS,False)
    assert list(root.iterdir())==[]
