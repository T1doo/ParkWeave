"""Assemble already acquired, hash-pinned files. No downloads or installers.

The trusted lock is an explicit build input, not a self-authenticating signature.
Native initialization is disabled in every candidate emitted by this builder.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

from .payload import (MANIFEST, SCHEMA, archive_files, dll_closure, file_manifest,
                      pe_imports, require, safe_name)
from . import payload as payload_module

PTH = b'python312.zip\n.\n../../vendor\n../../launcher\n../../app/src\n'
REQUIRED = ('runtime/python/python.exe', 'runtime/python/pythonw.exe',
            'runtime/python/python312.dll', 'runtime/python/python312.zip',
            'runtime/postgresql/bin/postgres.exe', 'runtime/postgresql/bin/initdb.exe',
            'runtime/postgresql/bin/pg_ctl.exe', 'app/scripts/windows/lifecycle.py',
            'app/src/parkweave/api.py', 'app/src/parkweave/web.html',
            'app/src/parkweave/park_demo_web.html')


def assemble(repo, source, assets, lock_path):
    require(len(source) == 40 and all(c in '0123456789abcdef' for c in source), 'FULL_SOURCE_SHA')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo)
    require(git('rev-parse', '--verify', source + '^{commit}').decode().strip() == source, 'SOURCE_COMMIT_REQUIRED')
    for name, path in (('build.py', Path(__file__)), ('payload.py', Path(payload_module.__file__))):
        require(git('show', source + ':scripts/windows_portable/' + name) == path.read_bytes(), 'BUILDER_SOURCE_DRIFT')
    lock_raw = lock_path.read_bytes(); lock = json.loads(lock_raw)
    require(git('show', source + ':scripts/windows_portable/runtime-assets.json') == lock_raw, 'ASSET_LOCK_SOURCE_DRIFT')
    require(lock['schema'] == 'parkweave-windows-runtime-assets/1', 'ASSET_LOCK_SCHEMA')
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
    require('runtime/python/python312._pth' in files, 'EMBEDDED_PTH_MISSING')
    files['runtime/python/python312._pth'] = PTH  # Explicitly locked application-private paths; no site.
    archive = git('archive', '--format=tar', source, '--', 'src/parkweave', 'scripts/windows',
        'scripts/windows_portable/entry.py', 'scripts/windows_portable/payload.py',
        'scripts/windows_portable/ParkWeave.cmd')
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        for item in tar:
            if item.isdir(): continue
            require(item.isfile(), 'SOURCE_OBJECT')
            name = safe_name(item.name)
            if name.startswith('scripts/windows_portable/'):
                base = Path(name).name
                target = base if base == 'ParkWeave.cmd' else 'launcher/' + base
            else: target = 'app/' + name
            put(target, tar.extractfile(item).read())
    put('runtime-assets.json', lock_raw)
    for name in REQUIRED: require(name in files, 'REQUIRED_COMPONENT:' + name)
    closure = dll_closure(files)
    # A static candidate can expose unresolved imports, but it cannot be
    # labelled closed or executed. The end-user entry always refuses startup.
    put('static-dll-audit.json', (json.dumps(closure, indent=2) + '\n').encode())
    manifest = dict(schema=SCHEMA, status='INITIALIZATION_NOT_ENABLED', source_commit=source,
        usable_product=False, native_initialization='OWNER_MUTATION_PAUSED',
        static_loading=closure['status'], windows_execution='NOT_RUN',
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
    a = p.parse_args(); repo = Path(__file__).resolve().parents[2]
    files, manifest = assemble(repo, a.source, a.assets.absolute(), a.lock)
    print(json.dumps(dict(status='ASSEMBLED_BLOCKED_CANDIDATE', usable_product=False,
        static_loading=manifest['static_loading'], **write_zip(a.output, files, manifest))))


if __name__ == '__main__': main()
