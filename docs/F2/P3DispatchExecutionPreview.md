# P3 原分派接单隔离执行预览：有限验收

运行候选 `345c95701851f16c71a3a36cb9548ee043a9c5b0`，基线 `31336f74f187f4268c31af1ff6284426aea19d26`。先提交[有界写入与存储合同](P3DispatchExecutionPreviewContract.md)（d6a0b4c02bf89f5fabdef33204df4bbfa8274590），再将漏列的原CREATE step/event INSERT修订为[79模板闭包](P3DispatchPreviewSQLClosure.json)（d4c7dbb3f91d616e803c44f72cccf3a9e95b0c89），然后实现。冻结356个源码路径，manifest SHA256 `75c98854e6f2514c11a5c48cf20c26af629741ef76fe709f2e785ece2cc3cb7d`，1571个实际AST函数诊断ID；roles.sql保持SHA256 `604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3`。

在实际原P1资料确认与P2资源关联成功后，实际调用原service_dispatches.offer、command ACCEPT/DECLINE、executor_receipts CREATE step/event及dispatch_notices.enqueue。27个专属临时影子表，search_path只pg_temp，封闭代理只接受79个精确SQL；未知SQL、公有表回退、commit、P4写入和通知消费被拒绝。复制本轮实际P1/P2的Case/Run/preparation、双槽证据、确认hash和资源关联/组合receipt关系；使用新的模拟角色/UUID和影子资格，原人没有批准。原READ/EXECUTE/PREPARE/HOLD、原获派专员REVIEW_ASSIGNED、精确Run唯一当前executor及managed bridge继续判定，运行时不补正式Grant或指派。

ACCEPT实际留下OFFER/ACCEPT事件和一个AWAITING_RECEIPT step及CREATE事件，没有回执正文；DECLINE留下OFFER/DECLINE且step为零，明确尚未接单。原enqueue实际生成4条未消费PENDING outbox，无delivered notice；换版后原接受拒绝保留OFFER及2条PENDING，无伪造ACCEPT。每个自有PG连接finally rollback/close，仅独立0700根/0600 SQLite的不可变预览及proof持久。除原authorization_audit诊断表外，全部public业务表逐值和旧P1/P2 SQLite整文件不变，正式分派/回执/通知业务写入为零；预览UUID不能被正式分派或回执入口消费。

独立scope保留Case、资料revision、双槽ID/version/hash、请求revision、P1/P2/P3注册合同、资源和原参与者资格generation绑定；当前授权先于历史，源CAS、同key幂等/异body拒绝、并发和提交前租约重验继续沿用。源变更保留旧STALE历史，只有明确新预演才重绑定。独立proof锚完整artifact/state/decision及全目标，单独改正文并重hash不能更改决定、actor、outbox、目标或receipt。基础设施503不伪装领域FAILED；提交后丢响应只GET核对原key。

原bounded-planning页面增加明确ACCEPT/DECLINE选择、读取历史和GET恢复。恢复句柄独立storage key，仅五个不透明字段、8条/24小时，无token/资料正文；Case/身份/草稿变化及403清私有视图并拒绝迟到回复。真实API不同PID重启、冷页面和原key均只GET；never-sent key显示NOT_OBSERVED，无自动OFFER或ACCEPT。DECLINE后原资料换版，冷页面仍显示旧DECLINED与STALE，无自动新接单。320/390/1200宽度已验证。全部原必需目标和unsupported目标保留，P4/P5列未预演，Case未完成。

| 窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根冻结19完整相关模块 | 511 PASS，0FAIL/ERROR/SKIP，自然0 | 303.441 / 305.311756 |
| 独立19完整相关模块 | 511 PASS，0FAIL/ERROR/SKIP，自然0 | 301.150 / 303.046972 |
| 独立自写真实HTTP/PG | 10 PASS，0FAIL/ERROR/SKIP，自然0 | 14.280 / 15.559451 |
| 独立自写原页面Chromium | 2 PASS，0FAIL/ERROR/SKIP，自然0 | 8.470 / 9.779278 |

19模块包含新增35项及原P1/P2、提交保护、权限/managed Run、资料/规划、资源和原dispatch/notice/receipt回归。原既有receipt模块SUBMIT/ACK回归不算新P4预演。独立探针使用自己HTTP/PG窗口、原模拟owner token执行ADD_EVIDENCE（无token轮换/Grant修补）、实际HTTP GET检查五类正文重hash篡改409、原专员/执行者撤权先于历史403，验证原actor与事件revision、step关联、4个outbox recipient pair、公有逐值/旧库字节和UUID隔离。窗口独立，不把相同511相加冒充一次验收；静态AST的27/79合同对照不计运行测试。

开发窗按[原始逐窗hash和分类](evidence/p3-dispatch-execution-preview/development-windows.json)保全：dev01/02各1个产品FAIL（既有Run表无managed_access列）；dev03/06各1个产品FAIL（冻结SQL漏原CREATE INSERT，封闭拒绝）；四次产品失败观察对应两个已修复原因。dev04/05各1个观察器fixture ERROR，dev08为2PASS/1个无效source_kind观察器FAIL；dev07的21PASS、dev09的34PASS均是后续修改前开发窗口，不转成冻结验收。全部失败XML/log留私有.runtime并给hash，未隐去、改名或并入最终PASS。

本次仅P1/P2/P3原合成隔离预演有限签收。P4 SUBMIT/ACK、P5、完整AT14、全仓、Windows未运行/未签收；不代表原人批准、正式资源可用容量或履约，未复制正式controlled plan/Approval。source_atomicity=false，SNAPSHOT_MATCH/STALE不承诺全来源原子一致；没有新增PG进程重启验收，不抵御同权限管理员联改正文/proof/锚或数据库截断。新接单preview接口默认关闭，仅显式合成工厂开启；不增加权限、模型调用或外部通知，不完成Case。旧Windows Job/accounting未推送修复留待以后重做，资料包导出未重做。

root是唯一源码/Git写入者。候选普通推送后对精确运行SHA独立审查；报告LIMITED_PASS、资源关闭及356路径前后零漂移后，仅追加本安全证据文档，再普通推送候选及ff-only整合dev。main、正式授权、凭据/安全网络配置均未改，未部署、未强推。

[独审报告](evidence/p3-dispatch-execution-preview/independent-report.json) SHA256 `25ce39df69f8b5d4d853caafe36d2852c5cbc5eeb425d611df9d8229d32d11a7`；[根冻结结果](evidence/p3-dispatch-execution-preview/root-frozen-audit.json)、[独立自写HTTP/PG探针](evidence/p3-dispatch-execution-preview/independent/test_independent_api.py)、[独立原页面探针](evidence/p3-dispatch-execution-preview/independent/test_independent_browser.py)、[320px旧DECLINED/STALE画面](evidence/p3-dispatch-execution-preview/independent/declined-stale-320.png)、[逐文件hash](evidence/p3-dispatch-execution-preview/artifact-hashes.json)。
