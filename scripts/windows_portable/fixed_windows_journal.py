"""Held-file Windows slot IO candidate; original durability gate still refuses.

No root opened until WindowsFilesystem accepts its original prerequisites.
No rename, volume flush, ACL setter or automatic missing-name repair.
"""
import ctypes as C

from .directories import LeaseRefused
from .fixed_directories import FIXED_JOURNAL
from .fixed_journal import FixedJournal, SIZE
from .windows_directory_handles import WindowsFilesystem


class FixedWindowsFilesystem(WindowsFilesystem):
    def __init__(self, base, *, api=None):
        super().__init__(base, api=api); self.journal = None

    def acquire(self, name, *, fresh):
        # Includes original OWNER pause and require_directory_durability BEFORE
        # root open. This implementation does not grant native admission.
        super().acquire(name, fresh=fresh)
        self.journal = self.hold(self.api.relative_file(self.root, FIXED_JOURNAL,
                                   fresh=fresh, write=True, exclusive=True))
        self.journal_id = self.identity()
        self.journal_descriptor = self.api.descriptor(self.journal)
        self.verify(); self.storage = FixedJournal(self)

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
