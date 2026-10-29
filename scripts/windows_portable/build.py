"""Assemble already acquired, hash-pinned files. No downloads or installers.

The trusted lock is an explicit build input, not a self-authenticating signature.
Native initialization is disabled in every candidate emitted by this builder.
"""
import argparse
from email import policy
from email.parser import BytesHeaderParser
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
import zipfile

from .payload import (MANIFEST, SCHEMA, archive_files, dll_closure, file_manifest,
                      pe_imports, require, safe_name)
from . import payload as payload_module

PTH = b'python312.zip\n.\n../../vendor\n../../launcher\n../../app/src\n../../app\n'
# Frozen runtime sources only: no tests, builder, or general CI command surface.
RUNTIME_SOURCES = tuple('scripts/windows_portable/' + name for name in (
    '__init__.py', 'application_readiness.py', 'cluster_processes.py', 'controller.py',
    'credential_envelope.py', 'directories.py', 'endpoint_plan.py', 'fixed_directories.py',
    'fixed_journal.py', 'fixed_secret_store.py', 'fixed_store_security.py', 'fixed_windows_journal.py',
    'initialize.py', 'instance_processes.py', 'isolated_pipe.py', 'payload.py', 'polling_database.py',
    'processes.py', 'runtime_payload.py', 'windows_directory_handles.py', 'windows_endpoint.py',
    'windows_process_handles.py', 'windows_user_protection.py',
    'native_composition.py', 'native_cluster.py', 'native_instance_security.py',
    'native_runtime_staging.py', 'native_web_login.py', 'native_system_crt.py', 'crt_pe.py',
    'native_acceptance_contract.py',
    'desktop_bridge.py', 'desktop_profile.py',
    'native_database_endpoint.py', 'native_protected_bootstrap.py', 'native_preparation_sessions.py',
    'native_secret_store_candidate.py', 'native_layout_candidate.py', 'dpapi_native_candidate.py',
    'pgdata_candidate.py', 'restricted_token_candidate.py',
    'restricted_initdb_candidate.py', 'restricted_startup_candidate.py', 'default_dacl_candidate.py',
    'initdb_pipe_candidate.py', 'initdb_client_candidate.py', 'local_preparation.py',
    'local_preparation_identity.py', 'local_preparation_transport.py',
)) + ('scripts/windows_ci/owned_job.py', 'scripts/windows_ci/job_stop_observation.py')
LAUNCHER_SOURCES = ('scripts/windows_portable/entry.py', 'scripts/windows_portable/payload.py',
                    'scripts/windows_portable/ParkWeave.cmd', 'scripts/windows_portable/desktop_bridge.py')
REQUIRED = ('runtime/python/python.exe', 'runtime/python/pythonw.exe',
            'runtime/python/python312.dll', 'runtime/python/python312.zip',
            'runtime/postgresql/bin/postgres.exe', 'runtime/postgresql/bin/initdb.exe',
            'runtime/postgresql/bin/pg_ctl.exe', 'app/scripts/windows/lifecycle.py',
            'app/src/parkweave/api.py', 'app/src/parkweave/web.html',
            'app/src/parkweave/park_demo_web.html') + tuple('app/' + name for name in RUNTIME_SOURCES)


def python_layout(assets):
    """Closed build layouts, not approval to acquire or execute either asset."""
    rows = [a for a in assets if a.get('kind') == 'python']
    require(len(rows) == 1, 'SINGLE_PYTHON_ASSET')
    row = rows[0]
    versions = {'3.12.10': (3, 12, 10), '3.14.9': (3, 14, 9)}
    version = versions.get(row.get('version'))
    require(version is not None and row['file'] ==
            'python-' + row['version'] + '-embed-amd64.zip', 'PYTHON_ASSET_LAYOUT')
    return version, 'python' + str(version[0]) + str(version[1])


def wheel_tags(value):
    require(type(value) is str and len(value) <= 256 and re.fullmatch(
        r'[a-z0-9_]+(?:\.[a-z0-9_]+)*-[a-z0-9_]+(?:\.[a-z0-9_]+)*-[a-z0-9_]+(?:\.[a-z0-9_]+)*',
        value), 'WHEEL_TAG_SYNTAX')
    parts = [part.split('.') for part in value.split('-')]
    require(all(re.fullmatch(r'(?:py[23](?:0|[1-9][0-9]*)?|cp3(?:0|[1-9][0-9]*))', tag)
                for tag in parts[0]), 'WHEEL_PYTHON_TAG')
    require(all(re.fullmatch(r'(?:none|abi3|cp3(?:0|[1-9][0-9]*)t?)', tag)
                for tag in parts[1]), 'WHEEL_ABI_TAG')
    require(all(len(part) == len(set(part)) for part in parts), 'WHEEL_TAG_DUPLICATE')
    require(len(parts[0]) * len(parts[1]) * len(parts[2]) <= 32, 'WHEEL_TAG_COUNT')
    return set(product(*parts))


def python_requirement(value, version):
    """Release-only subset used by this locked payload; refuse other syntax."""
    require(len(value) <= 1024, 'WHEEL_PYTHON_SPECIFIER')
    for clause in value.split(','):
        match = re.fullmatch(r'\s*(>=|<=|==|!=|>|<)\s*([0-9]+(?:\.[0-9]+){0,2})(\.\*)?\s*', clause)
        require(match is not None, 'WHEEL_PYTHON_SPECIFIER')
        op, release, wildcard = match.groups()
        numbers = tuple(map(int, release.split('.')))
        if wildcard:
            require(op in ('==', '!='), 'WHEEL_PYTHON_SPECIFIER')
            equal = version[:len(numbers)] == numbers
            accepted = equal if op == '==' else not equal
        else:
            target = numbers + (0,) * (3 - len(numbers))
            accepted = {'>=': version >= target, '<=': version <= target,
                        '==': version == target, '!=': version != target,
                        '>': version > target, '<': version < target}[op]
        require(accepted, 'WHEEL_REQUIRES_PYTHON')


def verify_application_python(raw, version):
    """Check the frozen application's own contract, not just dependency wheel tags."""
    require(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024, 'APPLICATION_PYTHON_METADATA')
    try:
        requirement = tomllib.loads(raw.decode('utf-8'))['project']['requires-python']
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise payload_module.PayloadRefused('APPLICATION_PYTHON_METADATA') from None
    require(type(requirement) is str and bool(requirement.strip()), 'APPLICATION_PYTHON_METADATA')
    try:
        python_requirement(requirement, version)
    except payload_module.PayloadRefused:
        raise payload_module.PayloadRefused('APPLICATION_REQUIRES_PYTHON') from None


def verify_wheel(asset, members, version):
    """Validate actual metadata, not just a compatible-looking archive name."""
    name = Path(asset['file']).name
    require(name.endswith('.whl'), 'WHEEL_FILENAME')
    parts = name[:-4].split('-')
    require(len(parts) in (5, 6) and re.fullmatch(r'[A-Za-z0-9_.]+', parts[0]) and
            parts[1] == asset['version'], 'WHEEL_FILENAME')
    # The asset lock uses two/three-component canonical numeric releases only.
    require(re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){1,2}', parts[1]),
            'WHEEL_RELEASE_VERSION')
    if len(parts) == 6: require(re.fullmatch(r'[0-9][A-Za-z0-9_]*', parts[2]), 'WHEEL_BUILD_TAG')
    expected_tags = wheel_tags('-'.join(parts[-3:]))
    directory = parts[0] + '-' + parts[1] + '.dist-info/'
    required = {directory + 'WHEEL', directory + 'METADATA'}
    require({n for n in members if n.endswith(('.dist-info/WHEEL', '.dist-info/METADATA'))}
            == required, 'WHEEL_METADATA_FILES')
    parser = BytesHeaderParser(policy=policy.default)
    def headers(path, limit):
        raw = members[path]
        require(len(raw) <= limit, 'WHEEL_METADATA_BYTES')
        result = parser.parsebytes(raw)
        require(not result.defects and not any(v.defects for _, v in result.items()), 'WHEEL_METADATA_HEADERS')
        return result
    wheel = headers(directory + 'WHEEL', 16384)
    metadata = headers(directory + 'METADATA', 4 * 1024 * 1024)
    require(not wheel.get_payload().strip(), 'WHEEL_METADATA_HEADERS')
    def one(message, key):
        values = message.get_all(key, [])
        require(len(values) == 1, 'WHEEL_METADATA_FIELD:' + key)
        return str(values[0]).strip()
    require(one(metadata, 'Metadata-Version') in
            ('1.1', '1.2', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6'), 'WHEEL_CORE_METADATA_VERSION')
    require(one(wheel, 'Wheel-Version') == '1.0', 'WHEEL_FORMAT_VERSION')
    pure = one(wheel, 'Root-Is-Purelib')
    require(pure in ('true', 'false'), 'WHEEL_PURELIB')
    tags = set(); declared = wheel.get_all('Tag', [])
    require(0 < len(declared) <= 32, 'WHEEL_TAG_COUNT')
    for value in declared:
        row = wheel_tags(str(value).strip())
        require(not tags & row, 'WHEEL_TAG_DUPLICATE')
        tags.update(row)
    require(tags == expected_tags, 'WHEEL_TAG_MISMATCH')
    require(all(tag[2] in ('any', 'win_amd64') for tag in tags), 'WHEEL_TARGET_TAG')
    metadata_name = one(metadata, 'Name')
    require(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?', metadata_name), 'WHEEL_METADATA_NAME')
    normalize = lambda s: re.sub(r'[-_.]+', '_', s).lower()
    require(normalize(metadata_name) == normalize(parts[0]) and
            one(metadata, 'Version') == parts[1], 'WHEEL_METADATA_IDENTITY')
    requirements = metadata.get_all('Requires-Python', [])
    require(len(requirements) <= 1, 'WHEEL_METADATA_FIELD:Requires-Python')
    if requirements: python_requirement(str(requirements[0]), version)
    def compatible(tag):
        interpreter, abi, platform = tag
        if platform not in ('any', 'win_amd64'): return False
        cp = re.fullmatch(r'cp3([0-9]+)', interpreter)
        if abi == 'abi3':
            return bool(cp and 2 <= int(cp[1]) <= version[1] and platform == 'win_amd64' and pure == 'false')
        if abi != 'none':
            return interpreter == abi == 'cp3' + str(version[1]) and platform == 'win_amd64' and pure == 'false'
        py = re.fullmatch(r'py3([0-9]+)?', interpreter)
        return bool((py and (py[1] is None or int(py[1]) <= version[1]) or
                     cp and int(cp[1]) == version[1]) and (platform != 'any' or pure == 'true'))
    require(any(compatible(tag) for tag in tags), 'WHEEL_TARGET_TAG')
    if any(tag[2] == 'any' for tag in tags):
        require(not any(n.lower().endswith(('.pyd', '.dll', '.exe')) for n in members), 'WHEEL_ANY_NATIVE_FILE')
    if any(n.lower().endswith('.pyd') for n in members):
        require(any(compatible(tag) and tag[1] != 'none' for tag in tags), 'WHEEL_NATIVE_ABI')


def assemble(repo, source, assets, lock_path, *, desktop_assets=None):
    require(len(source) == 40 and all(c in '0123456789abcdef' for c in source), 'FULL_SOURCE_SHA')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo)
    require(git('rev-parse', '--verify', source + '^{commit}').decode().strip() == source, 'SOURCE_COMMIT_REQUIRED')
    for name, path in (('build.py', Path(__file__)), ('payload.py', Path(payload_module.__file__))):
        require(git('show', source + ':scripts/windows_portable/' + name) == path.read_bytes(), 'BUILDER_SOURCE_DRIFT')
    lock_raw = lock_path.read_bytes(); lock = json.loads(lock_raw)
    require(git('show', source + ':scripts/windows_portable/runtime-assets.json') == lock_raw, 'ASSET_LOCK_SOURCE_DRIFT')
    require(lock['schema'] == 'parkweave-windows-runtime-assets/1', 'ASSET_LOCK_SCHEMA')
    version, stem = python_layout(lock['assets'])
    verify_application_python(git('show', source + ':pyproject.toml'), version)
    files = {}; asset_report = []
    def put(name, data):
        safe_name(name)
        require(name.casefold() not in {n.casefold() for n in files}, 'ASSEMBLY_COLLISION')
        files[name] = data
    for asset in lock['assets']:
        name = safe_name(asset['file']); path = assets / name
        require(path.resolve() == path.absolute() and not path.is_symlink(), 'ASSET_LINK')
        raw = path.read_bytes()
        require(len(raw) == asset['bytes'] and sha256(raw).hexdigest() == asset['sha256'], 'ASSET_HASH')
        require(asset['license_files'] and asset['url'].startswith('https://'), 'ASSET_PROVENANCE')
        group = asset['kind']
        require(group in ('python', 'wheel', 'postgresql'), 'ASSET_KIND')
        # Do not extract the unrelated pgAdmin, StackBuilder or SDK payload.
        selected = None
        if group == 'postgresql':
            selected = lambda n: (n.startswith(('pgsql/bin/', 'pgsql/share/')) or
                n.startswith('pgsql/lib/') and n.lower().endswith('.dll') or n in asset['license_files'])
        members = archive_files(path, selected=selected)
        for n, h in asset['license_files'].items():
            require(n in members and sha256(members[n]).hexdigest() == h, 'ASSET_LICENSE')
        if group == 'wheel': verify_wheel(asset, members, version)
        if group == 'python':
            require({stem + suffix for suffix in ('.dll', '.zip', '._pth')} <= members.keys(), 'PYTHON_ARCHIVE_LAYOUT')
            require(not any(re.fullmatch(r'python3[0-9]+\.(dll|zip|_pth)', n) and
                            not n.startswith(stem + '.') for n in members), 'PYTHON_ARCHIVE_LAYOUT')
        if group == 'postgresql':
            # Include the server lifecycle executables and their static DLL
            # dependencies, not StackBuilder, wxWidgets, ecpg or other tools.
            index = {n.casefold(): n for n in members}
            queue = ['pgsql/bin/' + n for n in ('initdb.exe', 'postgres.exe', 'pg_ctl.exe')]
            # initdb's default language, text search and encoding conversions
            # are dynamically loaded: they are absent from EXE import tables.
            bootstrap = [n for n in members if n.startswith('pgsql/share/') and
                ('/' not in n[len('pgsql/share/'):] and n.endswith(('.bki', '.sql')) or
                 n == 'pgsql/share/extension/plpgsql.control' or
                 n.startswith('pgsql/share/extension/plpgsql--') and n.endswith('.sql'))]
            require('pgsql/share/extension/plpgsql.control' in bootstrap, 'PG_DEFAULT_LANGUAGE_CONTROL')
            dynamic = set()
            for n in bootstrap:
                for module in re.findall(rb'\$libdir/([a-zA-Z0-9_-]+)', members[n]):
                    dynamic.add('pgsql/lib/' + module.decode('ascii') + '.dll')
            require('pgsql/lib/plpgsql.dll' in dynamic, 'PG_DEFAULT_LANGUAGE_MODULE')
            queue.extend(sorted(dynamic))
            keep = set()
            while queue:
                n = queue.pop()
                require(n in members, 'PG_EXECUTABLE_MISSING')
                if n in keep: continue
                keep.add(n)
                for dll in pe_imports(members[n]):
                    target = index.get(str(Path(n).parent / dll).replace('\\', '/').casefold()) or index.get('pgsql/bin/' + dll)
                    if target is not None: queue.append(target)
            members = {n: b for n, b in members.items() if n in keep or
                       n.startswith('pgsql/share/') or n in asset['license_files']}
        for n, data in members.items():
            if group == 'python': target = 'runtime/python/' + n
            elif group == 'wheel':
                require(not n.endswith(('.pth', '.egg-link')) and '.data/' not in n, 'WHEEL_EXECUTABLE_INSTALL_HOOK')
                target = 'vendor/' + n
            else:
                require(n.startswith('pgsql/'), 'PG_LAYOUT')
                target = 'runtime/postgresql/' + n[6:]
            put(target, data)
        asset_report.append({k: asset[k] for k in ('file', 'kind', 'version', 'url', 'bytes', 'sha256', 'license_files')})
    require('runtime/python/' + stem + '._pth' in files, 'EMBEDDED_PTH_MISSING')
    files['runtime/python/' + stem + '._pth'] = PTH.replace(b'python312', stem.encode('ascii'))
    archive = git('archive', '--format=tar', source, '--', 'src/parkweave', 'scripts/windows',
                  *RUNTIME_SOURCES, *LAUNCHER_SOURCES)
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        for item in tar:
            if item.isdir(): continue
            require(item.isfile(), 'SOURCE_OBJECT')
            name = safe_name(item.name)
            data = tar.extractfile(item).read()
            if name in LAUNCHER_SOURCES:
                base = Path(name).name
                target = base if base == 'ParkWeave.cmd' else 'launcher/' + base
                put(target, data)
                if name not in RUNTIME_SOURCES: continue
            put('app/' + name, data)
    put('runtime-assets.json', lock_raw)
    for name in REQUIRED:
        name = name.replace('python312', stem)
        require(name in files, 'REQUIRED_COMPONENT:' + name)
    if desktop_assets is not None:
        names={'ParkWeave.exe','WebView2Loader.dll','WebView2-SDK-LICENSE.txt','Desktop-Runtime-NOTICES.txt','desktop-build.json'}
        require({p.name for p in desktop_assets.iterdir()}==names,'DESKTOP_ASSET_SET')
        record=json.loads((desktop_assets/'desktop-build.json').read_bytes())
        require(record['schema']=='parkweave-desktop-build/1'
            and record['host_source_sha256']==sha256(git('show',source+':scripts/windows_desktop/host.cpp')).hexdigest()
            and record['build_script_sha256']==sha256(git('show',source+':scripts/windows_desktop/build.py')).hexdigest()
            and record['python_sha256']==sha256(files['runtime/python/python.exe']).hexdigest()
            and record['sdk_sha256']=='5ea526bbd728adda0da4d31219267e96460494a427e4894c4e09d9f320f4b9aa'
            and record['native_windows_execution'] is False
            and record['compiler_archive_and_binary_verified'] is True
            and record['compatibility_header_sha256']==sha256(git('show',source+':scripts/windows_desktop/EventToken.h')).hexdigest()
            and record['namespace_policy_sha256']==sha256(git('show',source+':scripts/windows_desktop/namespace_guard.h')).hexdigest()
            and record['bootstrap_files']==file_manifest(files),'DESKTOP_SOURCE_OR_SCOPE')
        for name in sorted(names):
            path=desktop_assets/name
            require(path.resolve()==path.absolute() and not path.is_symlink(),'DESKTOP_ASSET_LINK')
            raw=path.read_bytes()
            if name!='desktop-build.json':
                row=record['files'][name]
                require(len(raw)==row['bytes'] and sha256(raw).hexdigest()==row['sha256'],'DESKTOP_ASSET_HASH')
            if name=='WebView2Loader.dll':require(sha256(raw).hexdigest()=='2f965e10aed3b356a408978a0e6d74eb86e3e722dd008fa9ad39f68884479e85','DESKTOP_LOADER_PIN')
            put(name if name=='ParkWeave.exe' else 'launcher/'+name,raw)
    closure = dll_closure(files)
    # A static candidate can expose unresolved imports, but it cannot be
    # labelled closed or executed. Native startup retains the original gates.
    put('static-dll-audit.json', (json.dumps(closure, indent=2) + '\n').encode())
    manifest = dict(schema=SCHEMA, status='INITIALIZATION_NOT_ENABLED', source_commit=source,
        usable_product=False, native_initialization='OWNER_MUTATION_PAUSED',
        static_loading=closure['status'], windows_execution='NOT_RUN',
        desktop_host='WIN32_WEBVIEW2_NOT_NATIVE_ACCEPTED' if desktop_assets is not None else 'NOT_INCLUDED',
        publisher_authenticity='EXTERNAL_ZIP_SHA_REQUIRED_NOT_PROVEN_BY_INTERNAL_MANIFEST',
        runtime_assets=asset_report, files=file_manifest(files))
    return files, manifest


def write_zip(output, files, manifest):
    payload = {**files, MANIFEST: (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()}
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
                z.writestr(info, data)
    return dict(bytes=output.stat().st_size, sha256=sha256(output.read_bytes()).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True); p.add_argument('--assets', required=True, type=Path)
    p.add_argument('--lock', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
    p.add_argument('--desktop-assets',type=Path)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[2]
    files, manifest = assemble(repo, a.source, a.assets.absolute(), a.lock,
        desktop_assets=a.desktop_assets.absolute() if a.desktop_assets is not None else None)
    print(json.dumps(dict(status='ASSEMBLED_BLOCKED_CANDIDATE', usable_product=False,
        static_loading=manifest['static_loading'], **write_zip(a.output, files, manifest))))


if __name__ == '__main__': main()
