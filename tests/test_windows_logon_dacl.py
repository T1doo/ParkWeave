import struct
import pytest
from scripts.windows_portable.restricted_token_candidate import _without_logon_grants,TokenRefused

def sid(*parts):return bytes([1,len(parts)])+b'\0'*5+b'\5'+struct.pack('<'+'I'*len(parts),*parts)
def ace(principal,kind=0):return struct.pack('<BBHI',kind,0,8+len(principal),0x10000000)+principal
def acl(*rows):return struct.pack('<BBHHH',2,0,8+sum(map(len,rows)),len(rows),0)+b''.join(rows)

def test_only_observed_logon_allow_removed_and_denies_preserved():
    user,logon=sid(21,1,2,3,1001),sid(5,7,8)
    source=acl(ace(logon,1),ace(user),ace(logon),ace(sid(18)))
    assert _without_logon_grants(source,{1:user,2:{logon:0xc0000004}})==acl(ace(logon,1),ace(user),ace(sid(18)))

def test_unobserved_or_ordinary_group_grant_remains_refused():
    user,other=sid(21,1,2,3,1001),sid(5,7,8)
    for groups in ({},{other:4}):
        with pytest.raises(TokenRefused):_without_logon_grants(acl(ace(user),ace(other)),{1:user,2:groups})
