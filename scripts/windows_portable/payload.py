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
DEVICE = re.compile(r'(?i)^(con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)')
# Named OS DLL declarations only. CRT is NOT an OS_DLLS shortcut: the explicit
# existing-system CRT contract requires an issued native read-only witness.
# Other PG/Python libraries remain confined to their own payload domain.
OS_DLLS = frozenset(('kernel32.dll kernelbase.dll ntdll.dll advapi32.dll user32.dll '
    'gdi32.dll gdi32full.dll shell32.dll shlwapi.dll ole32.dll oleaut32.dll '
    'ws2_32.dll crypt32.dll bcrypt.dll bcryptprimitives.dll secur32.dll '
    'rpcrt4.dll version.dll comdlg32.dll comctl32.dll imm32.dll winmm.dll '
    'normaliz.dll psapi.dll userenv.dll netapi32.dll wldap32.dll dnsapi.dll '
    'iphlpapi.dll mswsock.dll ncrypt.dll wintrust.dll setupapi.dll ucrtbase.dll '
    'msvcrt.dll shfolder.dll dbghelp.dll winspool.drv').split())
# Classification only: these remain unresolved until observed on the target.
SYSTEM_DLL_CANDIDATES = frozenset(('cabinet.dll','msi.dll','propsys.dll','pdh.dll','powrprof.dll'))
SYSTEM_CRT_PREREQUISITES=frozenset(('vcruntime140.dll','msvcp140.dll'))
# Reviewed, whole-file byte profile from the existing locked psycopg-binary
# 3.3.6 wheel. No execution/AST guessing and no arbitrary .libs directory scan.
WHEEL_DLL_PROFILES = (('vendor/psycopg_binary/__init__.py',
    '712ff217ff67595f391b6dd2a0e148c78a6e74f3e8f4a66116f873c0e49395b4',
    'vendor/psycopg_binary','vendor/psycopg_binary.libs'),)


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


def parse_manifest(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 4 * 1024 * 1024, 'MANIFEST_BYTES')
    def pairs(items):
        value = {}
        for k, v in items:
            require(k not in value, 'JSON_DUPLICATE'); value[k] = v
        return value
    manifest = json.loads(raw, object_pairs_hook=pairs)
    require(type(manifest) is dict and manifest.get('schema') == SCHEMA and
            manifest.get('status') == 'INITIALIZATION_NOT_ENABLED', 'MANIFEST_SCHEMA')
    expected = manifest.get('files')
    require(isinstance(expected, dict) and 0 < len(expected) <= MAX_FILES, 'MANIFEST_FILES')
    seen, total = set(), 0
    for name, row in expected.items():
        safe_name(name)
        require(name.casefold() not in seen and name.casefold() != MANIFEST, 'MANIFEST_COLLISION')
        seen.add(name.casefold())
        require(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and
                0 <= row['bytes'] <= 128 * 1024 * 1024 and type(row['sha256']) is str and
                re.fullmatch('[0-9a-f]{64}', row['sha256']), 'MANIFEST_ROW')
        total += row['bytes']; require(total <= MAX_BYTES, 'PAYLOAD_BYTES')
    return manifest


def verify_directory(root, *, manifest_raw=None):
    root = Path(root).absolute()
    require(root.resolve() == root and not root.is_symlink(), 'ROOT_LINK')
    path = root / MANIFEST
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4 * 1024 * 1024, 'MANIFEST_FILE')
    manifest = parse_manifest(path.read_bytes() if manifest_raw is None else manifest_raw)
    expected = manifest['files']
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
    registrations = []
    for source, digest, package, directory in WHEEL_DLL_PROFILES:
        raw = files.get(source)
        if raw is not None and sha256(raw).hexdigest() == digest:
            registrations.append(dict(source=source,sha256=digest,package=package,directory=directory,
                status='DECLARED_BY_PINNED_WHEEL_CODE_NOT_EXECUTED'))
    modeled = []; platform = []; missing = []
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
            if any(n.casefold() in by_path for n in candidates):
                continue
            if dll in OS_DLLS:
                platform.append(dict(file=name,dependency=dll,kind='DECLARED_SYSTEM_DLL',observed=False))
                continue  # Existing declared-system policy, not new acceptance.
            matches = [profile for profile in registrations if row['domain']=='python' and
                (name.startswith(profile['package']+'/') or name.startswith(profile['directory']+'/'))
                and (profile['directory']+'/'+dll).casefold() in by_path]
            if matches:
                require(len(matches)==1,'WHEEL_DLL_DIRECTORY_AMBIGUOUS')
                profile=matches[0]
                modeled.append(dict(file=name,dependency=dll,target=by_path[(profile['directory']+'/'+dll).casefold()],
                    registration_source=profile['source'],registration_sha256=profile['sha256'],
                    status='STATIC_FILE_PRESENT_IN_DECLARED_WHEEL_DIRECTORY',native_loading='NOT_RUN'))
                continue
            reason='PRIVATE_DLL_MISSING_FROM_DOMAIN'
            if dll.startswith(('api-ms-win-', 'ext-ms-win-')):
                # An API-set-shaped name does not prove that the target OS
                # supplies it. Preserve it as an unresolved OS contract.
                valid=bool(re.fullmatch(r'(?:api|ext)-ms-[a-z0-9-]+-l[0-9]+-[0-9]+-[0-9]+\.dll',dll))
                contracts.append(dict(file=name, contract=dll,syntax_valid=valid,observed=False))
                reason='API_SET_REQUIRES_TARGET_SCHEMA' if valid else 'UNRECOGNIZED_API_SET_NAME'
                platform.append(dict(file=name,dependency=dll,kind=reason,observed=False))
            elif dll in SYSTEM_CRT_PREREQUISITES:
                reason='EXISTING_SIGNED_SYSTEM_CRT_WITNESS_REQUIRED'
                platform.append(dict(file=name,dependency=dll,kind=reason,observed=False))
            elif dll in SYSTEM_DLL_CANDIDATES:
                reason='SYSTEM_DLL_REQUIRES_TARGET_OBSERVATION'
                platform.append(dict(file=name,dependency=dll,kind=reason,observed=False))
            else:
                missing.append(dict(file=name,dependency=dll,domain=row['domain']))
            unresolved.append(dict(file=name, dependency=dll,reason=reason))
    return dict(status='PRIVATE_IMPORTS_PRESENT_OS_LOADING_UNVERIFIED' if not unresolved else 'UNRESOLVED',
                native_files=len(imports), imports=imports, unresolved=unresolved,
                unverified_api_contracts=contracts, native_loading='NOT_RUN',
                missing_private_dependencies=missing,platform_requirements=platform,
                wheel_directory_registrations=registrations,modeled_wheel_dependencies=modeled,
                platform_evidence='NOT_PROVIDED',activation_allowed=False,
                symbols_and_forwarders='NOT_CHECKED', system_lookup='DECLARED_WINDOWS_10_11_DLLS_NOT_OBSERVED')
