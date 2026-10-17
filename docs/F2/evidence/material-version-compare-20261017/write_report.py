"""Publish the completed evidence narrative; run only after export gate passes."""
from pathlib import Path
import json
root=Path('/workspace/ParkWeave');out=root/'docs/F2/evidence/material-version-compare-20261017';g=json.loads((out/'gate.json').read_text());f=g['final'];assert f['failures']==f['errors']==f['skipped']==0
source=g['source_sha'];table='\n'.join('| '+p+' | '+str(n)+' |' for p,n in g['module_unique'].items());windows='\n'.join('| '+w+' | '+str(v['testcases']-v['failures']-v['errors']-v['skipped'])+' | '+str(v['failures'])+' | '+str(v['errors'])+' | '+str(v['skipped'])+' | '+str(round(v['seconds'],3))+' |' for w,v in g['windows'].items())
text=f'''# 同事项新版材料与原版差异核对后补正

基线 `c3991ca0c7eee273bbb0be6da4e3aa929fe2e0d9`；冻结源码 `{source}`；开发分支 `dev/f2-material-version-compare-20261017`。父独审此前仅有限准入 c399 合成本地核对包及179完整重跑证据，未重哈全部316归档对，compare300触顶；这里不声明父审全归档。

## 实际用户路径

此前已有材料当前/历史正文、逐槽补正、审核失效和重新核对，也有文件候选预览。缺少的是“本次尚未提交的新版文件”与“当前同事项同槽材料”的正文/来源对照。原准备度只是材料和审核状态，计划来源冲突比较的是已保存来源与计划人工说明，均不等价。本片不扩展核对包或正式来源拒绝页。

已有合法会话打开本人原资料事项 → 原TXT/MD/CSV/JSON候选明确填入原材料表单 → “核对本表单与当前同槽材料差异” → 人工看完整新旧正文、来源和逐行变化 → 原“追加材料版本” → 原获派专员核对当前完整双槽资料包 → 企业原确认。文件填入或主动进入比较后，编辑正文/来源/槽位、刷新或换上下文都须重新比较；从未进入此功能的手工填写仍沿原流程。比较不自动保存、采用事实、认定补正充分或解决补正。

对照显示原材料ID/版本、正文指纹、来源类型/标签、本次实际待提交正文指纹及当前同槽补正理由/状态。首份材料明确没有旧版；正文相同与来源变化分开显示，不强制文本hash不同。正文相同的明确追加仍由原命令产生新版本并等待人工核对，不能自动RESOLVED。旧正文留在原历史。新增版本按原算法使旧审核失效。

原方案依据：[产品设计](../sources/V1/平台产品设计%20(2).md)106行的文件形式、131行的本人核对冲突、185–187行的版本/历史/补件、284行的人工文本保护；[原开发计划](../sources/V1/分阶段开发计划%20(2).md)F2-T01/T04、F3-T01/T03。原方案没有逐字指定此diff UI，本片是上述范围的一个具体用户切片。[实现前合同](MaterialVersionCompareContract-20261017.md)保留等价实现排除与边界。

## 复用原接口与状态

仅改前端以及相关测试。没有新业务端点、后端算法、表/迁移、权限模型或身份/Grant/分派/目录/批准。每次比较和比较入口追加前分别读取原entry → 完整preparation → material-corrections → entry。固定当前会话代际、preparation/Case/Run/revision、service精确版本、slot、原当前材料ID/version/text/hash、整包snapshot、补正引用和实际候选正文/来源；后一次投影须等于人工已看的投影。同revision下来源元数据变化仍不能沿用比较。

CSV仍用原明确转义编辑表示，比较先调用原decoder，按当前原命令的Unicode空白归一化后比较，并把同一实际正文送入原ADD_EVIDENCE；不把编辑器JSON_STRING或raw文件hash当正文。控制字符/孤立代理项在该比较入口拒绝，不截断。旧版材料以原API的4000码点为上限读取，包含超过4000 UTF16单元的合法旧正文。新文件候选仍保留原4000 UTF16单元上限。正文纯文本渲染，CR明确转义；逐行LCS最多250000单元，超预算时保留两份全文并明确仅供人工核对。

原CAS、原key、UNKNOWN和不透明恢复句柄保持。只读预检认可精确的自身prepCommand或真实prep-evidence.onsubmit写流对象、原可达调用集合、尚未失败且零请求阶段；外来/失败/已发请求/全局在途/UNKNOWN仍拒绝。每个异步阶段后、调用返回后及生成原key前重检。临时flow不写入比较状态。原成功读回只在原逻辑确实清空未变草稿时退出比较模式；UNKNOWN后的新草稿继续保留要求。

当前真实403沿原清理器清私有内存与DOM，保留原不透明恢复句柄；旧上下文的迟到200/403不覆盖新上下文。目录来源失效沿原entry返回409，拒绝比较且保留草稿，不补建目录。比较不新增localStorage。四次GET不是跨系统原子或未来有效性证明，原服务端CAS仍是提交事务边界。

## 冻结与实际验证

同一冻结源码上的10个完整相关模块 **{f['unique']}唯一项全PASS，0FAIL/ERROR/SKIP**，JUnit {f['seconds']:.3f}秒。新增{g['new_unique']}项已含其中；开发、修补窗口和独立探针都不相加。{g['source_inputs']}个源码/测试/脚本/配置输入SHA256零漂移。独立只读审查的精确源码、命令、报告转录及未验证边界见[独审记录](evidence/material-version-compare-20261017/independent-review.json)。

| 完整相关模块 | 唯一项 |
| --- | ---: |
{table}

实际Linux Chromium通过普通configured_app独立进程和隔离PG完成文件选择、未比较拒绝、全文与来源变化显示、真实ADD、原审核失效/补正待复核、独立REVIEW/CONFIRM及普通API进程重启后GET-only读回。包括1200/390/320px无横向溢出和脚本内容纯文本。边界覆盖同正文/同来源、来源单独变化、四种编辑后失效、并发改材料/补正、同revision元数据变化、当前原权限/来源拒绝、迟到200/403与身份/Case ABA、实际Pydantic正文与保存hash一致、LCS预算/合法旧非BMP正文、实际已提交却丢回复的原异议UNKNOWN与撤权清理。原CSV四种浏览器保存/重启及不可改原key恢复继续完整回归。

独立A/B仅在内存提取真实前端函数，DOM、GET及业务writer为替身；其dispatch不是实际HTTP。另与本地安装的Pydantic校验器对照，先扫描Unicode scalar集合，再逐点核34种候选及额外坏输入，并非110万次模型实例。命令/stdout由审查者报告，根线程转录且未复跑，不冒称根线程原始执行日志。首个独立探针因把原truthy UNKNOWN对象严格比较为true而退出1，仅把harness断言改为Boolean后成功；失败及命令均保留，不改产品。

所有窗口均完整保留，不能将其中通过项叠加：

| 窗口 | PASS | FAIL | ERROR | SKIP | JUnit秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
{windows}

开发首窗自身写流门误拒绝；第一次修补脚本在写文件前断言失败，却误启动旧代码窗口；随后发现真实表单外层写流名仍未获认可，精确补齐。dev-v4实际ADD/CSV已通过，完整用例在REVIEW读回结束前导航，测试改等原保存事件。dev-v5目录测试尝试DELETE被外键阻止，尚未进入HTTP；最初进度误归因为409/403断言，已纠正并保留原traceback。repair-v6同revision元数据用例通过，目录夹具仍因同一外键失败；改用原测试已有source={{}}隔离故障注入，repair-v7实际观察409、草稿保留、零POST。没有移除约束、放宽产品拒绝或伪造成功。工具断言和归因更正见[失败账](evidence/material-version-compare-20261017/failure-ledger.json)与[action记录](evidence/material-version-compare-20261017/action-failures.json)。

## 运行还缺的输入与未验范围

| 层次 | 还须已有的合法输入/实现 |
| --- | --- |
| 本片普通合成记录 | 当前合法会话及本人owner READ/PREPARE；原preparation/Case/Run ID与相互绑定；原service ID/精确版本及合法preparation_catalog来源；当前获派reviewer、READ/REVIEW_ASSIGNED。追加仍须原命令的当前EXECUTE等授权与revision；原完整双槽REVIEW和企业CONFIRM不能省略。 |
| 真实新版材料 | 用户有权使用的真实新旧正文、来源ID/修订/指纹与版本关系、用途授权、所需正式材料要求及实际审核主体。文件名、标签、hash和字面差异本身都不证明真实性或充分性。当前文件入口仍只接受明确合成样例；本片未开启真实材料导入。 |
| 正式资料来源 | source_domain/source_id、四对象稳定ID/类型/关联、owner/reviewer与park/org；preparation/plan revision、service精确版本、source_revision_sha256及规范化算法；当前head/撤销协议、源主体到本地主体合法映射与用途授权、既有采纳依据及已有信任验证协议。 |
| 正式产品与可信宿主 | 获准只读宿主/backend、按具体来源实现FormalSourceReader/IndependentProvenanceVerifier的独立证明/绑定/当前版本核验，及正式方案/资源批准映射。configured_app provider注入仍不完整，仅配置对象不能成功。NativeRunAccess默认拒绝permit/writer保持；不得以IsolatedPlanApproval或测试签名代替真实批准。 |

详见[正式资料来源报告](FormalPreparationEntry-20261017.md)、[原普通入口](OrdinaryPreparationEntry-20261017.md)与[已有资源方案批准读取](ResourcePlanApprovalRead-20261017.md)。无合法PREPARE、REVIEW_ASSIGNED或精确目录时准确拒绝。本片没有新增真实主体、凭据、Grant、分派、目录发布或批准。

Windows原生正式AT、真实园区/企业材料与履约、生产host正向来源接线、真实模型、部署及全项目验收仍未执行。SYNTHETIC隔离测试只证明本地工程流程；NOT_EVALUATED、NOT_SUBMITTED、NO_EVIDENCE及Case未完成的边界不变。项目未完成。

## 证据与交付

[最终gate](evidence/material-version-compare-20261017/gate.json)、[完整JUnit](evidence/material-version-compare-20261017/final-v1.xml)、[完整日志公开副本](evidence/material-version-compare-20261017/final-v1.log)、[冻结清单](evidence/material-version-compare-20261017/freeze.json)、[原件/公开件hash对](evidence/material-version-compare-20261017/public-pairs.json)。公开副本仅处理临时合成会话字符串值，JSON键、JUnit用例身份与远端引用保留；私有原件和失败源码快照保全。

本轮根线程自身逐项核对全部{g['inherited_F2_git_blobs_checked']}个继承F2文档/证据Git blob零变化，不把它说成父审全部归档核验。本轮公开{g['public_pairs']}对原件/公开件、全部JSON/XML/PNG及最终源码漂移在实际交付验证器中重新检查；该后置结果记录于私有delivery-verification.json与最终回复。常规开发分支推送后才报告实际交付完整SHA、远端0/0与干净工作树；不预填尚未发生的成功。不改main、不强推、不部署、不新增费用或安全网络权限、不调用真实模型、不查询拒绝的Actions，也不删除未知锁或进程。
'''
(root/'docs/F2/MaterialVersionCompare-20261017.md').write_text(text)
p=root/'README.md';s=p.read_text();line=f'2026-10-17 新增同事项新版材料与原版差异核对：原文件候选填入后，人工看完整新旧正文、来源/版本及当前补正，再明确沿原ADD、独立REVIEW与企业CONFIRM；不自动采纳事实或解决补正。冻结{source[:8]}的10个完整相关模块{f["unique"]}唯一项PASS（新{g["new_unique"]}含内）；失败/修补窗口分存不相加，Windows正式AT、真实材料/业务及全项目未验。[使用、边界、运行输入与证据](docs/F2/MaterialVersionCompare-20261017.md)。\n\n'
assert s.startswith('# 园合 ParkWeave\n\n');p.write_text(s.replace('# 园合 ParkWeave\n\n','# 园合 ParkWeave\n\n'+line,1))
print('Report and README written after successful gate')
