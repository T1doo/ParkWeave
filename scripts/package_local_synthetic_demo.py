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
         'scripts/package_local_synthetic_demo.py', 'docs/demo/LocalSyntheticExperience.md',
         'docs/demo/LocalSyntheticWalk.html', 'docs/F2/LocalSyntheticDemoContract-20261017.md')


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
    bundle = dict(schema='parkweave-local-synthetic-experience-bundle/1', source_commit=full,
                  profile='LOCAL_SYNTHETIC_DEMO', format='SOURCE_ONLY_NO_THIRD_PARTY_DEPENDENCIES',
                  runtime_inputs_included=False, business_operations_performed=False,
                  windows_formal_at='NOT_RUN', real_business='NOT_RUN', tracked_source_files=manifest)
    payload['BUNDLE.json'] = (json.dumps(bundle, ensure_ascii=False, indent=2) + '\n').encode()
    payload['START_HERE.txt'] = (
        'ParkWeave LOCAL_SYNTHETIC_DEMO\nSource commit: ' + full + '\n\n'
        '先打开 docs/demo/LocalSyntheticWalk.html，再看 LocalSyntheticExperience.md。\n'
        '固定源码包，不含第三方依赖、数据库、私有输入、会话或业务授权。\n'
        '从包根目录以既有批准的 Python 3.12 运行：\n'
        '  python scripts/demo_preflight.py --local-synthetic --json\n'
        '缺项返回 2，停止；不 seed/migrate，不补身份/Grant/assignment/批准。\n'
        '当前交付环境四项运行配置均缺失，实际业务未启动。\n'
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
