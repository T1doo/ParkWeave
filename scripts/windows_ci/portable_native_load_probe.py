"""Closed candidate: observe one process's locked DLLs, never initialize an app.

The current CLI refuses before filesystem/native access. Enabling a future
window requires a separately reviewed source change, not a command-line flag.
Origin classification is not an Authenticode or non-administrator acceptance.
"""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys

WINDOW_APPROVED = False
PRODUCT_SOURCE = 'd0b1403db07b76c152fc80a1b23070c974debad9'
SUBSET_SHA256 = '4b17e66e861af2f05e1f32ca7ac2c604c0363994c64ae17b794d0fe1846df1b4'
# Existing static OS names plus the three direct OS imports observed in the
# frozen wheels. No product loader allowlist is changed; unknown names fail.
SYSTEM_NAMES = frozenset(('kernel32.dll kernelbase.dll ntdll.dll advapi32.dll user32.dll '
    'gdi32.dll gdi32full.dll shell32.dll shlwapi.dll ole32.dll oleaut32.dll '
    'ws2_32.dll crypt32.dll bcrypt.dll bcryptprimitives.dll secur32.dll '
    'rpcrt4.dll version.dll comdlg32.dll comctl32.dll imm32.dll winmm.dll '
    'normaliz.dll psapi.dll userenv.dll netapi32.dll wldap32.dll dnsapi.dll '
    'iphlpapi.dll mswsock.dll ncrypt.dll wintrust.dll setupapi.dll ucrtbase.dll '
    'msvcrt.dll shfolder.dll dbghelp.dll winspool.drv pdh.dll powrprof.dll propsys.dll').split())


class ProbeRefused(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise ProbeRefused(reason)


def canonical(rows):
    return (json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def classify_module(path, root, system, expected, system_names):
    """Pure Windows path policy; actual file bytes are checked separately."""
    path, root, system = map(PureWindowsPath, (path, root, system))
    require(path.is_absolute() and not str(path).startswith('\\\\') and '..' not in path.parts,
            'MODULE_PATH_REFUSED')
    private_names = {PureWindowsPath(n).name.casefold() for n in expected
                     if n.lower().endswith(('.exe', '.dll', '.pyd'))}
    if path.is_relative_to(root):
        relative = path.relative_to(root).as_posix()
        names = {n.casefold(): n for n in expected}
        require(relative.casefold() in names and relative.lower().endswith(('.exe', '.dll', '.pyd')),
                'UNLISTED_PACKAGE_MODULE')
        return {'kind': 'PACKAGE', 'path': names[relative.casefold()]}
    require(path.name.casefold() not in private_names and
            not re.match(r'(?:vcruntime[0-9]|msvcp[0-9]|libpq-|libssl-|libcrypto-)', path.name.lower()),
            'EXTERNAL_THIRD_PARTY_MODULE')
    if not (path.parent == system and path.name.casefold() in system_names):
        error = ProbeRefused('EXTERNAL_OR_UNKNOWN_MODULE')
        error.module_name = path.name[:120]
        raise error
    return {'kind': 'SYSTEM_DIRECTORY', 'path': 'System32/' + path.name.casefold()}


def file_state(path):
    info = path.lstat()
    require(path.is_file() and not path.is_symlink() and
            not getattr(info, 'st_file_attributes', 0) & 0x400, 'FILE_OBJECT_CHANGED')
    raw = path.read_bytes()
    after = path.lstat()
    require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'FILE_CHANGED_DURING_READ')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns), {
        'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify_files(root, expected):
    actual = {}; identities = {'': directory_state(root)}
    for path in root.rglob('*'):
        info = path.lstat()
        require(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'PAYLOAD_LINK_REFUSED')
        if path.is_dir():
            identities[path.relative_to(root).as_posix() + '/'] = directory_state(path)
            continue
        name = path.relative_to(root).as_posix()
        require(name in expected, 'PAYLOAD_FILE_SET_CHANGED')
        identities[name], actual[name] = file_state(path)
    require(actual == expected, 'PAYLOAD_CONTENT_CHANGED')
    return identities


def directory_state(path):
    info = path.lstat()
    require(path.is_dir() and not path.is_symlink() and
            not getattr(info, 'st_file_attributes', 0) & 0x400, 'DIRECTORY_OBJECT_CHANGED')
    return info.st_dev, info.st_ino


def own_windows_modules():
    """Read the current process only, bounded buffers, no PID lookup/token API."""
    import ctypes
    require(os.name == 'nt', 'WINDOWS_REQUIRED')
    handle = ctypes.c_void_p
    kernel = ctypes.WinDLL('kernel32.dll', winmode=0x800, use_last_error=True)
    kernel.GetCurrentProcess.restype = handle
    kernel.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint32
    kernel.K32EnumProcessModulesEx.argtypes = [handle, ctypes.POINTER(handle), ctypes.c_uint32,
                                              ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
    kernel.K32EnumProcessModulesEx.restype = ctypes.c_int32
    kernel.K32GetModuleFileNameExW.argtypes = [handle, handle, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.K32GetModuleFileNameExW.restype = ctypes.c_uint32
    def api_result(value, reason):
        if not value:
            error = ProbeRefused(reason); error.winerror = ctypes.get_last_error()
            raise error
        return value
    system = ctypes.create_unicode_buffer(32768)
    length = api_result(kernel.GetSystemDirectoryW(system, len(system)), 'SYSTEM_DIRECTORY_READ_FAILED')
    require(length < len(system), 'SYSTEM_DIRECTORY_BUFFER_REFUSED')
    process = kernel.GetCurrentProcess()
    modules = (handle * 1024)(); needed = ctypes.c_uint32()
    api_result(kernel.K32EnumProcessModulesEx(process, modules, ctypes.sizeof(modules),
               ctypes.byref(needed), 3), 'MODULE_ENUMERATION_FAILED')
    require(0 < needed.value <= ctypes.sizeof(modules) and
            needed.value % ctypes.sizeof(handle) == 0, 'MODULE_ENUMERATION_FAILED')
    paths = []
    for module in modules[:needed.value // ctypes.sizeof(handle)]:
        buffer = ctypes.create_unicode_buffer(32768)
        count = api_result(kernel.K32GetModuleFileNameExW(process, module, buffer, len(buffer)), 'MODULE_PATH_READ_FAILED')
        require(count < len(buffer), 'MODULE_PATH_BUFFER_REFUSED')
        paths.append(buffer.value)
    return str(Path(system.value).resolve(strict=True)), [str(Path(p).resolve(strict=True)) for p in paths]


def observe(root, expected, system_names):
    require(sys.platform == 'win32' and sys.version_info[:3] == (3, 14, 9) and
            sys.maxsize > 2**32 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            'TARGET_INTERPRETER_OR_FLAGS_REFUSED')
    require(Path(sys.executable).resolve() == root / 'runtime/python/python.exe', 'INTERPRETER_ORIGIN_REFUSED')
    require([str(Path(p).resolve()) for p in sys.path] ==
            [str(root / p) for p in ('runtime/python/python314.zip', 'runtime/python',
             'vendor', 'launcher', 'app/src', 'app')], 'IMPORT_PATH_REFUSED')
    before = verify_files(root, expected)
    # Python audit events only: this is not a kernel network sandbox.
    def audit(event, args):
        if event.startswith('subprocess.') or event in ('socket.__new__', 'socket.connect', 'socket.bind',
                'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto',
                'socket.sendmsg', 'os.system', 'os.exec', 'os.spawn', 'os.startfile'):
            raise ProbeRefused('BUSINESS_NETWORK_OR_CHILD_REFUSED')
    sys.addaudithook(audit)
    import ssl
    import ctypes
    import psutil
    import pydantic_core
    import psycopg
    import psycopg_binary.pq
    import psycopg_binary._psycopg
    import certifi
    require(psutil.__version__ == '7.2.2' and pydantic_core.__version__ == '2.46.5' and
            psycopg.__version__ == '3.3.6' and psycopg.pq.__impl__ == 'binary' and
            certifi.__version__ == '2026.10.23', 'MODULE_VERSION_OR_IMPLEMENTATION_REFUSED')
    require(pydantic_core.SchemaValidator({'type': 'int'}).validate_python('17') == 17, 'NATIVE_CALL_FAILED')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    require(Path(certifi.where()).resolve() == root / 'vendor/certifi/cacert.pem', 'CERTIFI_ORIGIN_REFUSED')
    context.load_verify_locations(cafile=certifi.where())
    require(len(context.get_ca_certs()) == 118, 'CERTIFI_ROOT_COUNT_REFUSED')
    system, paths = own_windows_modules()
    observed = [classify_module(p, str(root), system, expected, system_names) for p in paths]
    system2, paths2 = own_windows_modules()
    require(system == system2 and set(paths) == set(paths2), 'MODULE_SET_CHANGED')
    package = {item['path'] for item in observed if item['kind'] == 'PACKAGE'}
    required = {'runtime/python/python.exe', 'runtime/python/python314.dll',
                'runtime/python/_ssl.pyd', 'runtime/python/_ctypes.pyd',
                'vendor/psycopg_binary/pq.cp314-win_amd64.pyd',
                'vendor/psycopg_binary/_psycopg.cp314-win_amd64.pyd',
                'vendor/pydantic_core/_pydantic_core.cp314-win_amd64.pyd'}
    required.update(n for n in expected if n.startswith(('vendor/psutil/', 'vendor/psycopg_binary.libs/'))
                    and n.lower().endswith(('.pyd', '.dll')))
    require(required <= package, 'REQUIRED_NATIVE_MODULE_NOT_OBSERVED')
    require(verify_files(root, expected) == before, 'PAYLOAD_IDENTITY_CHANGED')
    return {'status': 'OBSERVED', 'product_source': PRODUCT_SOURCE, 'pid': os.getpid(),
            'modules': sorted(observed, key=lambda row: (row['kind'], row['path'])),
            'business_requests': 0, 'database_connections': 0, 'system_trust_modified': False}


def main():
    if not WINDOW_APPROVED:
        print(json.dumps({'status': 'NOT_RUN', 'reason': 'WINDOW_NOT_APPROVED'}))
        return 2
    try:
        require(len(sys.argv) == 3, 'PROBE_ARGUMENTS_REFUSED')
        root = Path(sys.argv[1]).resolve()
        contract = json.loads(Path(sys.argv[2]).read_bytes())
        expected = contract['files']
        require(hashlib.sha256(canonical(expected)).hexdigest() == SUBSET_SHA256, 'SUBSET_CONTRACT_REFUSED')
        require(set(contract) == {'files'}, 'PROBE_CONTRACT_FIELDS_REFUSED')
        result = observe(root, expected, SYSTEM_NAMES)
    except Exception as error:
        result = {'status': 'FAIL', 'reason': str(error) if type(error) is ProbeRefused else 'UNEXPECTED_EXCEPTION',
                  'error_type': type(error).__name__,
                  'winerror': getattr(error, 'winerror', None) if type(getattr(error, 'winerror', None)) is int else None}
        if getattr(error, 'module_name', None): result['module_name'] = error.module_name
    raw = json.dumps(result, sort_keys=True)
    if len(raw.encode()) > 65536:
        raw = '{"status":"FAIL","reason":"PROBE_OUTPUT_BUDGET"}'
        result = {'status': 'FAIL'}
    print(raw)
    return 0 if result['status'] == 'OBSERVED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
