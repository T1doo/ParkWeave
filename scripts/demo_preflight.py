"""Offline, read-only inventory for the user demo; never a readiness authority."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
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
    parser = argparse.ArgumentParser(description='离线演示资产盘点；不读取会话、不连接数据库、不启动或安装服务。')
    parser.add_argument('--json', action='store_true', help='输出无凭据JSON清单')
    args = parser.parse_args(argv)
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
