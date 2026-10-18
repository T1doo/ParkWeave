# 服务计划恢复期限与模板模拟的真实修复验收

源码与测试冻结：`72c1e2a8a3a28774d801b93735cca26f24f9597c`，源码树 `6778db0198ba668a32198aca6c0d99f2aa311b92`。基线 `441674c5bfd06ffb64343a148ff85fc4a5cdd1c7`；同一普通开发分支 `dev/f2-demo-original-page-intake-20261017`，root为唯一源码/Git写入者。恢复时实际远端仍为基线，本地领先1、落后0，main为`31e7acb7e53bb1ab6465b9daae59de28757f7583`。本报告只签下述范围，完整项目未完成。

## 已证明的17项旧失败根因与最小改动

此前全回归是267PASS/17FAIL，原报告与全部原件保留。9项恢复句柄错误来自真实产品缺口：readServicePlanHandle只检查字段形状，未检查expires的值。现在一次捕获now，并要求expires为有限数值，且严格满足`now < expires <= now + 86400000`。24小时上限不增加，现有原key、expires和同名有效替换语义保持；无权限、来源、403、UNKNOWN、恢复协议或原事件算法放宽。

其余8项是两个Node Element模拟缺少真实DOM的classList，原入口清理在instance GET之前调用classList.remove而抛错。补上与className同步的有状态add/remove/contains和原清理断言；有效类保留、取消恢复类移除，pending保护仍保留。没有用no-op mock替代原产品清私有视图，也没有修改原时序、绑定、403、ABA或UNKNOWN负向断言。

产品只改web.html的原reader一行；另两处模拟、一个12项窄reader单元模块及其JS。新12项使用实际源码函数与固定时钟，分别验证过去、now边界、1毫秒有效、24小时边界、超限、0、超远期、null/string/bool、缺字段与额外字段；它们是无HTTP的Node VM单元，不冒称完整浏览器。修复前8FAIL/4PASS、修复后定向30PASS，均另有实际清单/日志，不与最终296累加。

## 实际基线/当前同输入复现

R2已对175918基线HTML与441674当前HTML实际运行原guards及诊断：两边各7个guard失败、pending控制通过；7种失败均观察到同一缺classList.remove异常。完整Node DOM→ASGI桥接→自有PG也分别复现该错误，不能只凭静态源码存在性下结论。

TTL复现使用实际Chromium→普通configured_app子进程→自有PG；对expires=0和超远期，分别在两个精确HTML上输入相同序列化opaque handle。两个版本都错误接受并发送原key恢复GET，0POST、DB快照不变。复现探针的PASS只表示观察到旧缺陷，不是修复验收。第一次TTL探针因测试导入路径不足在启动阶段失败，一次精确修正后完成，失败原日志保持。

## 暂停与恢复不迁成绩

R2四分片被用户主动暂停：27个有名真实节点为17PASS/10FAIL，另3条只有time的XML记录是中断残留，不计PASS或唯一项；296范围其余269节点没有完成记录。10FAIL中8项在普通API健康就绪15秒预算失败，尚未进入页面脚本；另外两项在原5秒断言时分别仍SUBMITTING、LOADING。旧窗口没有逐阶段耗时证据，具体import/DB/HTTP或哪个await耗时仍未知，不能称环境flake或已证明的新增产品缺陷。

中断后的旧私有runner因无名记录汇总报AttributeError，原四XML、stdout及异常文本保留。恢复环境中旧/tmp测试目录及独测镜像缺失；不把先前回执冒称仍存原件，也不把旧独测6个通过节点用于本轮验收。

R3先保持同SHA、同原断言，串行重测这10项：10PASS/0FAIL/ERROR/SKIP，外层95.091秒，740输入零漂移。该成绩仅属于其窗口，不逆推旧超时唯一根因。随后完整回归启动脚本一次将verbose收集树当节点列表解析，296已收集、0项执行；原件保留，仅修私有运行脚本的收集参数，产品和测试输入未改。

## 冻结后完整执行

本轮14个完整相关模块，**296唯一pytest项全部PASS，0FAIL/ERROR/SKIP**；原284项逐ID全部包含，新增12项已含内。两非重叠有界分片各150/146项，每节点一次，无自动重试；五个写相同恢复截图文件的原例始终同分片。原15秒启动及5秒界面断言预算保持，独测运行推迟至主回归退出后。外层697.927秒；740个源码、测试、脚本及原合同输入前后零漂移，HEAD不变，窗口worktree干净。

| 完整模块 | PASS |
| --- | ---: |
| `test_preparation_read_write_timing_browser.py` | 13 |
| `test_demo_original_page_intake_browser.py` | 2 |
| `test_local_synthetic_demo_browser.py` | 1 |
| `test_material_file_import_browser.py` | 6 |
| `test_material_review_comparison_browser.py` | 22 |
| `test_material_version_compare_browser.py` | 23 |
| `test_native_preparation_entry_browser.py` | 5 |
| `test_case_goal_results_browser.py` | 28 |
| `test_service_plan_recovery_browser.py` | 67 |
| `test_template_plan_continuity.py` | 18 |
| `test_case_cancellation_offline.py` | 51 |
| `test_service_selection_web.py` | 43 |
| `test_resource_response_binding_browser.py` | 5 |
| `test_service_plan_ttl_boundaries.py` | 12 |

[实际调用与节点](evidence/recovery-deadlines-20261018/runtime/resume/final-invocation.json)、[完整JUnit](evidence/recovery-deadlines-20261018/runtime/resume/final-pytest.xml)、[实际结果](evidence/recovery-deadlines-20261018/runtime/resume/final-result.json)、[740输入](evidence/recovery-deadlines-20261018/runtime/resume/final-inputs.json)。原自有PG连接诊断只采新建测试集群，未修改连接预算、业务事务或断言；原日志保留，不把诊断本身计为测试。

独立精确字节镜像静审0新增阻断，实际独测31PASS：原17个失败ID、新12个reader单元、最初两项读写时序。其31项全部与主296重叠，绝不相加。9项原TTL为Chromium→pytest内uvicorn/create_app loopback→PG，1项模板为Node DOM/ASGI桥接/PG，7项guard与12项reader为纯Node，2项时序为普通子进程Chromium；不把纯Node称真实HTTP。独测前后共享/镜像740输入均零漂移，真实模块从mirror/src导入。[独审与独测结算](evidence/recovery-deadlines-20261018/runtime/resume/independent/final-review.json)。

## 证据与运行缺口

[manifest](evidence/recovery-deadlines-20261018/manifest.json)共370对raw/public哈希，69处其他候选仍脱敏；原件保持在私有.runtime。903处冻结测试函数标识误遮蔽已按源码AST证明恢复，涉及18件公开产物；18件旧公开副本、旧manifest/校验均保留。此次仅更正导出标识，未重跑测试，也不改变296项成绩。详见[更正映射](evidence/recovery-deadlines-20261018/identifier-correction/correction-map.json)、[296精确ID校验](evidence/recovery-deadlines-20261018/identifier-correction/296-node-id-validation.json)及[旧映射](evidence/recovery-deadlines-20261018/legacy-identifier-redaction/manifest.json)。[结构/哈希校验](evidence/recovery-deadlines-20261018/archive-validation.json)覆盖全部配对和JSON/XML/PNG等实际产物。只导出可取得的原件，不含PG data目录；旧29301个继承F2证据blob另作逐个Git核对。旧R1/R2失败不改写为通过，已有历史报告保持原字节。

源码、测试及本报告的diff-check为0；完整新增证据有164处原始空白告警，均保留原日志/XML等字节，不作修剪。manifest、archive-validation、delivery-checks为配对表之外的衍生metadata。

普通合成运行仍需要：既有受限DSN与schema32；有效原会话、同park/org的READ及本人PREPARE或原获派REVIEW_ASSIGNED；原Case/Run/preparation和精确服务版本SYNTHETIC目录；当前pack/journal绝对路径/hash、私有journal及精确数据库/目录绑定；原worker与用户明确诉求/两槽来源正文及独立REVIEW/CONFIRM。继续P3还须该精确Run已有合法executor assignment，资源动作须各自原权限/批准。页面、加载器及本补丁不创建它们，新Run缺分派继续拒绝。

NativeRunAccess permit/writer默认拒绝保持，普通provider接线与可信OS/PG安装未由本片补全。正式来源仍缺来源专用独立证明、当前head/撤销、Case/Run/已采纳计划/主体授权绑定及正式资源批准映射等代码，也缺来源结构、稳定ID/版本指纹和既有信任/授权/宿主合同；不能靠自报REAL、凭据或IsolatedPlanApproval fixture替代。见[原合成配置](LocalSyntheticDemoContract-20261017.md)、[正式来源缺项](FormalPreparationEntry-20261017.md)。

仅Linux隔离合成测试；Windows/Win11、正式AT、真实主体/业务/来源、生产宿主接线、现实履约与真实模型NOT_RUN。没有新增真实身份、Grant、分派、目录发布、批准、凭据、费用或安全网络权限，没有改main、强推或部署，未知锁保持。正常开发分支交付与远端差异以最终回执为准。
