"""Append completed results; prepend new status preserving all prior bytes."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/formal-preparation-entry'
OUT=ROOT/'docs/F2/evidence/formal-preparation-entry-20261017'
g=json.loads((OUT/'gate.json').read_text());f=json.loads((R/'freeze.json').read_text())
assert g['final']['unique']==186 and not any(g['final'][k] for k in ('failure','errors','skipped'))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
seconds=g['final']['seconds'];source=g['source_sha'];report=ROOT/'docs/F2/FormalPreparationEntry-20261017.md'
body=report.read_text();assert '## 最终冻结与实际验证' not in body
lines=['\n## 最终冻结与实际验证\n',f'源码冻结 `{source}`，723输入无漂移。八个完整相关模块 **186唯一项PASS，0FAIL/ERROR/SKIP，JUnit {seconds:.3f}秒**；新增40项接口/纯契约及3项浏览器拒绝用例已含内。原143项在本片新SHA重新执行，不加历史成绩；不是全仓、正式AT或真实来源正向验收。\n',
       '| 完整模块 | 唯一项 |\n| --- | ---: |']
for name,count in g['module_unique'].items():lines.append(f'| `{name}` | {count} |')
lines += ['\n开发窗dev-v1的38PASS及edge-v1的2PASS分别保留且与最终重叠，不相加。首窗结束后补充主体/用途Lookup、禁止旧signature/history/approval字段及严格布尔revision拒绝，再正式冻结。首窗原五个源码/测试文件、原diff与调用记录保留，未把WIP标成最终冻结。\n',
          '首版归档把两条普通Git分支名误当43字符会话值脱敏，共4处；首版完整副本、原helper及错误记录保留，加入原远端引用白名单和逐字节一致性检查后重新导出，不重跑测试。\n',
          '一次web apply_patch因整行上下文不匹配未应用，API补丁已独立成功；核对后完整应用web补丁。执行通道一次transport disconnected，随后一次pwd确认恢复，原pytest PID及session继续，未重复启动测试；落盘证据确认继承核对实际完成。错误、恢复及结果保留于action-failures.json，不推断产品根因，不扩连接诊断。\n',
          f'继承{g["inherited_archive_git_blobs_checked"]}个F2证据blob未改；所有原src文件除API接线和页面外逐字节保持，新增formal模块只做封闭预检。原SQL/身份/权限/NativeRunAccess及合成来源/资源批准算法保持。实际远端98个原头及main在交付前未变，0fbd独审分支仍冻结。\n',
          f'归档{g["public_pairs"]}对原件/公开件hash已核对，JSON只脱敏字符串值并保留键、严格拒绝重复键，JUnit标识/属性保持。原始私有文件不覆盖。\n',
          '[最终gate](evidence/formal-preparation-entry-20261017/gate.json)、[完整JUnit](evidence/formal-preparation-entry-20261017/final-v1.xml)、[原日志公开副本](evidence/formal-preparation-entry-20261017/final-v1.log)、[冻结723输入](evidence/formal-preparation-entry-20261017/freeze.json)、[原件配对](evidence/formal-preparation-entry-20261017/public-pairs.json)、[通道与补丁失败记录](evidence/formal-preparation-entry-20261017/action-failures.json)。\n',
          '交付提交仅添加报告/历史状态和证据；实际交付SHA、远端与未提交差异于提交/推送后写入私有 `.runtime/formal-preparation-entry/delivery-verification.json` 和最终回复。新片待独审。正式来源读取卡点尚未全部解决：未知来源结构下本片只交付必要接口/类型与拒绝面；专用证明/绑定/批准映射仍须由本项目依据上表具体输入实现，不归因于单纯环境或凭据。完整项目未完成。\n']
report.write_text(body+'\n'.join(lines))
intro=(f'2026-10-17 正式资料来源新增独立入口条件预检与源域类型/精确选择拒绝面，未知来源证明始终关闭；不删除原SYNTHETIC门、不以REAL/verified标签或fixture授权。明确区分尚缺产品实现与所需外部结构/授权字段。本片八完整相关模块186唯一项PASS（新43含内），冻结 `{source}`，新片待独审；尚未实现正式记录成功读取，Windows/正式AT/真实业务未验。[源码原因、实际交付与逐项输入](docs/F2/FormalPreparationEntry-20261017.md)。\n\n')
section=(f'## 2026-10-17：正式来源入口预检，专用来源证明仍待实现\n\n基线 `{g["base_sha"]}` 保持原分支供独审，新冻结 `{source}`。查明原数据库CHECK、固定合成创建、runtime/entry_context及NativeRunAccess成功本地Case证明均限定SYNTHETIC，Store仅LOCAL/FAULT_INJECTION。不能删除判断或只靠凭据/provider标签接入正式数据。新增独立源域/对象引用、精确Selection、当前主体/用途Lookup、公开缩小配置及reader/verifier接口；两个GET和原页条件面板始终不可用，未知合同不调用任何来源/验真回调，不授予业务权限。\n\n八个完整相关模块186唯一项全部PASS、0FAIL/ERROR/SKIP，JUnit {seconds:.3f}秒；新40接口/纯项＋3浏览器已含内。开发38与边界2重叠保留，未加分；723输入零漂移，继承{g["inherited_archive_git_blobs_checked"]}证据未改。补丁上下文失败及一次通道断开/正常恢复保留，原测试未重启，未重跑原427和SIGINT诊断冒烟、没有扩展连接诊断。\n\n尚缺项目代码是来源专用的五类独立证明核验、正式计划绑定与批准映射；外部提供者须给源域/ID/对象关联/版本hash规则、原采纳和Run回执语义、主体映射/精确授权及当前head/撤销/既有验真协议，具体字段和现有接口已逐项列明，不全归为环境。无真实来源/身份/Grant/批准/凭据/费用/安全权限、模型、main/强推、部署或Actions动作；未知锁/进程保留。正式业务、Windows/AT及生产正向接线未验，新片待审，完整项目未完成。[源码与证据/精确输入](FormalPreparationEntry-20261017.md)。下方历史原字节保留。\n\n')
rows=[]
for name in ('README.md','docs/F2/Plan.md','docs/F2/Log.md'):
    old=subprocess.check_output(['git','show',g['base_sha']+':'+name],cwd=ROOT);path=ROOT/name;assert path.read_bytes()==old
    if name=='README.md':
        header='# 园合 ParkWeave\n\n'.encode();assert old.startswith(header);new=header+intro.encode()+old[len(header):]
        assert new[len(header)+len(intro.encode()):]==old[len(header):]
    else:new=section.encode()+old;assert new.endswith(old)
    path.write_bytes(new);rows.append(dict(path=name,prior_sha256=hashlib.sha256(old).hexdigest(),prior_bytes_preserved=True))
(R/'documentation-preservation.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps({'source_sha':source,'final':g['final'],'report':str(report.relative_to(ROOT))}))
