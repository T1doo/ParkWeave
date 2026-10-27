"""Unactivated read-only Windows candidate. Production files.py does not call it.
Policy/flow is independently testable; native syscall semantics are NOT_RUN on Linux.
No create, path reopen, ACL write, backup privilege or unsupported-platform fallback.
"""
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import os
import re
from uuid import UUID
from .store import Denied

LIMIT=16384
DIRECTORY=0x10
REPARSE=0x400
UNSAFE_ATTRIBUTES=0x40|0x1000|0x40000|0x400000  # DEVICE, OFFLINE, RECALL_ON_OPEN
PROTECTED=0x1000
DACL_PRESENT=0x4
TRUSTED_SYSTEM={'S-1-5-18','S-1-5-32-544'}

@dataclass(frozen=True)
class Ace:
    kind:int
    flags:int
    mask:int
    sid:str

@dataclass(frozen=True)
class Security:
    owner:str
    control:int
    aces:tuple[Ace,...] | None

@dataclass(frozen=True)
class Info:
    attributes:int
    size:int
    links:int
    volume:int
    identity:int


def component(name):
    if (not isinstance(name,str) or not name or len(name.encode('utf-16-le'))>510
        or name in ('.','..') or name[-1:] in (' ','.') or '~' in name
        or any(ord(c)<32 or c in '<>:"/\\|?*' for c in name)):
        raise Denied('invalid Windows component')
    stem=name.split('.')[0].upper()
    if stem in {'CON','PRN','AUX','NUL','CONIN$','CONOUT$'} or re.fullmatch(r'(COM|LPT)[1-9¹²³]',stem):
        raise Denied('reserved Windows component')
    return name


def root_parts(root):
    raw=os.fspath(root) if root is not None else ''
    if not isinstance(raw,str) or not re.match(r'^[A-Za-z]:\\',raw) or len(raw)>2048:
        raise Denied('local absolute Windows root required')
    parts=raw[3:].split('\\')
    if not parts or len(parts)>64:raise Denied('invalid Windows root')
    return raw[:3],tuple(component(p) for p in parts)


def logical_resource(resource):
    try:
        value=str(resource['id']);uid=UUID(value)
        # Canonical UUID only: no path, ADS, braced or silently normalized ID.
        if value!=str(uid):raise ValueError()
        size=resource['size'];sha=resource['sha256']
        if type(size) is not int or not 0<=size<=LIMIT or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError()
        return str(uid)+'.txt',size,sha
    except (ValueError,TypeError,KeyError):raise Denied('invalid logical resource') from None


def private_acl(security,user):
    if (security.owner!=user or security.control&(PROTECTED|DACL_PRESENT)!=(PROTECTED|DACL_PRESENT)
        or security.aces is None or not security.aces or len(security.aces)>128):
        raise Denied('unsafe Windows owner/DACL; permissions unchanged')
    allowed={user}|TRUSTED_SYSTEM
    for ace in security.aces:
        # Restrictive supported subset: simple allow/deny only; no inherited,
        # conditional/object/callback or unknown flags, even when apparently harmless.
        if ace.kind not in (0,1) or ace.flags&~0x0f or ace.mask<0 or not ace.sid:
            raise Denied('unsupported Windows ACE; permissions unchanged')
        if ace.kind==0 and ace.sid not in allowed:
            raise Denied('untrusted Windows allow ACE; permissions unchanged')


def metadata(info,directory,volume):
    if info.attributes&(REPARSE|UNSAFE_ATTRIBUTES) or bool(info.attributes&DIRECTORY)!=directory or info.volume!=volume:
        raise Denied('unsupported Windows file object')
    if not directory and (info.links!=1 or not 0<=info.size<=LIMIT):raise Denied('invalid Windows file metadata')


def _read_candidate(root,resource,api):
    """Test seam requires explicit API; it is never selected by production dispatch."""
    drive,parts=root_parts(root);name,size,sha=logical_resource(resource)
    with ExitStack() as stack:
        def hold(handle):stack.callback(api.close,handle);return handle
        parent=hold(api.open_drive(drive))
        guid=api.final_path(parent)
        if not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\',guid) or api.filesystem(parent)!='NTFS' or api.drive_type(guid)!=3:
            raise Denied('only fixed local NTFS volume roots supported')
        volume=api.info(parent).volume
        metadata(api.info(parent),True,volume)
        # Keep all ancestor handles until read completes. Never reopen by path.
        for part in parts:
            parent=hold(api.open_relative(parent,part,False))
            metadata(api.info(parent),True,volume)
        root_handle=parent;private_acl(api.security(root_handle),api.user_sid())
        directory=hold(api.open_relative(root_handle,'files',False))
        metadata(api.info(directory),True,volume);private_acl(api.security(directory),api.user_sid())
        item=hold(api.open_relative(directory,name,True))
        before=api.info(item);metadata(before,False,volume)
        private_acl(api.security(item),api.user_sid())
        if before.size!=size:raise Denied('resource size mismatch')
        data=api.read(item,LIMIT+1)
        after=api.info(item);metadata(after,False,volume)
        # Recheck private descriptors after reading; never claim administrator-proof.
        for handle in (root_handle,directory,item):private_acl(api.security(handle),api.user_sid())
        if after!=before or len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:
            raise Denied('resource integrity mismatch')
        try:data.decode('utf-8',errors='strict')
        except UnicodeError:raise Denied('invalid UTF8 resource') from None
        return data


def read_windows_candidate(root,resource):
    if os.name!='nt':raise Denied('Windows candidate requires native Windows; no fallback')
    try:
        from .windows_handles import WinAPI
        return _read_candidate(root,resource,WinAPI())
    except Denied:raise
    except Exception:raise Denied('Windows candidate unavailable; no fallback') from None
