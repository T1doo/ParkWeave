"""Private embedded-Python entry; integrity precedes original readiness only."""
import importlib.util
import json
from pathlib import Path
import sys

if __package__:
    from .payload import PayloadRefused, require, verify_directory
else:
    from payload import PayloadRefused, require, verify_directory


def readiness(root):
    path = root / 'app/scripts/windows/lifecycle.py'
    spec = importlib.util.spec_from_file_location('_parkweave_original_windows_lifecycle', path)
    require(spec is not None and spec.loader is not None, 'READINESS_MODULE')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.setup_readiness()  # Never main/doctor/setup, DDL or ACL setters.
    require(isinstance(result, dict) and result.get('status') in ('READY', 'BLOCKED'), 'READINESS_RESULT')
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        require(sys.platform == 'win32' and sys.maxsize > 2**32 and sys.flags.isolated, 'NATIVE_EMBEDDED_PYTHON_REQUIRED')
        manifest = verify_directory(root)
        require(Path(sys.executable).resolve() == root / 'runtime/python/python.exe', 'PRIVATE_INTERPRETER_REQUIRED')
        gate = readiness(root)
        print(json.dumps(dict(payload='INTEGRITY_VERIFIED', source_commit=manifest['source_commit'],
            initialization='BLOCKED', readiness=gate, usable_product=False), ensure_ascii=False))
        print('当前是封装校验候选，尚不能初始化或办理；不会安装系统依赖、修改权限或连接已有数据库。')
        if gate['status'] == 'READY':
            print('PRIVATE_INSTANCE_BOOTSTRAP_NOT_IMPLEMENTED')
        return 2
    except Exception as error:
        reason = str(error) if type(error) is PayloadRefused else type(error).__name__
        print('ParkWeave 未启动：' + reason, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
