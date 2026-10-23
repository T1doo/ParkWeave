"""Stdlib-only payload integrity and static AMD64 import checks; never loads PE."""
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import re
import stat
import struct
import zipfile

MAX_FILES = 16000
MAX_BYTES = 1024 * 1024 * 1024
MANIFEST = 'payload-manifest.json'
SCHEMA = 'parkweave-windows-portable-candidate/1'
DEVICE = re.compile(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)')
# Windows 10/11 API-set contracts and named OS DLLs only. CRT/PG/Python DLLs
# are deliberately absent: these must be resolved inside the payload domain.
OS_DLLS = frozenset(('kernel32.dll kernelbase.dll ntdll.dll advapi32.dll user32.dll '
    'gdi32.dll gdi32full.dll shell32.dll shlwapi.dll ole32.dll oleaut32.dll '
    'ws2_32.dll crypt32.dll bcrypt.dll bcryptprimitives.dll secur32.dll '
    'rpcrt4.dll version.dll comdlg32.dll comctl32.dll imm32.dll winmm.dll '
    'normaliz.dll psapi.dll userenv.dll netapi32.dll wldap32.dll dnsapi.dll '
    'iphlpapi.dll mswsock.dll ncrypt.dll wintrust.dll setupapi.dll ucrtbase.dll '
    'msvcrt.dll shfolder.dll dbghelp.dll winspool.drv').split())


class PayloadRefused(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise PayloadRefused(reason)


def safe_name(name):
    require(isinstance(name, str) and 0 < len(name) <= 220, 'PATH_LENGTH')
    require('\\' not in name and not name.startswith('/') and '\x00' not in name, 'PATH_ABSOLUTE')
    parts = name.split('/')
    require(all(p not in ('', '.', '..') and p[-1] not in ' .' and
                not DEVICE.match(p) and not any(c in p for c in ':<>"|?*') and
                all(ord(c) >= 32 for c in p) for p in parts), 'WINDOWS_PATH')
    require(str(PurePosixPath(name)) == name, 'PATH_NORMALIZATION')
    return name


def archive_files(path, *, selected=None):
    result = {}; seen = set(); total = 0
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist()) <= 40000, 'ARCHIVE_FILE_COUNT')
        for item in z.infolist():
            if selected is not None and not selected(item.filename):
                continue
            name = safe_name(item.filename.rstrip('/') if item.is_dir() else item.filename)
            folded = name.casefold()
            require(folded not in seen, 'ARCHIVE_CASE_COLLISION'); seen.add(folded)
            kind = stat.S_IFMT(item.external_attr >> 16)
            require(kind in (0, stat.S_IFREG, stat.S_IFDIR) and not item.flag_bits & 1, 'ARCHIVE_OBJECT')
            if item.is_dir():
                continue
            total += item.file_size
            require(item.file_size <= 128 * 1024 * 1024 and total <= MAX_BYTES, 'ARCHIVE_BYTES')
            result[name] = z.read(item)
    # Reject file/ancestor collisions before any extraction is attempted.
    files = {n.casefold() for n in result}
    for name in files:
        require(not any('/'.join(name.split('/')[:i]) in files
                        for i in range(1, len(name.split('/')))), 'ARCHIVE_PARENT_FILE')
    return result


def file_manifest(files):
    require(0 < len(files) <= MAX_FILES, 'PAYLOAD_FILE_COUNT')
    seen = set()
    for name in files:
        safe_name(name)
        require(name.casefold() not in seen and name != MANIFEST, 'PAYLOAD_COLLISION')
        seen.add(name.casefold())
    require(sum(map(len, files.values())) <= MAX_BYTES, 'PAYLOAD_BYTES')
    return {n: dict(bytes=len(b), sha256=sha256(b).hexdigest()) for n, b in sorted(files.items())}


def verify_directory(root):
    root = Path(root).absolute()
    require(root.resolve() == root and not root.is_symlink(), 'ROOT_LINK')
    path = root / MANIFEST
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4 * 1024 * 1024, 'MANIFEST_FILE')
    def pairs(items):
        value = {}
        for k, v in items:
            require(k not in value, 'JSON_DUPLICATE'); value[k] = v
        return value
    manifest = json.loads(path.read_bytes(), object_pairs_hook=pairs)
    require(manifest.get('schema') == SCHEMA and manifest.get('status') == 'INITIALIZATION_NOT_ENABLED', 'MANIFEST_SCHEMA')
    expected = manifest.get('files')
    require(isinstance(expected, dict) and 0 < len(expected) <= MAX_FILES, 'MANIFEST_FILES')
    actual = {}; total = 0; seen = set()
    for child in root.rglob('*'):
        name = child.relative_to(root).as_posix(); safe_name(name)
        st = child.lstat()
        require(not stat.S_ISLNK(st.st_mode) and not getattr(st, 'st_file_attributes', 0) & 0x400, 'PAYLOAD_REPARSE')
        require(name.casefold() not in seen, 'PAYLOAD_CASE_COLLISION'); seen.add(name.casefold())
        if child.is_dir():
            continue
        require(stat.S_ISREG(st.st_mode), 'PAYLOAD_OBJECT')
        if name == MANIFEST:
            continue
        total += st.st_size
        require(total <= MAX_BYTES and name in expected, 'PAYLOAD_UNEXPECTED_OR_SIZE')
        row = expected[name]
        require(isinstance(row, dict) and set(row) == {'bytes', 'sha256'} and
                type(row['bytes']) is int and row['bytes'] == st.st_size and
                isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'MANIFEST_ROW')
        require(sha256(child.read_bytes()).hexdigest() == row['sha256'], 'PAYLOAD_HASH')
        actual[name] = row
    require(actual == expected, 'PAYLOAD_MISSING')
    return manifest


def pe_imports(data):
    """Read PE32+ import and delay-import names without executing native code."""
    def number(offset, fmt):
        require(0 <= offset <= len(data) - struct.calcsize(fmt), 'PE_BOUNDS')
        return struct.unpack_from(fmt, data, offset)[0]
    require(data[:2] == b'MZ', 'PE_DOS')
    pe = number(0x3c, '<I')
    require(data[pe:pe + 4] == b'PE\0\0' and number(pe + 4, '<H') == 0x8664, 'PE_AMD64')
    count = number(pe + 6, '<H'); size = number(pe + 20, '<H'); opt = pe + 24
    require(0 < count <= 96 and size >= 240 and number(opt, '<H') == 0x20b, 'PE32_PLUS')
    require(number(opt + 108, '<I') >= 14, 'PE_DIRECTORIES')
    base = number(opt + 24, '<Q'); sections = opt + size
    def offset(rva):
        for i in range(count):
            s = sections + i * 40; va = number(s + 12, '<I')
            raw = number(s + 16, '<I'); ptr = number(s + 20, '<I')
            if va <= rva < va + raw:
                result = ptr + rva - va
                require(result < len(data), 'PE_RVA_BOUNDS'); return result
        raise PayloadRefused('PE_RVA')
    def name(rva):
        start = offset(rva); end = data.find(b'\0', start, start + 256)
        require(end > start, 'PE_IMPORT_NAME')
        try: value = data[start:end].decode('ascii').lower()
        except UnicodeError: raise PayloadRefused('PE_IMPORT_ASCII') from None
        require(re.fullmatch(r'[a-z0-9_.-]+\.(dll|drv|exe)', value), 'PE_IMPORT_PATH')
        return value
    result = set()
    for index, stride in ((1, 20), (13, 32)):
        rva = number(opt + 112 + index * 8, '<I'); length = number(opt + 116 + index * 8, '<I')
        if not rva:
            require(length == 0, 'PE_DIRECTORY_SIZE'); continue
        require(stride <= length <= 1024 * stride, 'PE_IMPORT_LIMIT')
        terminated = False
        for i in range(length // stride):
            pos = offset(rva + i * stride); row = data[pos:pos + stride]
            require(len(row) == stride, 'PE_DESCRIPTOR_BOUNDS')
            if not any(row): terminated = True; break
            n = number(pos + (12 if index == 1 else 4), '<I')
            if index == 13:
                attrs = number(pos, '<I'); require(attrs in (0, 1), 'PE_DELAY_ATTRS')
                if attrs == 0: n -= base
            result.add(name(n))
        require(terminated, 'PE_IMPORT_UNTERMINATED')
    return sorted(result)


def dll_closure(files):
    domains = {'python': {}, 'postgresql': {}}; imports = {}; unresolved = []; contracts = []
    by_path = {name.casefold(): name for name in files}
    for name, data in files.items():
        if not name.lower().endswith(('.exe', '.dll', '.pyd')):
            continue
        domain = 'postgresql' if name.startswith('runtime/postgresql/') else 'python'
        dll = PurePosixPath(name).name.casefold()
        prior = domains[domain].get(dll)
        require(prior is None or sha256(files[prior]).digest() == sha256(data).digest(), 'DOMAIN_DLL_CONFLICT')
        domains[domain][dll] = name
        imports[name] = dict(domain=domain, dependencies=pe_imports(data))
    for name, row in imports.items():
        for dll in row['dependencies']:
            executable_dir = 'runtime/postgresql/bin' if row['domain'] == 'postgresql' else 'runtime/python'
            candidates = (str(PurePosixPath(name).parent / dll), executable_dir + '/' + dll)
            if any(n.casefold() in by_path for n in candidates) or dll in OS_DLLS:
                continue
            if dll.startswith(('api-ms-win-', 'ext-ms-win-')):
                # An API-set-shaped name does not prove that the target OS
                # supplies it. Preserve it as an unresolved OS contract.
                contracts.append(dict(file=name, contract=dll))
            unresolved.append(dict(file=name, dependency=dll))
    return dict(status='PRIVATE_IMPORTS_PRESENT_OS_LOADING_UNVERIFIED' if not unresolved else 'UNRESOLVED',
                native_files=len(imports), imports=imports, unresolved=unresolved,
                unverified_api_contracts=contracts, native_loading='NOT_RUN',
                symbols_and_forwarders='NOT_CHECKED', system_lookup='DECLARED_WINDOWS_10_11_DLLS_NOT_OBSERVED')
