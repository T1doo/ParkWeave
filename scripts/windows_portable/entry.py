"""Private embedded-Python entry; integrity precedes original readiness only."""
import importlib.util
import json
from pathlib import Path
import sys
import argparse
import stat
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


def verified_payload():
    """Native interpreter and immutable payload check, before launch prompts."""
    root = Path(__file__).resolve().parents[1]
    require(sys.platform == 'win32' and sys.maxsize > 2**32 and sys.flags.isolated,
            'NATIVE_EMBEDDED_PYTHON_REQUIRED')
    with (root / MANIFEST).open('rb') as manifest_file:
        raw = manifest_file.read(4*1024*1024+1)
    manifest = verify_directory(root,manifest_raw=raw)
    require(Path(sys.executable).resolve() == root / 'runtime/python/python.exe',
            'PRIVATE_INTERPRETER_REQUIRED')
    return root, manifest, raw


def instance_hint(instance, *, fresh):
    """Read-only user-error check; held native acquisition remains authority."""
    require(instance is not None and instance.is_absolute(),'EXPLICIT_PRIVATE_INSTANCE_REQUIRED')
    try:
        info = instance.lstat()
    except FileNotFoundError:
        require(fresh,'INSTALLATION_MISSING_USE_EXPLICIT_NEW')
        return
    require(not fresh,'INSTANCE_EXISTS_NO_REINITIALIZATION')
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
            and not getattr(info,'st_file_attributes',0) & 0x400,'INSTANCE_DIRECTORY_REQUIRED')


def choose_action(args, read):
    if args.action != 'launch':return args.action
    if args.instance is not None:return 'reopen'  # Existing only, never new on failure.
    print('园合 · 本地资料工作台\n1 重开已有安装\n2 首次新建安装\n3 只读查看准入状态\n0 退出')
    choice = read('请选择：').strip()
    require(choice in ('0','1','2','3'),'EXPLICIT_LAUNCH_CHOICE_REQUIRED')
    return {'0':'cancel','1':'reopen','2':'new','3':'status'}[choice]


def public_failure_reason(error, *, verified=False):
    # Error reporting must never load app code, especially when integrity fails.
    fallback = str(error) if type(error) is PayloadRefused else type(error).__name__
    if not verified:return fallback
    known = {'OWNER_MUTATION_PAUSED','WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED',
             'NATIVE_RUNTIME_LOADING_NOT_ACCEPTED','SYSTEM_CRT_PREREQUISITE_UNVERIFIED'}
    pending = [error]; seen = set()
    module = sys.modules.get('scripts.windows_portable.controller')
    failure_type = getattr(module,'ControlFailure',None) if module is not None else None
    if failure_type is not None and type(error) is failure_type:
        pending.extend(error.causes[:16])
    for _ in range(64):
        if not pending:break
        cause = pending.pop()
        if cause is None or id(cause) in seen:continue
        seen.add(id(cause))
        reason = getattr(cause,'parkweave_lifecycle_reason',None)
        if type(reason) is str and reason in known:return reason
        if str(cause) in known:return str(cause)
        pending.extend((cause.__cause__,cause.__context__))
        if isinstance(cause,BaseExceptionGroup):pending.extend(cause.exceptions[:16])
    return fallback


def main(argv=None, *, read=None, use_workspace=None, enroll=None):
    parser=argparse.ArgumentParser(description='ParkWeave 本地安装与资料工作台')
    parser.add_argument('--action',choices=('launch','status','new','reopen'),default='launch')
    parser.add_argument('--instance',type=Path)
    parser.add_argument('--database-port',type=int)
    parser.add_argument('--api-port',type=int)
    args=parser.parse_args(argv)
    read = input if read is None else read
    verified = False
    try:
        root,manifest,manifest_raw = verified_payload()
        verified = True
        interactive = args.action == 'launch'
        action = choose_action(args,read)
        if action == 'cancel':return 0
        # Only NEW and explicit status query the historical new-setup pause.
        # REOPEN reaches its original fixed-journal and loader gates unchanged.
        if action in ('status','new'):
            gate = readiness(root)
            if action == 'status' or gate['status'] != 'READY':
                print(json.dumps(dict(payload='INTEGRITY_VERIFIED',source_commit=manifest['source_commit'],
                    requested_action=action,initialization='NOT_STARTED' if gate['status']=='READY' else 'BLOCKED',
                    readiness=gate,usable_product=False,native_factory='IMPLEMENTED_NOT_NATIVE_ACCEPTED'),ensure_ascii=False))
                return 0 if action=='status' and gate['status']=='READY' else 2
        if interactive and args.instance is None:
            args.instance = Path(read('新安装目录（尚不存在）全路径：' if action=='new' else '已有安装目录全路径：').strip())
        instance_hint(args.instance,fresh=action=='new')
        if action == 'new':
            if interactive:
                if args.database_port is None:args.database_port=int(read('新建数据库回环端口：'))
                if args.api_port is None:args.api_port=int(read('新建工作台回环端口：'))
            require(all(type(p) is int and 1 <= p <= 65535 for p in (args.database_port,args.api_port))
                    and args.database_port != args.api_port,'TWO_DISTINCT_EXPLICIT_PORTS_REQUIRED')
        else:
            require(args.database_port is None and args.api_port is None,'REOPEN_USES_PROTECTED_EXISTING_PORTS')
        from scripts.windows_portable.endpoint_plan import PlanMode
        from scripts.windows_portable.native_web_login import prompt_enrollment
        mode=PlanMode.NEW if action=='new' else PlanMode.REOPEN
        enrollment=(enroll or prompt_enrollment)() if action=='new' else None
        invocation=native_invocation(root,manifest,args.instance,mode,manifest_raw=manifest_raw,
            database_port=args.database_port,api_port=args.api_port,enrollment=enrollment)
        def use(workspace):
            print('工作台已由本次运行校验。请在浏览器打开 http://127.0.0.1:'+str(workspace.application.port),flush=True)
            try:read('按回车正常停止本次私有运行时：')
            except (KeyboardInterrupt,EOFError):pass
        callback = use if use_workspace is None else lambda workspace:use_workspace(workspace,invocation)
        result=(invocation.create if action=='new' else invocation.reopen)(str(args.instance),callback)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (KeyboardInterrupt,EOFError):
        return 2  # Prompt interrupted; never choose a mode or restart on behalf of the user.
    except Exception as error:
        reason = public_failure_reason(error,verified=verified)
        if reason=='SYSTEM_CRT_PREREQUISITE_UNVERIFIED':
            print('已有官方 x64 系统运行库缺失或未能核验。请由安装者核对微软说明；不会自动安装或修改系统：\n'
                  'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170',file=sys.stderr)
        print('ParkWeave 未启动或未正常结束：'+reason+'；保留现有状态，没有自动初始化或重试。',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
