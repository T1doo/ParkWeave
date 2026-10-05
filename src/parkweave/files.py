"""Logical IDs only. Linux descriptor confinement; unsupported platforms fail closed."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
from uuid import UUID
from .store import Denied


@contextmanager
def resource_directory(root,create=False):
    if root is None or not hasattr(os,'O_NOFOLLOW') or os.open not in os.supports_dir_fd:
        raise Denied('file backend unavailable on this platform')
    # Validate raw input before Path normalizes traversal components.
    raw=os.fspath(root)
    path=Path(raw)
    if not path.is_absolute() or any(part in ('.','..') for part in raw.split('/')):
        raise Denied('absolute private root required')
    fd=None
    try:
        fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for part in path.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        if create:
            try:os.mkdir('files',0o700,dir_fd=fd)
            except FileExistsError:pass
        child=os.open('files',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        os.close(fd);fd=child
        yield fd
    except OSError as exc:raise Denied('resource unavailable') from exc
    finally:
        if fd is not None:os.close(fd)


def read_text_resource(root,resource):
    # UUID normalization excludes separators, drives, UNC, ADS and traversal.
    name=str(UUID(str(resource['id'])))+'.txt'
    try:
        with resource_directory(root) as directory:
            item=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
            try:
                info=os.fstat(item)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>16384:
                    raise Denied('invalid resource')
                with os.fdopen(item,'rb',closefd=False) as f:data=f.read(16385)
            finally:os.close(item)
        if len(data)!=resource['size'] or hashlib.sha256(data).hexdigest()!=resource['sha256']:
            raise Denied('resource integrity mismatch')
        data.decode('utf-8',errors='strict')
        return data
    except (OSError,UnicodeError,ValueError) as exc:raise Denied('resource unavailable') from exc
