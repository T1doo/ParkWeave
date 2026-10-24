"""Held-file Windows slot IO with independent, still closed native preflight.

No instance root opened until fixed-file prerequisites and acceptance pass.
No rename, volume flush, ACL setter or automatic missing-name repair.
"""
import ctypes as C

from .directories import LeaseRefused
from .fixed_directories import FIXED_JOURNAL
from .fixed_journal import FixedJournal, FixedFormat, require_format, SIZE
from .windows_directory_handles import WindowsFilesystem, NativeLeaseAPI


class FixedWindowsFilesystem(WindowsFilesystem):
    def __init__(self, base, *, api=None, format=FixedFormat.V1):
        self._journal_format = require_format(format)
        super().__init__(base, api=api); self.journal = None

    @property
    def journal_format(self): return self._journal_format

    def acquire(self, name, *, fresh):
        if fresh:
            from scripts.windows.lifecycle import require_setup_readiness
            require_setup_readiness()
        if self.api is None: self.api = NativeFixedLeaseAPI()
        self.api.require_fixed_file_prerequisites(self.base)
        require_fixed_native_acceptance()  # Independent closed gate, not a flag.
        self._acquire_handles(name, fresh=fresh)
        self.journal = self.hold(self.api.relative_file(self.root, FIXED_JOURNAL,
                                   fresh=fresh, write=True, exclusive=True))
        self.journal_id = self.identity()
        self.journal_descriptor = self.api.descriptor(self.journal)
        self.verify(); self.storage = FixedJournal(self, format=self.journal_format)

    def identity(self, handle=None):
        return super().identity(self.journal if handle is None else handle)

    def verify(self):
        super().verify()
        if self.journal is None: return
        if (self._object(self.journal, directory=False, private=True) != self.journal_id
                or self.api.info(self.journal).size > SIZE
                or self.api.descriptor(self.journal) != self.journal_descriptor
                or self.api.final_path(self.journal) != self.api.final_path(self.root).rstrip('\\') + '\\' + FIXED_JOURNAL):
            raise LeaseRefused('FIXED_NATIVE_FILE_BINDING')

    def signature(self):
        from parkweave.windows_handles import FileInfo
        info = FileInfo(); self.api.need(self.api.getinfo(self.journal, C.byref(info)))
        # Access time may change from our own read; write/identity fields may not.
        return (info.Attributes, info.Creation.Low, info.Creation.High, info.Write.Low, info.Write.High,
                info.Volume, info.SizeHigh, info.SizeLow, info.Links, info.IndexHigh, info.IndexLow)

    def length(self): return self.api.info(self.journal).size

    def _seek(self, offset):
        seek = self.api.readonly.k.SetFilePointerEx
        seek.argtypes, seek.restype = [C.c_void_p, C.c_int64, C.c_void_p, C.c_uint32], C.c_int32
        self.api.need(seek(self.journal, offset, None, 0))

    def read_at(self, offset, count):
        self._seek(offset)
        return self.api.read(self.journal, count)  # One full-slot read, no fallback.

    def write_at(self, offset, raw):
        self._seek(offset)
        buffer, count = C.create_string_buffer(raw), C.c_uint32()
        self.api.need(self.api.writefile(self.journal, buffer, len(raw), C.byref(count), None))
        if count.value > len(raw): raise LeaseRefused('FIXED_NATIVE_WRITE_COUNT')
        return count.value

    def flush_file(self): self.api.flush(self.journal)
    def read(self): return self.storage.read()
    def replace(self, raw, expected): return self.storage.write(raw, expected)


def require_fixed_native_acceptance():
    # No environment/boolean/mock result can issue acceptance. A future source
    # change requires independent actual Windows validation and review. This is
    # separate from legacy rename durability and from OWNER permission.
    raise LeaseRefused('WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED')


class NativeFixedLeaseAPI(NativeLeaseAPI):
    def require_fixed_file_prerequisites(self, base):
        import os
        import re
        from parkweave.windows_files import root_parts, metadata
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise LeaseRefused('NATIVE_WINDOWS_X64_REQUIRED')
        drive, _ = root_parts(base)
        # Resolve the exact existing local drive through a read-only held
        # handle. No instance root, file, ACL or credential creation here.
        handle, primary = self.open_drive(drive), None
        try:
            guid = self.final_path(handle)
            if (not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\', guid)
                    or self.filesystem(handle) != 'NTFS' or self.drive_type(guid) != 3):
                raise LeaseRefused('FIXED_LOCAL_NTFS_REQUIRED')
            info = self.info(handle); metadata(info, True, info.volume)
            self.descriptor(handle)  # Original owner/control/raw DACL readability.
            self.user_sid()  # Existing token only, no impersonation/privileges.
            seek = self.readonly.k.SetFilePointerEx
            seek.argtypes, seek.restype = [C.c_void_p,C.c_int64,C.c_void_p,C.c_uint32],C.c_int32
            # These are original bounded synchronous file-handle APIs. Their
            # presence is necessary, not native durability acceptance.
            if not all(callable(getattr(self, name)) for name in ('read','writefile','flushfile','relative_file')):
                raise LeaseRefused('FIXED_FILE_APIS_REQUIRED')
        except BaseException as error:
            primary = error
            raise
        finally:
            try: self.close(handle)
            except BaseException as cleanup:
                if primary is not None: raise BaseExceptionGroup('FIXED_PREFLIGHT_AND_CLOSE_UNKNOWN',[primary,cleanup]) from primary
                raise
