"""Exact static symbol requirements for target collection, never admission.

Reads immutable payload bytes only. No native calls, module loading, token
issuance, credentials, API-set guesses or expansion of existing trust domains.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path,PurePosixPath
import re

from . import payload
from .crt_pe import Image


def symbol_requirements(files):
    # Keep the original PG/Python domain policy. Desktop PE files are a
    # separate search domain per containing directory, never Python fallback.
    desktop={name for name in files if name.lower().endswith(('.exe','.dll','.pyd'))
             and not name.startswith(('runtime/postgresql/','runtime/python/','vendor/'))}
    groups=[(False,{name:raw for name,raw in files.items() if name not in desktop})]
    for parent in sorted({str(PurePosixPath(name).parent) for name in desktop}):
        groups.append((True,{name:files[name] for name in desktop if str(PurePosixPath(name).parent)==parent}))
    closure=dict(imports={},native_files=0,modeled_wheel_dependencies=[],unresolved=[],
        missing_private_dependencies=[],unverified_api_contracts=[])
    for is_desktop,group in groups:
        part=payload.dll_closure(group);closure['native_files']+=part['native_files']
        for name,row in part['imports'].items():
            closure['imports'][name]={**row,'domain':'desktop' if is_desktop else row['domain']}
        for key in ('modeled_wheel_dependencies','unresolved','missing_private_dependencies','unverified_api_contracts'):
            closure[key].extend({**row,'domain':'desktop'} if is_desktop and 'domain' in row else row
                                for row in part[key])
    paths={name.casefold():name for name in files}
    wheel={(row['file'],row['dependency']):row['target']
           for row in closure['modeled_wheel_dependencies']}
    reasons={(row['file'],row['dependency']):row['reason'] for row in closure['unresolved']}
    direct=[];missing=[];forwarders=[];resolved=[];external=[];export_cache={}
    def platform_name(dll):
        return (dll in payload.OS_DLLS|payload.SYSTEM_CRT_PREREQUISITES|payload.SYSTEM_DLL_CANDIDATES
            or bool(re.fullmatch(r'(?:api|ext)-ms-[a-z0-9-]+-l[0-9]+-[0-9]+-[0-9]+\.dll',dll)))
    def locate(importer,dll):
        domain=closure['imports'][importer]['domain']
        own=str(PurePosixPath(importer).parent/dll)
        bindir='runtime/postgresql/bin' if domain=='postgresql' else 'runtime/python'
        candidates=(own,) if domain=='desktop' else (own,bindir+'/'+dll)
        return next((paths[item.casefold()] for item in candidates if item.casefold() in paths),
                    None if domain=='desktop' else wheel.get((importer,dll)))
    def inspect_symbol(item):
        target,symbol=item['target'],item['symbol'];seen=set();via=[]
        for _ in range(32):
            if (target,symbol) in seen:
                missing.append(dict(**item,reason='PRIVATE_FORWARDER_CYCLE'));return
            seen.add((target,symbol))
            if target not in export_cache:export_cache[target]=Image(files[target]).export_targets()
            exports=export_cache[target]
            if symbol not in exports:
                missing.append(dict(**item,terminal_target=target,terminal_symbol=symbol));return
            forwarder=exports[symbol][1]
            if forwarder is None:
                direct.append(item)
                if via:resolved.append(dict(**item,terminal_target=target,terminal_symbol=symbol,via=via))
                return
            module,separator,next_symbol=forwarder.partition('.')
            payload.require(separator and re.fullmatch('[A-Za-z0-9_-]+',module) and next_symbol,
                            'LOADER_FORWARDER_FORM')
            if next_symbol.startswith('#'):
                payload.require(bool(re.fullmatch('#[1-9][0-9]{0,4}',next_symbol))
                    and int(next_symbol[1:])<=65535,'LOADER_FORWARDER_ORDINAL')
            dll=module.lower()+'.dll';via.append(dict(file=target,forwarder=forwarder))
            destination=locate(target,dll)
            if destination is None:
                if not platform_name(dll):
                    missing.append(dict(**item,reason='PRIVATE_FORWARDER_TARGET_MISSING',
                        missing_dependency=dll,via=via));return
                forwarders.append(dict(**item,forwarder=forwarder,via=via,resolution='TARGET_REQUIRED'))
                external.append(dict(importer=target,importer_basename=PurePosixPath(target).name.lower(),
                    dependency=dll,symbols=[next_symbol],reason='FORWARDER_TARGET_NOT_OBSERVED',
                    original_importer=item['importer'],resolution='TARGET_REQUIRED'))
                return
            target,symbol=destination,next_symbol
        missing.append(dict(**item,reason='PRIVATE_FORWARDER_DEPTH_LIMIT'))
    for name,row in sorted(closure['imports'].items()):
        imports=Image(files[name]).symbol_imports()
        payload.require(set(imports)==set(row['dependencies']),'LOADER_IMPORT_TABLE_DISAGREES')
        for dll,symbols in sorted(imports.items()):
            target=locate(name,dll)
            if target is None:
                if not platform_name(dll):
                    missing.extend(dict(importer=name,dependency=dll,symbol=symbol,
                        reason='PRIVATE_DLL_OR_INVALID_CONTRACT_MISSING') for symbol in (sorted(symbols) or [None]))
                    continue
                external.append(dict(importer=name,importer_basename=PurePosixPath(name).name.lower(),
                    dependency=dll,symbols=sorted(symbols),
                    reason=reasons.get((name,dll),'DECLARED_SYSTEM_DLL_NOT_OBSERVED'),
                    resolution='TARGET_REQUIRED'))
                continue
            for symbol in sorted(symbols):
                item=dict(importer=name,dependency=dll,target=target,symbol=symbol)
                inspect_symbol(item)
    images={}
    for name in sorted(closure['imports']):
        image=Image(files[name]);opt=image.opt
        images[name]=dict(sha256=sha256(files[name]).hexdigest(),machine='AMD64',
            search_domain=closure['imports'][name]['domain'],
            linker_version=[image.u(opt+2,'B'),image.u(opt+3,'B')],
            declared_os_version=[image.u(opt+40,'H'),image.u(opt+42,'H')],
            subsystem_version=[image.u(opt+48,'H'),image.u(opt+50,'H')],
            subsystem=image.u(opt+68,'H'),size_of_image=image.image_size,
            compiler_strings=[row.decode('ascii') for row in re.findall(
                rb'compiled by msvc-[0-9]+\.[0-9]+\.[0-9]+',files[name])],
            minimum_crt_toolset='NOT_ISSUED_FROM_PE_HEADER')
    return dict(schema='parkweave-static-loader-symbols/1',native_images=closure['native_files'],
        private_symbol_count=len(direct),direct_private_symbol_count=len(direct)-len(resolved),
        missing_private_symbols=missing,
        missing_private_dependencies=closure['missing_private_dependencies'],
        invalid_api_set_contracts=[row for row in closure['unverified_api_contracts'] if not row['syntax_valid']],
        image_facts=images,
        private_forwarders=forwarders,resolved_private_forwarders=resolved,external_imports=external,
        direct_system_dll_names=sorted({row['dependency'] for row in external
            if not row['dependency'].startswith(('api-ms-win-','ext-ms-win-'))}),
        api_set_contract_names=sorted({row['dependency'] for row in external
            if row['dependency'].startswith(('api-ms-win-','ext-ms-win-'))}),
        native_loading='NOT_RUN',activation_allowed=False,usable_product=False,
        limitations=['static imports only; dynamic LoadLibrary/GetProcAddress and all future Job descendants unverified',
            'desktop static model uses containing directory and system targets only; actual initial OS loader search remains unverified',
            'API-set host and forwarder resolution must use this target and importing module; no fixed KernelBase guess',
            'file/symbol availability is not source trust, minimum-toolset acceptance or a native capability'])


def inspect_payload(root):
    root=Path(root).absolute();manifest=payload.verify_directory(root)
    raw_manifest=(root/payload.MANIFEST).read_bytes()
    payload.require(payload.parse_manifest(raw_manifest)==manifest,'LOADER_MANIFEST_CHANGED')
    # Include pinned wheel registration code so the original per-domain search
    # policy is reused. Read bytes again with their original manifest hashes;
    # this is a cooperative read-only snapshot, not an atomic native lease.
    selected={name for name in manifest['files'] if name.lower().endswith(('.exe','.dll','.pyd'))}
    selected.update(row[0] for row in payload.WHEEL_DLL_PROFILES if row[0] in manifest['files'])
    selected.add('runtime-assets.json')
    files={}
    for name in sorted(selected):
        raw=(root/name).read_bytes();row=manifest['files'][name]
        payload.require(len(raw)==row['bytes'] and sha256(raw).hexdigest()==row['sha256'],'LOADER_INPUT_BYTES_CHANGED')
        files[name]=raw
    report=symbol_requirements(files)
    return dict(**report,payload_source=manifest['source_commit'],
        payload_manifest_sha256=sha256(raw_manifest).hexdigest(),
        producer_assets=[{key:row[key] for key in ('file','version','sha256')}
            for row in json.loads(files['runtime-assets.json'])['assets']],
        target_request_schema='parkweave-windows-loader-target/1',
        declared_target=dict(family='Windows 11 desktop',architecture='AMD64 native',
            python='3.12 x64',minimum_accepted_build=None,production_acceptance='NOT_ESTABLISHED'),
        target_fields=dict(
            os=dict(nt_major='integer',nt_minor='integer',build='integer',ubr='integer',
                    edition_id='string',installation_type='Client or server; desktop scope is Client'),
            architecture=dict(os_64bit='boolean',process_64bit='boolean',
                native_machine='PE machine 0x8664',process_machine='IsWow64Process2; 0 for native'),
            system_directory='actual GetSystemDirectoryW result, never PATH or guessed C drive',
            system_files='exact requested basenames: path/size/SHA256/PE Machine/FileVersion/Authenticode status; missing or unknown explicit',
            api_set='ApiSetSchema file identity/hash/version plus target contract-to-host mapping for each importer; presence/hash alone is not resolution',
            module_exports='exact named/ordinal exports and forwarder strings of requested target hosts, read from the same hashed image',
            toolchains='use the attached pinned-asset/header/compiler-string facts now; linker fields alone do not prove a minimum CRT toolset. Lock published upstream minima where available; do not invent missing producer metadata or substitute it for target compatibility tests',
            loaded_origins='later original process HANDLE/birth/Job/image and module source observations; not collected by this static plan'),
        response_is_native_witness=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload',required=True,type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(inspect_payload(args.payload),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
