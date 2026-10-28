"""Private embedded-Python entry; integrity precedes original readiness only."""
import importlib.util
import json
from pathlib import Path
import sys
import argparse
from hashlib import sha256

if __package__:
    from .payload import MANIFEST, PayloadRefused, require, verify_directory
else:
    from payload import MANIFEST, PayloadRefused, require, verify_directory


def readiness(root):
    path = root / 'app/scripts/windows/lifecycle.py'
    spec = importlib.util.spec_from_file_location('_parkweave_original_windows_lifecycle', path)
    require(spec is not None and spec.loader is not None, 'READINESS_MODULE')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.setup_readiness()  # Never main/doctor/setup, DDL or ACL setters.
    require(isinstance(result, dict) and result.get('status') in ('READY', 'BLOCKED'), 'READINESS_RESULT')
    return result


def native_invocation(payload_root,manifest,instance,mode,*,manifest_raw,database_port=None,api_port=None,enrollment=None):
    """Wire verified payload pins into the concrete runtime, without OS actions.

    The held-handle installer rechecks the same raw manifest and every byte.
    Native acceptance gates still precede all instance operations.
    """
    from scripts.windows_portable.native_composition import compose_native_local_preparation
    from scripts.windows_portable.endpoint_plan import PlanMode,EndpointRequest
    from scripts.windows_portable.native_runtime_staging import RuntimeSource
    import secrets
    require(type(mode) is PlanMode,'EXPLICIT_NATIVE_MODE')
    request=EndpointRequest(database_port,api_port) if mode is PlanMode.NEW else None
    pins={}
    for name,relative in (('initdb','runtime/postgresql/bin/initdb.exe'),
                          ('postgres','runtime/postgresql/bin/postgres.exe'),
                          ('python','runtime/python/python.exe')):
        row=manifest['files'][relative]
        pins[name+'_sha256']=row['sha256'];pins[name+'_size']=row['bytes']
    return compose_native_local_preparation(base=str(instance.parent),mode=mode,request=request,
        runtime=dict(source_commit=manifest['source_commit'],
            manifest_sha256=sha256(manifest_raw).hexdigest()),
        payload_source=RuntimeSource(str(payload_root),manifest_raw),
        enrollment=enrollment,
        challenge=secrets.token_hex(32),**pins)


def main():
    parser=argparse.ArgumentParser(description='ParkWeave 私有运行时校验与本地入口')
    parser.add_argument('--action',choices=('status','new','reopen'),default='status')
    parser.add_argument('--instance',type=Path)
    parser.add_argument('--database-port',type=int)
    parser.add_argument('--api-port',type=int)
    args=parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        require(sys.platform == 'win32' and sys.maxsize > 2**32 and sys.flags.isolated, 'NATIVE_EMBEDDED_PYTHON_REQUIRED')
        with (root / MANIFEST).open('rb') as manifest_file:
            manifest_raw = manifest_file.read(4*1024*1024+1)
        manifest = verify_directory(root,manifest_raw=manifest_raw)
        require(Path(sys.executable).resolve() == root / 'runtime/python/python.exe', 'PRIVATE_INTERPRETER_REQUIRED')
        gate = readiness(root)
        if args.action=='status' or gate['status']!='READY':
            print(json.dumps(dict(payload='INTEGRITY_VERIFIED', source_commit=manifest['source_commit'],
                initialization='NOT_STARTED' if gate['status']=='READY' else 'BLOCKED',readiness=gate,
                usable_product=False,native_factory='IMPLEMENTED_NOT_NATIVE_ACCEPTED'),ensure_ascii=False))
            return 0 if args.action=='status' and gate['status']=='READY' else 2
        require(args.instance is not None and args.instance.is_absolute(),'EXPLICIT_PRIVATE_INSTANCE_REQUIRED')
        from scripts.windows_portable.endpoint_plan import PlanMode
        mode=PlanMode.NEW if args.action=='new' else PlanMode.REOPEN
        from scripts.windows_portable.native_web_login import prompt_enrollment
        enrollment=prompt_enrollment() if mode is PlanMode.NEW else None
        invocation=native_invocation(root,manifest,args.instance,mode,manifest_raw=manifest_raw,
            database_port=args.database_port,api_port=args.api_port,enrollment=enrollment)
        def use(workspace):
            print('LOCAL_SYNTHETIC_RUNTIME: http://127.0.0.1:'+str(workspace.application.port),flush=True)
            try:input('按回车停止本次私有运行时。')
            except (KeyboardInterrupt,EOFError):pass
        result=(invocation.create if mode is PlanMode.NEW else invocation.reopen)(str(args.instance),use)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as error:
        reason = str(error) if type(error) is PayloadRefused else type(error).__name__
        print('ParkWeave 未启动：' + reason, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
