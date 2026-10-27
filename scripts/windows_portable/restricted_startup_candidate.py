"""Unwired STARTUPINFOEX/UTF-16 marshaller, not restricted-process authority.

No import-time DLL; no CreateProcess, Token, DACL, Job, environment mutation or
credential IO. Calling prepare WOULD duplicate real handles and initialize a
native attribute list, requiring separate authorization. Borrowed stdio must
remain stable under the caller's ownership until prepare returns. Inputs are
data, not proof of executable pin, stdio permissions or a restricted token.
"""
import ctypes as C
import ntpath
import os
import subprocess

from parkweave.process_env import OS_ENV_NAMES


class StartupRefused(RuntimeError):
    pass


class StartupFailure(StartupRefused):
    def __init__(self, phase, primary_type, cleanup, winerror):
        self.phase, self.primary_type = phase, primary_type
        self.cleanup, self.winerror = tuple(cleanup), winerror
        self.outcome = 'UNKNOWN'
        super().__init__('RESTRICTED_STARTUP_UNKNOWN:'+phase)


class StartupInfo(C.Structure):
    _fields_ = [('cb', C.c_uint32), ('lpReserved', C.c_void_p),
                ('lpDesktop', C.c_void_p), ('lpTitle', C.c_void_p)]
    _fields_ += [(name, C.c_uint32) for name in
                 ('dwX', 'dwY', 'dwXSize', 'dwYSize', 'dwXCountChars',
                  'dwYCountChars', 'dwFillAttribute', 'dwFlags')]
    _fields_ += [('wShowWindow', C.c_uint16), ('cbReserved2', C.c_uint16),
                ('lpReserved2', C.c_void_p), ('hStdInput', C.c_void_p),
                ('hStdOutput', C.c_void_p), ('hStdError', C.c_void_p)]


class StartupInfoEx(C.Structure):
    _fields_ = [('StartupInfo', StartupInfo), ('lpAttributeList', C.c_void_p)]


def _need(ok):
    if not ok:
        raise StartupRefused('RESTRICTED_STARTUP_REFUSED')


def _utf16(text):
    try:
        raw = text.encode('utf-16-le', errors='strict')
    except UnicodeError:
        raise StartupRefused('RESTRICTED_STARTUP_UTF16_REFUSED') from None
    _need(len(raw) // 2 <= 32767)
    return (C.c_uint16 * (len(raw) // 2)).from_buffer_copy(raw)


def command_buffer(executable, arguments):
    _need(type(executable) is str and ntpath.isabs(executable)
          and 0 < len(executable) <= 4096 and '"' not in executable)
    _need(type(arguments) is tuple and len(arguments) <= 32)
    _need(all(type(x) is str and len(x) <= 2048 for x in arguments))
    _need(sum(map(len, arguments)) <= 8192)
    _need(all(not any(ord(c) < 32 for c in x) for x in (executable, *arguments)))
    # Serialization only: upstream must still admit the exact fixed Command.
    return _utf16(subprocess.list2cmdline([executable, *arguments]) + '\0')


def environment_buffer(environment):
    _need(type(environment) is dict and len(environment) <= len(OS_ENV_NAMES))
    allowed, seen, rows = {x.lower() for x in OS_ENV_NAMES}, set(), []
    for key, value in environment.items():
        _need(type(key) is str and key.lower() in allowed and key.lower() not in seen)
        _need(type(value) is str and len(value) <= 8192
              and not any(ord(c) < 32 for c in value))
        seen.add(key.lower())
        rows.append((key, value))
    rows.sort(key=lambda row: row[0].lower())
    return _utf16('\0'.join(key + '=' + value for key, value in rows) + '\0\0')


def _handle(value):
    # Exclude signed and unsigned pseudo-handle encodings, including token
    # pseudo handles. DuplicateHandle can materialize pseudo process handles.
    return type(value) is int and 0 < value < (1 << (8 * C.sizeof(C.c_void_p))) - 16


def native_restricted_startup():
    raise StartupRefused('NATIVE_RESTRICTED_STARTUP_NOT_ACCEPTED')


class _OwnedStartup:
    native_acceptance = False
    launch_ready = False

    def __init__(self):
        _need(os.name == 'nt' and C.sizeof(C.c_void_p) == 8)
        self._kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        pointer, size, dword, boolean = C.c_void_p, C.c_size_t, C.c_uint32, C.c_int32
        signatures = {
            'GetCurrentProcess': ([], pointer),
            'DuplicateHandle': ([pointer, pointer, pointer, C.POINTER(pointer), dword, boolean, dword], boolean),
            'CloseHandle': ([pointer], boolean),
            'GetFileType': ([pointer], dword),
            'InitializeProcThreadAttributeList': ([pointer, dword, dword, C.POINTER(size)], boolean),
            'UpdateProcThreadAttribute': ([pointer, dword, size, pointer, size, pointer, C.POINTER(size)], boolean),
            'DeleteProcThreadAttributeList': ([pointer], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self._kernel, name)
            function.argtypes, function.restype = arguments, result
        self.info = StartupInfoEx()
        self._duplicates = []
        self._attributes = self._handle_array = None
        self._initialized = self._started = self._closed = self.failed = False
        self.prepared = False
        self.phase, self.winerror, self.cleanup_errors = 'NEW', None, []

    def _api(self, ok):
        if not ok:
            self.winerror = C.get_last_error()
            _need(False)

    def prepare(self, stdio):
        _need(not self._started and not self._closed and not self.failed)
        _need(type(stdio) is tuple and len(stdio) == 3 and all(_handle(x) for x in stdio))
        self._started = True
        try:
            process = self._kernel.GetCurrentProcess()
            for borrowed in stdio:
                self.phase = 'DUPLICATE_STDIO'
                duplicate = C.c_void_p()
                ok = self._kernel.DuplicateHandle(process, borrowed, process,
                                                  C.byref(duplicate), 0, True, 2)
                if not ok:
                    self.winerror = C.get_last_error()
                if ok and _handle(duplicate.value) and duplicate.value not in self._duplicates:
                    self._duplicates.append(duplicate.value)
                else:
                    _need(False)
                self.phase = 'STDIO_TYPE'
                # UNKNOWN is a refusal, not necessarily a Win32 API failure.
                _need(self._kernel.GetFileType(duplicate) in (1, 2, 3))
            self.phase = 'ATTRIBUTE_SIZE'
            required = C.c_size_t()
            ok = self._kernel.InitializeProcThreadAttributeList(None, 1, 0, C.byref(required))
            error = C.get_last_error() if not ok else None
            self.winerror = error if error != 122 else None
            _need(not ok and error == 122 and 0 < required.value <= 65536)
            self._attributes = C.create_string_buffer(required.value)
            _need(C.addressof(self._attributes) % C.alignment(C.c_void_p) == 0)
            self.phase = 'ATTRIBUTE_INITIALIZE'
            self._api(self._kernel.InitializeProcThreadAttributeList(
                self._attributes, 1, 0, C.byref(required)))
            self._initialized = True  # before any later validation/update
            _need(0 < required.value <= C.sizeof(self._attributes))
            self._handle_array = (C.c_void_p * 3)(*self._duplicates)
            self.phase = 'ATTRIBUTE_HANDLE_LIST'
            self._api(self._kernel.UpdateProcThreadAttribute(
                self._attributes, 0, 0x20002, self._handle_array,
                C.sizeof(self._handle_array), None, None))
            self.info.StartupInfo.cb = C.sizeof(StartupInfoEx)
            self.info.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
            self.info.StartupInfo.hStdInput, self.info.StartupInfo.hStdOutput, self.info.StartupInfo.hStdError = self._duplicates
            self.info.lpAttributeList = C.addressof(self._attributes)
            self.prepared = True
        except BaseException as error:
            primary_type, phase = type(error).__name__, self.phase
            self.failed = True
            try:
                self.close()
            except BaseException:
                pass  # close retained the exact cleanup types; preserve primary
            raise StartupFailure(phase, primary_type, self.cleanup_errors, self.winerror) from None

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.prepared = False
        # Keep buffers alive even if Delete raises; never retry unknown release.
        if self._initialized:
            try:
                self._kernel.DeleteProcThreadAttributeList(self._attributes)
            except BaseException as error:
                self.cleanup_errors.append(('DELETE_ATTRIBUTES', type(error).__name__, None))
        for handle in reversed(self._duplicates):
            try:
                if not self._kernel.CloseHandle(handle):
                    self.cleanup_errors.append(('CLOSE_DUPLICATE', 'WIN32_FALSE', C.get_last_error()))
            except BaseException as error:
                self.cleanup_errors.append(('CLOSE_DUPLICATE', type(error).__name__, None))
        C.memset(C.byref(self.info), 0, C.sizeof(self.info))
        if self.cleanup_errors:
            self.failed = True
            raise StartupFailure('CLOSE', None, self.cleanup_errors, self.winerror)
