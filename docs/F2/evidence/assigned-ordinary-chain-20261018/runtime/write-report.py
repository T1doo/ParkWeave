from pathlib import Path
import json,collections,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/assigned-demo-chain-20261018';dest=root/'docs/F2/evidence/assigned-ordinary-chain-20261018'
final=json.loads((r/'final-result.json').read_text());independent=json.loads((r/'independent/final-review.json').read_text());manifest=json.loads((dest/'manifest.json').read_text())
assert final['unique']==31 and not any(final[k] for k in ['failures','errors','skipped','input_drift'])
assert independent['passed']==3 and independent['blockers']==0 and independent['source_sha']==final['source_sha']
mods=collections.Counter(t.get('classname') for t in E.parse(r/'final.xml').findall('.//testcase'))
table='\n'.join('| `'+k.split('.')[-1]+'.py` | '+str(v)+' |' for k,v in mods.items())
text=f'''# 已有合法Run分派下的普通页面五步闭环

基线交付`0567ba3abea00e5cb2eb64ce3b46d04750dffb91`；本片冻结`{final['source_sha']}`，仍在普通开发分支`dev/f2-demo-original-page-intake-20261017`。唯一新增源码为143行`tests/test_assigned_demo_chain_browser.py`；产品src树仍为`6778db0198ba668a32198aca6c0d99f2aa311b92`，与TTL验收冻结72c及基线逐字相同，没有新增产品UI、业务算法或权限接线。

## 补齐的用户路径及严格初态

前一新Run页面切片从零业务数据通过DOM创建诉求/材料、独立核对、原NO_MODEL选择及P1/P2，并正确拒绝无已有执行者分派的P3。本片补齐另一个有用路径：已有精确Run执行分派时，普通页面实际能继续P3–P5，不能拿新Run缺分派作为整个路径的替代验收。

正向初态明确是自有隔离PG合成fixture：原`prepared` API创建、原两槽来源正文、原REVIEW/CONFIRM，以及既有角色/目录/资源配置；唯一该Run的executor assignment显式在普通API进程启动前准备。它不属于普通加载器，不是从新页面零准备取得权限，也不能迁入真实运行。普通过程启动之后无测试API业务初始化，三方操作全部通过真实Chromium DOM→独立普通configured_app子进程→自有PG；只读evaluate/wait观察不导航、不清key或解锁。

两个宽度1200/320均从原事项列表进入，读取目录、NO_MODEL生成并明确ADOPT、P1 VERIFY，原资源两占位/组合/Case关联及P2 VERIFY；专员向原已有合法执行者OFFER，本人ACCEPT后企业P3 VERIFY；执行者原SUBMIT，企业从“我的回执事项”读取原回执并独立ACKNOWLEDGE、P4 VERIFY；原REVALIDATE及P5 VERIFY。最终6项均LOCAL_OUTPUT_VERIFIED，整体LOCAL_OUTPUTS_VERIFIED、case_goal_completed=false。每例实际捕获18个POST响应，均2xx；响应监听只覆盖已收到响应，不冒称记录全部发送/无响应请求。原权限表前后相同，未创建运行、资料、Run访问或方案批准；既有Run/材料/分派初态与运行期效果分开。

同一数据库上普通API进程退出，再启动新普通进程和新浏览器；仅GET读取相同六目标结果，原业务历史及7张身份/权限/分派表不变。两例有实际JSON、API日志及PNG。这里只签本地合成记录，不是现实履约、资格、外部受理或Case正式完成。

## 冻结后实际验证

**4个完整相关模块，31唯一pytest项全部PASS，0FAIL/ERROR/SKIP**，外层{final['elapsed_seconds']:.3f}秒；741项源码、测试、脚本及原合同输入前后零漂移。新2例已含内，开发单例不重复加入。

| 完整模块 | PASS |
| --- | ---: |
{table}

[实际调用](evidence/assigned-ordinary-chain-20261018/runtime/final-invocation.json)、[完整JUnit](evidence/assigned-ordinary-chain-20261018/runtime/final.xml)、[实际结果](evidence/assigned-ordinary-chain-20261018/runtime/final-result.json)、[741输入](evidence/assigned-ordinary-chain-20261018/runtime/final-inputs.json)。26项原profile接口用例和原新Run页面2例同时覆盖错误配置/当前授权不足/无分派拒绝；负向fixture的授权变动仅限自有隔离数据库，不代表普通运行提供补权能力。

独立精确字节镜像静审0阻断，实际执行新2例与原缺Run分派拒绝1例，共**3PASS/0FAIL/ERROR/SKIP**，完全与本片31重叠、不相加。共享/镜像各741输入前后零漂移，独测pytest实际载入86个parkweave模块均来自mirror/src；普通子API按原helper固定镜像PYTHONPATH启动，未额外插桩其import origin。原件立即保存共享，不只依赖tmp。[独审结算](evidence/assigned-ordinary-chain-20261018/runtime/independent/final-review.json)。

TTL与模板修复已在较早72c源码冻结完成296PASS、独立31重叠PASS并交付0567，详见[前批报告](RecoveryDeadlinesAndTemplateFixtures-20261018.md)。本片产品源码字节相同，但测试树新增文件，**没有把前批296成绩转签给本片冻结或相加为新总数**。

## 开发失败与证据

development-v1为1FAIL：误将编辑后的request_text当原事项goal，列表实际上保留原Case标题；只修测试定位，不重写产品历史。development-v2为1FAIL：误点创建回执目录入口而期待现有回执决定表单；真实POST已完成OFFER、ACCEPT、P3 VERIFY和SUBMIT，改走原“我的回执事项”读取。development-v3为1PASS；随后加强禁止Run访问/方案批准POST的断言，重新冻结执行完整31，未迁开发分数。各次测试版本、741哈希、stdout/XML、请求响应记录和失败截图原样保留。

[manifest](evidence/assigned-ordinary-chain-20261018/manifest.json)保存{len(manifest['records'])}对raw/public哈希、{manifest['redactions']}处临时合成会话候选脱敏；[结构与哈希校验](evidence/assigned-ordinary-chain-20261018/archive-validation.json)覆盖实际JSON/XML/PNG等，私有原件保留，不导出PG data目录。继承29674个F2证据blob逐个Git核对保持，包含全部TTL原失败/中断原件。交付只正常推送开发分支，实际完整SHA及远端差异以最终回执为准。

## 真实运行尚缺输入

需要既有受限DSN/schema32、当前合法会话、同域READ及本人PREPARE/原获派REVIEW_ASSIGNED、原EXECUTE及资源权限；已存在原Case/Run/preparation及精确SYNTHETIC目录；当前pack/journal路径/hash和DB/目录绑定、原材料核对确认；该精确Run已有合法executor assignment和所需独立批准。新Run缺该分派继续拒绝，不由页面或本片补建。

NativeRunAccess permit/writer继续默认拒绝，普通provider可信宿主接线及正式来源独立验真、当前head/撤销、主体/Case/Run/已采纳方案绑定与正式批准映射等缺口保持。IsolatedPlanApproval不作为普通批准；不能只补凭据、自报REAL或复用fixture称正式接入。具体输入见[合成配置](LocalSyntheticDemoContract-20261017.md)与[正式来源缺项](FormalPreparationEntry-20261017.md)。

未验Windows/Win11、正式AT、真实主体/来源/业务、生产宿主与现实履约；真实模型调用0，完整项目尚未完成。没有新增真实身份、Grant、分派、目录发布、批准、凭据、费用或安全网络权限，没有改main、强推或部署，不动未知锁/进程。
'''
(root/'docs/F2/AssignedRunOrdinaryChain-20261018.md').write_text(text);print('report written')
