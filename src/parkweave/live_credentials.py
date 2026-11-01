"""Read pre-existing operator credentials; never provision or persist a secret.

Windows uses only the current logon session's fixed generic Credential Manager
target. POSIX accepts only an explicitly inherited, private anonymous pipe.
Neither path falls back to argv, environment token values or plaintext files.
"""
from dataclasses import dataclass, field
import os
import re
import select
import stat
import sys
import time
from uuid import UUID

from pydantic import SecretStr
from .intern_adapter import ModelBoundaryError, strict_json

TARGET = 'ParkWeave/F1/InternModel'
MAX_BYTES = 2560  # Windows CRED_MAX_CREDENTIAL_BLOB_SIZE; one UTF-8 document.
_retained = []  # Unknown original native call/free output is not retried.


@dataclass(frozen=True)
class LiveCredentials:
    token: SecretStr = field(repr=False)
    quota_dsn: SecretStr = field(repr=False)
    account: str
    coordinator_id: UUID


def parse_credentials(raw):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:raise ValueError()
        data = strict_json(raw)
        if type(data) is not dict or set(data) != {'schema','token','quota_dsn','account','coordinator_id'}:
            raise ValueError()
        if data['schema'] != 'parkweave-live-worker/1':raise ValueError()
        for name in ('token','quota_dsn'):
            value=data[name]
            if type(value) is not str or not value.strip() or any(ord(c)<32 for c in value):raise ValueError()
        if type(data['account']) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',data['account']):raise ValueError()
        identity=UUID(data['coordinator_id'])
        if str(identity)!=data['coordinator_id']:raise ValueError()
        # The coordinator is always supplied explicitly, never store.dsn.
        from psycopg.conninfo import conninfo_to_dict
        config=conninfo_to_dict(data['quota_dsn'])
        if not all(config.get(k) for k in ('host','dbname','user')) or config.get('service') or config.get('passfile'):
            raise ValueError()
        if not config['host'].startswith('/') and (config.get('sslmode')!='verify-full' or not config.get('password')):
            raise ValueError()
        from psycopg.conninfo import make_conninfo
        # Disable implicit plaintext pgpass lookup. Normal live startup also
        # refuses ambient PG* names instead of changing process environment.
        explicit=make_conninfo(data['quota_dsn'],passfile=os.devnull,connect_timeout=2,
            options='-c statement_timeout=3000 -c lock_timeout=1000')
        return LiveCredentials(SecretStr(data['token']),SecretStr(explicit),data['account'],identity)
    except Exception:
        raise ModelBoundaryError('LIVE_CREDENTIAL_FORMAT_REFUSED') from None


class InheritedPipeCredentials:
    def __init__(self,fd):self.fd=fd

    def read(self):
        if not sys.platform.startswith('linux') or type(self.fd) is not int or self.fd<3:
            raise ModelBoundaryError('LIVE_CREDENTIAL_SOURCE_REFUSED')
        owned=None
        try:
            owned=os.dup(self.fd);os.set_inheritable(owned,False)
            before=os.fstat(owned)
            if not (stat.S_ISFIFO(before.st_mode) and before.st_nlink==1
                    and before.st_uid==os.geteuid() and stat.S_IMODE(before.st_mode)&0o077==0
                    and re.fullmatch(r'pipe:\[[0-9]+\]',os.readlink('/proc/self/fd/'+str(owned)))):
                raise ValueError()
            os.set_inheritable(self.fd,False);os.set_blocking(owned,False)
            deadline=time.monotonic()+2;parts=[];size=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not select.select([owned],[],[],remaining)[0]:raise ValueError()
                try:block=os.read(owned,min(1024,MAX_BYTES+1-size))
                except BlockingIOError:continue
                if not block:break
                parts.append(block);size+=len(block)
                if size>MAX_BYTES:raise ValueError()
            after=os.fstat(owned)
            if (before.st_dev,before.st_ino,before.st_uid,before.st_mode)!=(after.st_dev,after.st_ino,after.st_uid,after.st_mode):
                raise ValueError()
            return parse_credentials(b''.join(parts))
        except ModelBoundaryError:raise
        except Exception:raise ModelBoundaryError('LIVE_CREDENTIAL_SOURCE_REFUSED') from None
        finally:
            if owned is not None:os.close(owned)


def _credential_type():
    """Windows fixed-width CREDENTIALW layout; no DLL load or native call."""
    import ctypes as c
    class FileTime(c.Structure):_fields_=[('low',c.c_uint32),('high',c.c_uint32)]
    class Credential(c.Structure):
        _fields_=[('Flags',c.c_uint32),('Type',c.c_uint32),('TargetName',c.c_wchar_p),('Comment',c.c_wchar_p),
            ('LastWritten',FileTime),('CredentialBlobSize',c.c_uint32),('CredentialBlob',c.POINTER(c.c_ubyte)),
            ('Persist',c.c_uint32),('AttributeCount',c.c_uint32),('Attributes',c.c_void_p),
            ('TargetAlias',c.c_wchar_p),('UserName',c.c_wchar_p)]
    return Credential


def _read_credential(api):
    """Same production FFI ownership path, separable for non-native protocols."""
    import ctypes as c
    Credential=_credential_type()
    api.CredReadW.argtypes=[c.c_wchar_p,c.c_uint32,c.c_uint32,c.POINTER(c.POINTER(Credential))]
    api.CredReadW.restype=c.c_int32
    api.CredFree.argtypes=[c.c_void_p];api.CredFree.restype=None
    pointer=c.POINTER(Credential)();target=c.create_unicode_buffer(TARGET);argument=c.byref(pointer)
    graph=dict(api=api,pointer=pointer,target=target,argument=argument,
        read_returned=False,read_succeeded=False,free_attempted=False,free_returned=False)
    _retained.append(graph)  # Before the original call or any output inspection.
    def forget():
        for index,item in enumerate(_retained):
            if item is graph:del _retained[index];break
    try:
        graph['read_succeeded']=bool(api.CredReadW(target,1,0,argument));graph['read_returned']=True
        if not graph['read_succeeded']:raise ValueError()
        if not pointer:raise ValueError()
        value=pointer.contents
        if value.Type!=1 or value.TargetName!=TARGET or not value.CredentialBlob or not 0<value.CredentialBlobSize<=MAX_BYTES:
            raise ValueError()
        return c.string_at(value.CredentialBlob,value.CredentialBlobSize)
    except Exception:raise ModelBoundaryError('LIVE_CREDENTIAL_UNAVAILABLE') from None
    finally:
        if graph['read_returned'] and graph['read_succeeded'] and pointer:
            # Only the API-returned memory is cleared; no CredWrite/Delete or
            # system credential/profile change is performed.
            try:
                value=pointer.contents
                if value.CredentialBlob and 0<value.CredentialBlobSize<=MAX_BYTES:
                    c.memset(value.CredentialBlob,0,value.CredentialBlobSize)
                graph['free_attempted']=True
                api.CredFree(pointer);graph['free_returned']=True
                forget()
            except BaseException:
                raise ModelBoundaryError('LIVE_CREDENTIAL_RELEASE_UNKNOWN') from None
        elif graph['read_returned'] and not graph['read_succeeded'] and not pointer:
            forget()  # Known failed call, no allocation. Other outputs remain held.


def _windows_blob():
    if os.name!='nt':raise ModelBoundaryError('LIVE_CREDENTIAL_SOURCE_REFUSED')
    import ctypes as c
    return _read_credential(c.WinDLL('advapi32.dll',use_last_error=True,winmode=0x800))


class WindowsCredentialCredentials:
    def read(self):
        try:return parse_credentials(_windows_blob())
        except ModelBoundaryError:raise
        except Exception:raise ModelBoundaryError('LIVE_CREDENTIAL_UNAVAILABLE') from None


def read_live_credentials(config_fd=None):
    if config_fd is not None:return InheritedPipeCredentials(config_fd).read()
    return WindowsCredentialCredentials().read()
