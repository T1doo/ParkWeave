"""Append actual completed results and preserve preceding documentation bytes."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path('/workspace/ParkWeave')
r=root/'.runtime/resource-plan-approval-read'
target=root/'docs/F2/evidence/resource-plan-approval-read-20261017'
gate=json.loads((target/'gate.json').read_text())
f=json.loads((r/'freeze-v2.json').read_text())
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
assert gate['final']['unique']==143 and gate['final']['failure']==gate['final']['errors']==gate['final']['skipped']==0
seconds=gate['final']['seconds'];source=gate['source_sha']
report=root/'docs/F2/ResourcePlanApprovalRead-20261017.md'
body=report.read_text()
assert '## 最终冻结与验证' not in body
lines=['\n## 最终冻结与验证\n',f'最终源码冻结 `{source}`，720个源码/测试/脚本/配置输入SHA256零漂移，原7个权限/计划/资源算法及角色SQL逐字节未改。原db108到准入基线156b、再到本冻结的祖先关系已核对。原有{gate["inherited_archive_git_blobs_checked"]}个F2证据Git blob保持不变，字段修正只新增副本。\n',
f'六个完整相关模块 **143唯一用例全部PASS，0FAIL/ERROR/SKIP，JUnit {seconds:.3f}秒**。新增50个接口与6个实际Chromium/HTTP用例已包含其中；不叠加旧141、开发/补测或此前获准入427。最终运行未启用连接诊断选项，不重跑427或SIGINT。\n',
'| 完整模块 | 唯一用例 |\n| --- | ---: |']
for module,count in gate['per_module_unique'].items():lines.append(f'| `{module}` | {count} |')
lines.extend(['\n| 保留窗口 | testcase元素 | FAIL | ERROR | SKIP | JUnit秒 |\n| --- | ---: | ---: | ---: | ---: | ---: |'])
for window,counts in gate['windows'].items():
    lines.append(f'| {window} | {counts["testcase_elements"]} | {counts["failure"]} | {counts["errors"]} | {counts["skipped"]} | {counts["seconds"]:.3f} |')
lines.extend(['\n以上窗口各自保留，不相加；早期开发窗没有单独捕获调用元数据/准确源码SHA，未事后编造。final-v1为957ca923冻结，final-v2为上述5180冻结。\n',
f'[最终gate](evidence/resource-plan-approval-read-20261017/gate.json)、[完整JUnit](evidence/resource-plan-approval-read-20261017/final-v2.xml)、[原日志的脱敏副本](evidence/resource-plan-approval-read-20261017/final-v2.log)、[原件/公开件hash配对](evidence/resource-plan-approval-read-20261017/public-pairs.json)、[全部窗口及原因](evidence/resource-plan-approval-read-20261017/failure-ledger.json)、[冻结清单](evidence/resource-plan-approval-read-20261017/freeze-v2.json)。新归档{gate["public_pairs"]}对均核对原件未变与公开件hash；JSON/JSONL仅处理字符串值、保留schema键并严格拒绝重复键，JUnit节点/非message属性保持。旧错误副本保留，未默默覆盖。\n',
'本片仅完成本地合成边界下的已有资源方案批准只读契约，独立父线程审查仍待。交付使用普通开发分支提交与推送；最终交付SHA、实际远端和未提交差异于交付后写入私有 `.runtime/resource-plan-approval-read/delivery-verification.json` 并在最终回复给出，不在归档中预填尚未发生的远端结果。完整项目、真实业务、Windows/正式AT均未完成验收。\n'])
report.write_text(body+'\n'.join(lines))

intro=(f'2026-10-17 新增已有资源方案批准的独立只读契约及原资料页导航：精确核对原preparation/Case/Run、方案版本、动作/来源、批准主体和当前有效期/撤销，不创建或消费批准；与Run READ批准分开。六个相关完整模块143唯一项PASS（新增56含内），冻结 `{source}`，新片待独审。原资料/目录仍仅SYNTHETIC；普通启动缺合法provider时保持不可用，真实来源/业务/Windows/正式AT未验，完整项目未完成。[实现、全部窗口、证据和真实缺口](docs/F2/ResourcePlanApprovalRead-20261017.md)。\n\n')
section=(f'## 2026-10-17：已有资源方案批准独立只读契约\n\n基线 `{gate["base_sha"]}`，冻结 `{source}`。可信宿主显式接入已有记录的read/verify对象，严格模型与原身份/资料/目录/方案/来源/权限复核，固定原记录ID复读并复核当前head；页面分别显示核对通过、失效、缺来源和契约不可用，可GET核对原记录。Run READ与IsolatedPlanApproval不作为资源方案批准，不加创建/激活/消费或资源执行；普通CLI缺provider保持不可用。原entry_context的SYNTHETIC资料/目录门保持。\n\n六个完整相关模块143唯一项全部PASS，0FAIL/ERROR/SKIP，JUnit {seconds:.3f}秒；新增50接口＋6浏览器用例已含内。保留开发setup错误、UTC断言失败、首冻结141PASS、Playwright时间跳跃失败及补测；均不累加。720输入与原算法零漂移，继承{gate["inherited_archive_git_blobs_checked"]}证据保持，旧重复JSON键副本保留、另增修正；新导出仅脱敏字符串值并严格校验键与JUnit标识。\n\n正向证据是独立签名/当前head合成文件和工厂重建；实际普通子进程重启只证明缺provider仍不可用，不证明生产正向安装。真实namespace入口、既有批准源/主体授权/当前head与撤销、既有信任根及获准只读宿主适配器仍缺；Windows、正式AT/AT35、真实业务与资源履约未验，完整项目未完成。新片独审待；诊断已结束，无427或SIGINT重跑、Actions、main/强推、部署、模型、真实身份/Grant/批准/凭据/费用或安全网络权限变化，未知锁/进程/session未删。[全部证据与运行输入](ResourcePlanApprovalRead-20261017.md)。下方历史原字节保留。\n\n')
preservation=[]
for path in ('README.md','docs/F2/Plan.md','docs/F2/Log.md'):
    old=subprocess.check_output(['git','show',gate['base_sha']+':'+path],cwd=root)
    file=root/path
    assert file.read_bytes()==old
    if path=='README.md':
        header='# 园合 ParkWeave\n\n'.encode();assert old.startswith(header)
        new=header+intro.encode()+old[len(header):]
        assert new[len(header)+len(intro.encode()):]==old[len(header):]
    else:
        new=section.encode()+old;assert new.endswith(old)
    file.write_bytes(new)
    preservation.append(dict(path=path,preceding_sha256=hashlib.sha256(old).hexdigest(),preceding_bytes_preserved=True))
(r/'documentation-preservation.json').write_text(json.dumps(preservation,indent=2)+'\n')
print(json.dumps({'report':str(report.relative_to(root)),'source_sha':source,'final_unique':143,'seconds':seconds,'history_files_preserved':3}))
