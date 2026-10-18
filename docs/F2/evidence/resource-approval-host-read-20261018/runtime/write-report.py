from pathlib import Path
import json,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018';v=json.loads((r/'final-summary.json').read_text());ind=json.loads((r/'independent-final-review.json').read_text())
assert ind['source_sha']==v['source_sha'] and ind['passed']==55 and not any(ind[k] for k in ('failures','errors','skipped','blockers'))
e='evidence/resource-approval-host-read-20261018/';manifest=json.loads((root/'docs/F2'/e/'manifest.json').read_text());validation=json.loads((root/'docs/F2'/e/'archive-validation.json').read_text());assert validation['all_raw_public_hashes_valid']
rows='\n'.join('| `'+name+'` | '+str(n)+' |' for name,n in v['module_counts'].items())
p=root/'docs/F2/ResourceApprovalHostRead-20261018.md';text=p.read_text();old='本片正在开发验证。最终源码冻结、完整模块实跑、独审、raw/public哈希归档和实际远端结果在收尾补记；开发失败不改写为通过。';assert text.count(old)==1
section=f'''最终源码冻结 `{v['source_sha']}`，src树 `{v['src_tree']}`。八个完整直接相关模块 **190唯一项PASS，0FAIL/ERROR/SKIP**，实际外层{v['elapsed_seconds']:.3f}秒，无自动重试；749个源码/测试/脚本/原配置合同输入PRE/POST零漂移，新55项已经包含，不与旧成绩相加。新接口合同在源码冻结中的独立SHA256为 `{v['contract_freeze_sha256']}`；正文验证结果在测试后补记，不冒称最终文档字节是运行输入。

| 完整模块 | 唯一PASS |
| --- | ---: |
{rows}

独立精确镜像同一SHA：55唯一PASS/0FAIL/ERROR/SKIP，全部重叠主190，不相加；静审0开放P1/P2，共享/镜像各749输入零漂移，实际pytest模块来源核验见机器独审。独测不升级SAME-UID lab为真实host安装验收。[主调用]({e}runtime/final-invocation.json)、[完整主JUnit]({e}runtime/final.xml)、[逐ID/输入结算]({e}runtime/final-summary.json)、[独审/独测]({e}runtime/independent-final-review.json)。

新增53协议用例中5项为实际ASGI→Unix host→自有PG；其余为实际Unix通道/进程/pin/预算及纯配置/dispatcher或明确保护边界DI测试，不统称53项HTTP或生产安装。另2项实际子进程/浏览器测试：可信安装边界DI的configured_app→独立host→原签名合成文件→PG/Chromium，在不同API进程中读取同一原记录，再核当前撤销；两个API进程的临时HTTP端口不同，不宣称同origin重启。另一个未改普通CLI两次真实启动均因该lab不满足生产保护条件而拒绝，0后端读取。页面request观察均GET，不是全网络trace；fixture自身明确预置/撤销原合成来源，与产品业务写入分开。

全部开发窗都记录当时HEAD2e3加dirty源码/输入hash，不能迁入冻结b963成绩：dev-v1为7PASS/23FAIL/5ERROR（fixture合同键误用斜线、少原fixture导入）；dev-v2为20PASS/15FAIL（sandbox根owner65534使正向lab安装DI不完整）；dev-v3为33PASS/2FAIL（测试误写首次VERIFY原ID已知）；dev-v4为55PASS。修正fixture/断言不放宽生产门或改原算法。独审曾发现P2：最后post-pin核验之后缺deadline检查，已补前述检查和真实延迟反例。失败日志/XML/原输入、修补和预算边界见[失败台账]({e}runtime/failure-ledger.json)。

本片归档{len(manifest['records'])}对raw/public文件，逐对SHA/长度、严格JSON/JSONL、XML及PNG CRC/解压通过，所有JUnit测试标识原样。一个精确原测试故意重复state键的来源INPUT保留原字节并按路径/测试ID/SHA单列；不冒称它是合法结构输出。私有合成key bootstrap和PG data不导出。继承30651个证据Git blob的实际字节均与2e3基线一致，0更改；这不是重做上一批774私有配对的独审。[配对清单]({e}manifest.json)、[结构与哈希校验]({e}archive-validation.json)、[继承证据校验]({e}runtime/inherited-evidence-verification.json)。

尚未验证：真实不同UID/root保护/既有信任根/真实来源正向安装、来源专用证明和正式namespace入口、批准消费/现实履约、Windows/Win11与正式AT/AT35、真实模型或生产部署。新host client不等同于真实backend已接通；完整项目未完成。最终实际HEAD、正常push与远端heads差异在收尾实际查询，私有post-export回执不伪填进上述冻结manifest。'''
p.write_text(text.replace(old,section))
entry=f'''## 2026-10-18：已有资源方案批准的可信宿主只读接线

源码冻结 `{v['source_sha']}`，在原普通provider读取协议上补受保护public pin、独立Unix host固定READ/VERIFY、749输入下2READ/3VERIFY共享预算与普通configured_app显式配置；复用原Scope、原ID双读和当前权限/来源head复核，不重做批准算法。host只消费既有listener和可信adapter，不创建身份/服务/endpoint/信任根或批准。正式未知来源仍UNAVAILABLE，SYNTHETIC入口、permit/writer默认拒绝和批准不可消费保持。

八完整相关模块190唯一项PASS，新55已含内；同SHA独测55全部重叠PASS、静审0开放P1/P2，749输入零漂移。生产保护边界正向仅显式SAME-UID SYNTHETIC DI；实际IPC/API/PG/Chromium和不同API进程复读/当前撤销实跑，未改CLI拒绝lab。四开发窗失败与预算P2修补完整保全，30651继承证据blob原字节不变。详见[本片合同、测试与来源输入](REPORT_LINK)。

可继续编码的生产client/dispatcher/工厂接线已完成；真实source backend、四对象/主体/采纳证明及正式批准映射仍需据来源规范开发，不泛化为只缺凭据。运行还须原合法记录/Grant/目录、现有不同UID host与受保护pin、原批准源及当前head/撤销/验真机制。Windows、正式AT/AT35、真实来源/批准/业务/模型、生产host安装与部署未验，完整项目未完成。无main/强推/部署、新费用、真实身份/Grant/分派/目录/批准/凭据或安全权限扩大，未知锁保留。下方历史原字节保留。

'''
for name,link in [('docs/F2/Plan.md','ResourceApprovalHostRead-20261018.md'),('docs/分阶段开发计划.md','F2/ResourceApprovalHostRead-20261018.md')]:
 q=root/name;old=q.read_text();assert not old.startswith('## 2026-10-18：已有资源方案批准的可信宿主只读接线');q.write_text(entry.replace('REPORT_LINK',link)+old)
print('Report and two dated plan entries updated from actual final results')
