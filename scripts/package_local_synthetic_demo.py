"""Build a reproducible source-only experience ZIP from one existing Git commit.

Stdlib only. No checkout, installation, runtime inputs, app import or database.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

PATHS = ('src/parkweave', 'pyproject.toml', 'scripts/demo_preflight.py',
         'scripts/package_local_synthetic_demo.py', 'scripts/material_only_demo.py',
         'scripts/linux_fixture_server.py', 'scripts/ordinary_synthetic_demo.py',
         'scripts/local_demo_inputs.py', 'requirements-linux-evidence.txt',
         'docs/demo/OrdinarySyntheticDemo.md', 'docs/demo/LocalSyntheticExperience.md',
         'docs/demo/MaterialOnlyDemo.md', 'docs/demo/LocalSyntheticWalk.html',
         'docs/F2/LocalSyntheticDemoContract-20261017.md',
         'docs/F2/OriginalCollaborationDOMValidation-20261018.md',
         'docs/F2/MaterialReuseDOMValidation-20261018.md',
         'docs/F2/MaterialOnlyDemoValidation-20261018.md')


def build(root, commit, output):
    full = subprocess.check_output(['git', 'rev-parse', '--verify', commit + '^{commit}'],
                                   cwd=root, text=True).strip()
    if commit != full or len(full) != 40:
        raise ValueError('existing full commit SHA required')
    raw = subprocess.check_output(['git', 'archive', '--format=tar', full, '--', *PATHS], cwd=root)
    payload = {}
    with tarfile.open(fileobj=BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:
                raise ValueError('regular allowlisted source files required')
            payload[member.name] = archive.extractfile(member).read()
    for name in PATHS[1:]:
        if name not in payload:
            raise ValueError('required source asset missing')
    if not payload or not any(name.startswith('src/parkweave/') for name in payload):
        raise ValueError('source package missing')
    manifest = {name: dict(bytes=len(data), sha256=sha256(data).hexdigest())
                for name, data in sorted(payload.items())}
    src_tree = subprocess.check_output(['git', 'rev-parse', full + ':src'], cwd=root, text=True).strip()
    bundle = dict(schema='parkweave-local-synthetic-experience-bundle/2', source_commit=full,
                  src_tree=src_tree, delivery_baseline='5842312391dce574a25087ed974308ada1798623',
                  entry_scopes=['ORDINARY_SYNTHETIC', 'MATERIAL_ONLY_SYNTHETIC', 'LOCAL_SYNTHETIC_DEMO'],
                  format='COMPLETE_APPLICATION_SOURCE_NO_THIRD_PARTY_DEPENDENCIES',
                  runtime_inputs_included=False, business_operations_performed=False,
                  material_launcher_requires_git_checkout=True,
                  ordinary_launcher_requires_git_checkout=False,
                  ordinary_state_location='OWNED_PRIVATE_TMP_ONLY_NOT_PERMANENT_STORAGE',
                  ordinary_stop_preserves_state=True, ordinary_runtime_by_packaging='NOT_RUN',
                  historical_browser_reports_included=True, current_sandbox_browser='NOT_CHECKED_BY_PACKAGING',
                  fresh_install_fixture_free_at35='NOT_RUN',
                  windows_formal_at='NOT_RUN', real_business='NOT_RUN', tracked_source_files=manifest)
    payload['BUNDLE.json'] = (json.dumps(bundle, ensure_ascii=False, indent=2) + '\n').encode()
    payload['START_HERE.txt'] = (
        'ParkWeave 合成演示代码交付\nSource commit: ' + full + '\n\n'
        '普通首办入口：先读 docs/demo/OrdinarySyntheticDemo.md。\n'
        '本包收齐普通启动器与输入辅助源码；无需 .git，但仍需既有非root Linux、\n'
        'Python3.12及已准备依赖（含pgserver==0.1.4，版本清单为requirements-linux-evidence.txt）。\n'
        '源码包不会下载或安装依赖，不是独立wheel/Windows安装器。\n'
        '在解压根目录、原已准备的Python环境，先看帮助（不启动服务）：\n'
        '  python -B -m scripts.ordinary_synthetic_demo --help\n'
        '首次全新合成实例才运行一次：\n'
        '  python -B -m scripts.ordinary_synthetic_demo setup --with-local-catalog --with-local-resource-approval\n'
        '保存实际输出的state_dir；把下两处示例路径同时替换为该目录：\n'
        '  python -B -m scripts.ordinary_synthetic_demo serve --state-dir /tmp/parkweave-ordinary-demo-实际值 --local-demo-config /tmp/parkweave-ordinary-demo-实际值/local-demo/config.json --port 8765\n'
        '只打开serve输出的本机demo_url，选择同目录sessions.json，显式切换人物办理。\n'
        'Ctrl+C后保留数据和日志；退出重开只运行同一serve命令，不再setup。\n'
        '仍须同一源码内容、原目录和原权限；不搬库、不修改绑定、不续期或补权。\n'
        '数据在/tmp，系统/平台清理后可能丢失，不能称永久持久化；模拟目录原7天有效期不续。\n'
        '本次打包只做离线校验，未从解压包实际初始化/停启PG或人工安装验收。\n\n'
        '其他历史入口：LocalSyntheticExperience.md / LocalSyntheticWalk.html。\n'
        '包含完整产品运行源码、启动辅助源码与部分历史范围说明；更多证据另见仓库链接。\n'
        '不含第三方依赖、Git历史、数据库、私有输入、会话或业务授权。\n'
        '已有材料演示：在原 Git checkout 复用原私有目录，只运行 serve；不得重复 setup。\n'
        'material_only_demo 依赖 Git src树绑定，不能从无 .git 的解压目录重启原库。\n'
        '普通解压源码：已有合法 DSN/权限时按说明启动原 configured_app 和 worker。\n'
        '严格 LOCAL_SYNTHETIC_DEMO profile 另需 pack/journal，与材料演示分开。\n'
        '该 profile 可先以既有批准的 Python 3.12 从包根盘点：\n'
        '  python scripts/demo_preflight.py --local-synthetic --json\n'
        '缺项返回 2，停止；不 seed/migrate，不补身份/Grant/assignment/批准。\n'
        '旧材料 HTTP/重启和历史 Chromium P1–P5/材料复用属于各原版本，各有合成前置。\n'
        '打包不探测浏览器，不重试或降级沙箱。新安装零准备、同Case完整P1–P5再运行的\n'
        '无夹具正式AT35仍缺；完整F2/比赛交付、Windows正式AT和真实业务未完成。\n'
        'SHA256SUMS 覆盖除自身外所有载荷；ZIP 本身的 SHA256 随交付单提供。\n'
    ).encode()
    payload['Comparison.txt'] = (
        '两次 SYNTHETIC 体验空白核对表（不填会话、DSN 或私有输入）\n'
        '来源 commit: ' + full + '\n'
        '每件分别记：Run / Case / preparation；材料版本；专员核对、企业确认状态；\n'
        '材料文本文件名、下载时间、SHA256；Case核对包文件名/SHA256或未生成原因；停点。\n\n'
        'A 设备维护：\n\n\nB 员工培训：\n\n\n'
        '比较：编号分别不同 [ ] 内容分别独立 [ ] 刷新后重读 [ ]\n'
        '实际未完成项与拒绝：\n\nWindows正式AT、真实业务、AT35全部：本包未验。\n'
    ).encode()
    payload['SHA256SUMS'] = ''.join(sha256(data).hexdigest() + '  ' + name + '\n'
                                     for name, data in sorted(payload.items())).encode()
    # Exclusive create: preserve previous packages and failures, never overwrite.
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payload.items()):
                item = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                archive.writestr(item, data, compresslevel=9)
    return dict(source_commit=full, zip=output.name, bytes=output.stat().st_size,
                sha256=sha256(output.read_bytes()).hexdigest(), entries=len(payload),
                tracked_source_entries=len(manifest))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True, help='full existing source commit SHA')
    parser.add_argument('--output', required=True, type=Path, help='new ZIP path; parent must exist')
    args = parser.parse_args()
    result = build(Path(__file__).resolve().parents[1], args.commit, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
