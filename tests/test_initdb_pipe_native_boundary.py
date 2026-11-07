"""Original nontransmitting pipe boundary, current Windows user only.

No source grant, registered pipe capability, derived token, process, password,
client connection, write, database or service identity is created.
"""
import os
from uuid import uuid4
import secrets
import pytest
from scripts.windows_portable import initdb_pipe_candidate as pipe
from scripts.windows_portable.fixed_directories import FixedDirectoryLease
from scripts.windows_portable.fixed_windows_journal import NativeFixedLeaseAPI
from scripts.windows_portable.restricted_token_candidate import _RestrictedPrimaryCandidate
from scripts.windows_portable.native_protected_objects import sid_bytes


@pytest.mark.skipif(os.name!='nt',reason='actual nontransmitting Windows pipe APIs required')
def test_original_pipe_creation_security_readback_and_close_without_secret_or_grant():
    api=NativeFixedLeaseAPI();user=api.user_sid()
    # Constructor only validates types and loads APIs. These uninitialized
    # placeholders cannot pass the registered lease/owner creation entry.
    lease=object.__new__(FixedDirectoryLease)
    owner=object.__new__(_RestrictedPrimaryCandidate)
    server=pipe._OwnedInitdbPipe(lease,owner)
    server._name=pipe._pipe_name(str(uuid4()),secrets.token_hex(16))
    try:
        server._create_native(user)
        server._verify_native(sid_bytes(user))
        assert server._handle is not None and not server._ready
        assert lease not in pipe._by_lease and owner not in pipe._by_owner
    finally:
        server.close()
    assert server._closed and not server.cleanup_errors
