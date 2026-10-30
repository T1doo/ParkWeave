"""Bounded Server 2025 source/protocol observation, never product admission.

No token setters, DPAPI, original lease acquisition, identities, PG/API, target
DLL observation or native product process is invoked. The existing independent
Job measurement remains a separate workflow step with its original scope.
"""
import argparse
import ast
import ctypes
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import sysconfig
import time

BEFORE='e152fd2988df5a3b1e65b7e2e84fd0aa5361565d'
REF='refs/heads/dev/local-product-runtime-20261028'
MARKER='ci: bounded Server 2025 source protocol PW_SERVER_PROTOCOL_20261030_A'
_phase='ENTRY'


def need(ok):
    if not ok:raise RuntimeError('SOURCE_PROTOCOL_REFUSED')


class AuditFence:
    """Guard pure composition after imports; no OS capability is substituted."""
    def __init__(self):self.active=False;self.denied=[]
    def __call__(self,event,args):
        if not self.active:return
        denied=(event.startswith(('ctypes.dlopen','ctypes.dlsym','subprocess.','socket.','os.exec','os.spawn'))
            or event in ('os.system','os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink',
                         'os.chmod','os.chown','os.truncate','os.putenv','os.unsetenv'))
        if event=='open':
            mode=args[1];flags=args[2]
            denied=bool((type(mode) is str and any(c in mode for c in 'wax+'))
                or (type(flags) is int and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        if denied:
            self.denied.append(event)
            raise RuntimeError('PURE_PROTOCOL_OS_OPERATION_REFUSED')


def compile_sources(root):
    files=sorted(set((root/'src/parkweave').rglob('*.py')) |
                 set((root/'scripts/windows_portable').glob('*.py')) |
                 set((root/'scripts/windows').glob('*.py')))
    need(0<len(files)<=1600);digest=sha256();total=0
    for path in files:
        need(path.is_file() and not path.is_symlink() and path.stat().st_size<=2*1024*1024)
        raw=path.read_bytes();total+=len(raw);need(total<=32*1024*1024)
        name=path.relative_to(root).as_posix()
        compile(raw,name,'exec')  # No imports, execution or bytecode files.
        digest.update(name.encode()+b'\0'+sha256(raw).digest())
    return dict(files=len(files),bytes=total,sha256=digest.hexdigest(),bytecode_written=False)


def composition(root):
    global _phase
    _phase='PINNED_DEPENDENCY_IMPORTS'
    # Pinned third-party extension imports are ordinary dependency loading,
    # separate from product activation. First product imports are fenced too.
    import psycopg
    from pydantic import BaseModel
    fence=AuditFence();sys.addaudithook(fence);fence.active=True
    try:
        _phase='FENCED_PRODUCT_IMPORTS'
        from scripts.windows import lifecycle
        from scripts.windows_portable import payload,entry
        from scripts.windows_portable.native_composition import compose_native_local_preparation
        from scripts.windows_portable.endpoint_plan import PlanMode,EndpointRequest
        from scripts.windows_portable.native_runtime_staging import RuntimeSource
        from scripts.windows_portable.fixed_windows_journal import require_fixed_native_acceptance
        from scripts.windows_portable.directories import LeaseRefused
        from scripts.windows_portable.native_acceptance_contract import Area,requirement
        from scripts.windows_portable.native_preparation_sessions import NativePreparationSessionProvider
        _phase='PURE_FACTORY_CONSTRUCTION'
        # A plainly synthetic manifest for syntax/port binding only: no file
        # presence, package compatibility or trusted lease is inferred from it.
        raw=json.dumps(dict(schema=payload.SCHEMA,status='INITIALIZATION_NOT_ENABLED',source_commit=os.environ['PW_PROTOCOL_SHA'],
            files={'app/source-protocol.txt':dict(bytes=0,sha256=sha256(b'').hexdigest())}),separators=(',',':')).encode()
        runtime=dict(source_commit=os.environ['PW_PROTOCOL_SHA'],manifest_sha256=sha256(raw).hexdigest())
        source=RuntimeSource(str(root),raw)
        pins=dict(initdb_sha256='a'*64,initdb_size=1,postgres_sha256='b'*64,postgres_size=1,
                  python_sha256='c'*64,python_size=1,challenge='d'*32)
        new=compose_native_local_preparation(base=str(root),mode=PlanMode.NEW,request=EndpointRequest(55431,58761),runtime=runtime,**pins)
        reopened=compose_native_local_preparation(base=str(root),mode=PlanMode.REOPEN,request=None,runtime=runtime,payload_source=source,**pins)
        for invocation in (new,reopened):
            security=invocation.security.security;provider=invocation.security.provider
            need(type(provider) is NativePreparationSessionProvider and provider.native_acceptance is False
                 and invocation.native_acceptance is False and security.native_acceptance is False
                 and invocation.processes.endpoint_source is security
                 and invocation.processes.cluster.prerequisites.security is security
                 and invocation.processes.session_provider is provider
                 and security.lease is None and security.store is None and provider._identities is None)
        _phase='PURE_REOPEN_BINDING'
        reopened.security.require_runtime_support(reopened.controller.database,reopened.processes)
        need(reopened.security.provider.security is reopened.security.security)
        _phase='OWNER_REFUSAL'
        try:new.create(str(root/'not-created'),lambda _:need(False))
        except lifecycle.BoundaryError as error:need(error.parkweave_lifecycle_reason=='OWNER_MUTATION_PAUSED')
        else:need(False)
        _phase='FIXED_REFUSAL'
        try:require_fixed_native_acceptance()
        except LeaseRefused as error:need(str(error)==requirement(Area.FIXED_JOURNAL).reason)
        else:need(False)
        _phase='ENTRY_SELECTION'
        need(entry.choose_action(argparse.Namespace(action='launch',instance=root/'existing'),lambda _:need(False))=='reopen')
        # Loader inspect is intentionally NOT called. Verify the original
        # unconditional post-inspect refusal structurally, not with a fake lease.
        _phase='LOADER_AST_ONLY'
        tree=ast.parse((root/'scripts/windows_portable/runtime_payload.py').read_bytes())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='require_for_cluster')
        expected=ast.parse('self.inspect(lease, deadline)\nfrom .native_acceptance_contract import Area,requirement\nraise RuntimePayloadRefused(requirement(Area.LOADER).reason)').body
        need(ast.dump(ast.Module(body=method.body,type_ignores=[]))==ast.dump(ast.Module(body=expected,type_ignores=[]))
             and requirement(Area.LOADER).reason=='NATIVE_RUNTIME_LOADING_NOT_ACCEPTED')
        need(not fence.denied and new.security.provider._identities is None and reopened.security.provider._identities is None)
        return dict(factory='PURE_NEW_AND_REOPEN_COMPOSITION_PASSED',provider='REOPEN_MEMORY_BINDING_ONLY_PASSED',
            owner_gate='ORIGINAL_REFUSAL_OBSERVED',fixed_gate='ORIGINAL_REFUSAL_OBSERVED',
            loader_gate='POST_INSPECT_REFUSAL_AST_ONLY_NOT_INVOKED',entry='PYTHON_COMPILED_EXISTING_SELECTION_ONLY',
            synthetic_manifest_not_payload=True,product_imports_fenced=True,denied_operations=len(fence.denied),
            protected_storage='NOT_INVOKED',dpapi='NOT_INVOKED',identities_created=False)
    finally:fence.active=False


def main(argv=None):
    global _phase
    _phase='CONTEXT'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-protocol',action='store_true');args=parser.parse_args(argv)
    report=dict(scope='WINDOWS_SERVER_2025_SOURCE_PROTOCOL_NOT_WIN11_ACCEPTANCE',
        activation_allowed=False,usable_product=False,native_acceptance='NOT_ACCEPTED')
    if not args.run_protocol:print(json.dumps(dict(report,status='NOT_RUN')));return 2
    if sys.platform!='win32' or sys.version_info[:2]!=(3,12) or ctypes.sizeof(ctypes.c_void_p)!=8:
        print(json.dumps(dict(report,status='NATIVE_SERVER_REQUIRED')));return 2
    try:
        version=sys.getwindowsversion()
        need(version.build>=26100 and version.product_type in (2,3) and sysconfig.get_platform()=='win-amd64'
             and os.environ.get('GITHUB_REPOSITORY')=='T1doo/ParkWeave'
             and os.environ.get('GITHUB_REF')==REF and os.environ.get('GITHUB_EVENT_NAME')=='push'
             and os.environ.get('PW_PROTOCOL_BEFORE')==BEFORE and os.environ.get('PW_PROTOCOL_ATTEMPT')=='1'
             and os.environ.get('PW_PROTOCOL_PUBLIC')=='true'
             and re.fullmatch('[a-f0-9]{40}',os.environ.get('PW_PROTOCOL_SHA',''))
             and os.environ['PW_PROTOCOL_SHA']==os.environ.get('GITHUB_SHA'))
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
        need(event.get('before')==BEFORE and event.get('head_commit',{}).get('message')==MARKER
             and event.get('head_commit',{}).get('id')==os.environ['PW_PROTOCOL_SHA']
             and event.get('repository',{}).get('private') is False
             and event.get('repository',{}).get('full_name')=='T1doo/ParkWeave')
        _phase='PINNED_DEPENDENCIES'
        versions={name:importlib.metadata.version(name) for name in ('psycopg','psycopg-binary','pydantic','pydantic_core')}
        need(versions['psycopg']==versions['psycopg-binary']=='3.3.6' and versions['pydantic']=='2.13.5')
        root=Path(__file__).resolve().parents[2];started=time.monotonic()
        _phase='SOURCE_COMPILE'
        compiled=compile_sources(root);observed=composition(root)
        need(time.monotonic()-started<45)
        report.update(status='SOURCE_PROTOCOL_PASSED',source_sha=os.environ['PW_PROTOCOL_SHA'],
            platform=dict(build=version.build,product_type=version.product_type,architecture='AMD64'),
            dependencies=versions,compiled=compiled,observed=observed)
        print(json.dumps(report,separators=(',',':')));return 0
    except Exception as error:
        print(json.dumps(dict(report,status='FAIL',phase=_phase,error_type=type(error).__name__)));return 1


if __name__=='__main__':raise SystemExit(main())
