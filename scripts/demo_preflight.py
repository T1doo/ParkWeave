"""Offline, read-only inventory for the user demo; never a readiness authority."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys

BASELINE = '9ab3c06567ec4d3ff2bcd8152008ba46c39089a5'
ASSETS = (
    'docs/demo/AcceptanceWalk.html',
    'docs/demo/README.md',
    'scripts/linux_fixture_server.py',
    'scripts/template_cold_start_browser_smoke.py',
    'scripts/dispatch_recovery_browser_smoke.py',
    'scripts/material_reuse_browser_smoke.py',
    'src/parkweave/web.html',
    'pyproject.toml',
)
# Inventory only: do not import app, read credentials, inspect runtime or connect.
DEPENDENCIES = ('fastapi', 'uvicorn', 'psycopg', 'pydantic', 'httpx', 'pgserver')
LOCAL_ASSETS = ('docs/demo/LocalSyntheticExperience.md', 'docs/demo/LocalSyntheticWalk.html',
                'docs/F2/LocalSyntheticDemoContract-20261017.md',
                'scripts/demo_preflight.py', 'src/parkweave/web.html', 'pyproject.toml')
LOCAL_DEPENDENCIES = {'fastapi': '0.142.2', 'uvicorn': '0.54.0', 'psycopg': '3.3.6',
                      'psycopg-binary': '3.3.6', 'pydantic': '2.13.5', 'httpx': '0.28.1'}
INPUTS = ('PARKWEAVE_DSN', 'PARKWEAVE_MODE', 'PARKWEAVE_SERVICE_PROFILE',
          'PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG')
OTHER_PROVIDERS = ('PARKWEAVE_RUNTIME_READ_CONFIG', 'PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG',
                   'PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG')


def _readonly_store_type(base):
    """A probe-only store. Every connection is protected before any catalog read."""
    class ReadOnlyStore(base):
        def connect(self):
            c = super().connect()
            try:
                c.execute('SET TRANSACTION READ ONLY')
                c.execute("SET LOCAL statement_timeout = '3000ms'")
                c.execute("SET LOCAL lock_timeout = '1000ms'")
                row = c.execute("""SELECT
                    EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN (current_user, session_user)
                        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
                    OR EXISTS (SELECT 1 FROM pg_database WHERE datname=current_database()
                        AND (pg_has_role(current_user, datdba, 'USAGE')
                             OR pg_has_role(session_user, datdba, 'USAGE')))
                    OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname='public'
                        AND (pg_has_role(current_user, c.relowner, 'USAGE')
                             OR pg_has_role(session_user, c.relowner, 'USAGE')))
                    AS privileged"""
                ).fetchone()
                if not row or row['privileged'] is not False:
                    raise ValueError('application role required')
                return c
            except Exception:
                c.close()
                raise
    return ReadOnlyStore


def _probe_existing_inputs(root, environ):
    # Only the explicitly requested probe imports production code or reads values.
    sys.path.insert(0, str(root / 'src'))
    try:
        from parkweave.store import Store
        from parkweave.local_synthetic_demo import configure
        store = _readonly_store_type(Store)(environ['PARKWEAVE_DSN'], mode='LOCAL')
        demo = configure(store, environ['PARKWEAVE_SERVICE_PROFILE'],
                         environ['PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG'])
        if demo is None:
            raise ValueError('explicit demo required')
    finally:
        sys.path.pop(0)


def inspect_local_demo(root, *, check_existing=False, environ=None, version=None,
                       distribution_version=None, probe=None):
    environ = os.environ if environ is None else environ
    version = sys.version_info if version is None else version
    distribution_version = distribution_version or importlib.metadata.version
    deps = []
    for name, expected in LOCAL_DEPENDENCIES.items():
        try:
            installed = distribution_version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        deps.append(dict(name=name, expected_version=expected, installed_version=installed,
                         matches=installed == expected))
    missing_assets = [name for name in LOCAL_ASSETS if not (root / name).is_file()]
    missing_inputs = [name for name in INPUTS if not environ.get(name)]
    profile_ok = (environ.get('PARKWEAVE_MODE') == 'LOCAL'
                  and environ.get('PARKWEAVE_SERVICE_PROFILE') == 'LOCAL_SYNTHETIC_DEMO')
    mixed = any(environ.get(name) for name in OTHER_PROVIDERS)
    complete = tuple(version[:2]) == (3, 12) and not missing_assets and all(d['matches'] for d in deps)
    status = ('BLOCKED_MISSING_EXISTING_INPUTS' if missing_inputs else
              'BLOCKED_PROFILE' if not profile_ok or mixed else
              'BLOCKED_INVENTORY' if not complete else 'INVENTORY_ONLY_INPUT_VALUES_NOT_VALIDATED')
    database = 'NOT_PROBED'
    if check_existing and complete and not missing_inputs and profile_ok and not mixed:
        try:
            (probe or _probe_existing_inputs)(root, environ)
        except Exception:
            # Errors can contain private DSNs, file paths or input contents. Never echo them.
            status, database = 'BLOCKED_EXISTING_INPUT_VALIDATION', 'READ_ONLY_PROBE_REFUSED'
        else:
            status, database = 'CURRENT_DEMO_INPUT_BINDINGS_VALIDATED_READ_ONLY', 'READ_ONLY_BINDINGS_VALIDATED'
    return dict(schema='parkweave-local-demo-preflight/1', scope='LOCAL_SYNTHETIC_DEMO',
                status=status, inventory_complete=complete, python_3_12=tuple(version[:2]) == (3, 12),
                missing_assets=missing_assets, dependencies=deps, missing_input_names=missing_inputs,
                exact_profile=profile_ok, mixed_provider_configuration=mixed,
                explicit_read_only_probe=check_existing, database=database,
                sessions='NOT_CHECKED', grants='NOT_CHECKED', run_assignment='NOT_CHECKED',
                business_ready=False, runtime='NOT_STARTED', model_calls_by_this_tool=0,
                guide='docs/demo/LocalSyntheticWalk.html')


def inspect_demo(root: Path, version=None, distribution_version=None):
    version = sys.version_info if version is None else version
    distribution_version = distribution_version or importlib.metadata.version
    dependencies = []
    for name in DEPENDENCIES:
        try:
            installed = distribution_version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        dependencies.append({'name': name, 'installed_version': installed})
    files = [{'path': name, 'present': (root / name).is_file()} for name in ASSETS]
    python_ok = tuple(version[:2]) == (3, 12)
    missing = [item['path'] for item in files if not item['present']]
    missing_dependencies = [item['name'] for item in dependencies if item['installed_version'] is None]
    return {
        'schema': 'parkweave-demo-inventory/1',
        'scope': 'OFFLINE_INVENTORY_ONLY',
        'reference_baseline': BASELINE,
        'python_3_12': python_ok,
        'assets': files,
        'dependencies': dependencies,
        'inventory_complete': python_ok and not missing and not missing_dependencies,
        'missing_assets': missing,
        'missing_dependencies': missing_dependencies,
        'runtime': 'NOT_PROBED',
        'database': 'NOT_PROBED',
        'authorization': 'NOT_PROBED',
        'cold_case_to_receipt': 'BLOCKED_UNLESS_EXISTING_AUTHORIZED_RUN_ASSIGNMENT',
        'template_publication': 'ISOLATED_CANDIDATE_ONLY_NOT_FORMALLY_ENABLED',
        'windows_native': 'NOT_RUN',
        'formal_at_ex': 'NOT_RUN',
        'model_calls_by_this_tool': 0,
        'guide': 'docs/demo/AcceptanceWalk.html',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='默认离线盘点；仅显式 --local-synthetic --check-existing-inputs 可只读校验既有数据库绑定。不读取会话、不启动或安装服务。')
    parser.add_argument('--json', action='store_true', help='输出无凭据JSON清单')
    parser.add_argument('--local-synthetic', action='store_true', help='当前合成体验包：盘点精确依赖与既有配置缺项')
    parser.add_argument('--check-existing-inputs', action='store_true', help='显式只读校验既有合成资料绑定；不校验会话或授权')
    args = parser.parse_args(argv)
    if args.check_existing_inputs and not args.local_synthetic:
        parser.error('--check-existing-inputs requires --local-synthetic')
    if args.local_synthetic:
        report = inspect_local_demo(Path(__file__).resolve().parents[1], check_existing=args.check_existing_inputs)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['status'] in ('INVENTORY_ONLY_INPUT_VALUES_NOT_VALIDATED',
                                        'CURRENT_DEMO_INPUT_BINDINGS_VALIDATED_READ_ONLY') else 2
    # Anchor to this script, never infer another project from the working directory.
    report = inspect_demo(Path(__file__).resolve().parents[1])
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('ParkWeave 离线体验预检（仅盘点，不证明服务可运行或业务权限）')
        print('Python 3.12：' + ('已检测到' if report['python_3_12'] else '未满足'))
        print('缺少演示资产：' + ('、'.join(report['missing_assets']) or '无'))
        print('缺少当前解释器依赖：' + ('、'.join(report['missing_dependencies']) or '无'))
        print('运行、数据库、身份授权：未探测；依赖版本未作兼容性验证。')
        print('新Case回执：须有该Run既有合法assignment；本工具不准备授权。')
        print('模板正式发布未启用；Windows/正式AT与EX未运行；本工具模型调用0。')
        print('普通用户：用浏览器打开 docs/demo/AcceptanceWalk.html，按卡逐项核对。')
    return 0 if report['inventory_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
