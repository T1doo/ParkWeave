# ENG085：持久关联诉求、显式目标与覆盖结果

基线 `498d5d2ed03aa241f2bdcba72d614546033d3945`。承接《平台产品设计》§5.1/§5.2及F2-T01/T02/T06/T07，不执行迁移恢复任务。只核对用户明确列出的目标，不把固定本地目标当作模型理解全部自然语言诉求。

## 数据模型与最小迁移

原Case/Run/资料事项已保存建单诉求与不可变资料事件；ENG084预览中的额外必需目标尚只在会话内存在。本轮版本19只给既有 `preparations` 追加nullable `request_intent` JSONB列，给既有 `preparation_events` action约束追加UPDATE_REQUEST。无新表、GRANT、角色、身份、Runassignment、ACL或owner修改；`roles.sql`与权限模型字节保持。应用沿用原PREPARE/EXECUTE及现有资料表/事件表权限，应用本身不执行DDL。部署本切片前须由既有数据库迁移流程完成19，再使用新保存入口。

旧行NULL不回填固定目标。原Case.goal与preparations.goal不改；记录原始诉求及当前用户修订诉求的关联，显式目标列表、覆盖逐项目标状态、模板hash、联合资料revision和来源USER_EXPLICIT_STATEMENT。所有更新保留既有事件历史。空目标UNKNOWN、含未支持目标PARTIAL，明确唯一支持目标才SUPPORTED_LOCAL；该状态仅表示目录中有本地合成记录能力，不表示资料已齐、原诉求完整覆盖或履约完成。旧模板hash呈现STALE，当前覆盖尚未核对，需再保存。

`POST /api/preparations/{id}/request-intent`要求当前owner/PREPARE/EXECUTE、同企业/园区/SYNTHETIC与期望资料revision，沿用身份锁→key锁→资料父记录锁顺序。同一事务更新JSON/资料revision/IN_PREPARATION/清人工review、失效P1及原有UPDATE_REQUEST事件。目标或诉求修改必须重新核对材料，保留旧资源关联、分派、接单、回执与计划历史；不撤单或释放。相同key重放返回原事件，key输入或Case不符409；发生事件写入异常则整个更新回滚。

## 产品流程与权限

企业在同Case计划页看原始诉求，填写当前诉求，主动选择本地协作记录目标或列出其他必需目标，再明确保存。未主动选择时不默认勾选固定目标；空目标保存后保持UNKNOWN。刷新页面并重新选取事项，会从库恢复诉求、显式目标和覆盖结果。

页面仅用已保存且与当前草稿一致的目标预览；改草稿清除旧预览，不能启用。已保存目标必须与预览输入一致；已保存UNKNOWN/PARTIAL/STALE不仅隐藏UI启用，也在服务端阻止所有CREATE与P1核对。故即使旧固定目标直CREATE接口不带preview hash，也不能绕过新保存的未覆盖目标。旧NULL行保留原有限直CREATE兼容合同，同时明确标为NOT_RECORDED/UNKNOWN；不能假称这些旧Case已确认必需目标。

企业以外角色只看到必要覆盖状态。资料详情的新增JSON及新增事件payload对获派专员剔除；计划的私有intent和必需目标对专员/执行者不投影。用户修订的文本与未知目标不会因SELECT *或历史事件泄漏给其他角色。原来已授权的资料/回执可见范围不扩展。

实际修改已启用事项后，原计划id、revision、历史保留，当前缺口继续显示BLOCKED、PARTIAL及P3已有运行访问缺失。Case原始诉求与真实状态保留，目标仍未完成。

## 验证与失败保留

相关真实PG/API最终130 PASS/0 FAIL/2既有WARN，52.17秒。覆盖保存/重读/跨Case/企业/专员/执行者权限、当前EXECUTE拒绝与版本边界、并发同key/冲突、提交事件异常回滚、修改后预览失效与完整历史保留、v18追加升级/重复migrate/旧行NULL/原授权不变、模板hash STALE。

首轮124 PASS/1 FAIL/1 ERROR：空列表被旧测试helper替成固定目标、测试模块缺receipt_fixture导入；辅助修正后125 PASS/1 FAIL，回执保留测试误用不存在的preparation_id列，已改为经receipt step关联。最终130全通过，原功能失败记录保留，不改变拒绝或业务规则。

实际最终Chromium/API/worker/PG tag `f67f82265561`：新Case `0c317abb-4f90-48fc-b2e4-1f664ede2361`、资料 `82aa8ad5-67e2-4bb3-ae1c-50e2524b764a`、计划 `a2ba70d3-9a41-4ec6-b9b5-54788430fd31`。保存空目标UNKNOWN、未覆盖目标PARTIAL、页面reload恢复、改变诉求后重新保存/预览、支持目标明确启用、再加入未覆盖目标后保留plan revision1/history1，最终诉求联合revision8。实际响应丢失同key重试只多1条事件，commit后身份切换迟到回复不回显；专员私有intent为空。1200/390/320无横向溢出，桌面与覆盖状态窄屏截图实际查看。权限四表摘要前后相同；CaseNEEDS_INPUT/目标false/P3missing，未新增运行访问。API/worker自有进程回收，PG保留数据库并停止。

独立源码/最终浏览器及测试诊断清单复审无阻断。完整Linux首轮1477 PASS/2 FAIL/9native SKIP，303.71秒：Junit安全诊断测试名清单未登记新函数、旧升级测试把当前19当未来版本插入，已将清单按tests AST精确登记且未来marker改为20；不控制执行或应用/OS权限。修正与新增READ/EXECUTE/PREPARE三参数当前撤权拒绝验证的92定点PASS，30.97秒。最终完整Linux **1482 PASS/0 FAIL/9原生Windows SKIP/2既有WARN**，302.44秒；200份源hash复核无变化，最终源码、日志和7张实际图hash见[evidence/eng085-persistent-request-coverage.json](evidence/eng085-persistent-request-coverage.json)。9项原生skip保持，不能当Windows通过。预备全量一次因发现遗漏的schema18旧health断言主动中断，没有计为通过；用例保留并更新到当前19，原9native skip不增。旧带fixture-owner赋权的演示脚本仅适配入口，本轮不运行其赋权段。

## 可发布边界与后两项缺口的安全下一步

本片可作为本地合成用户显式诉求/目标记录、覆盖与预览失效机制供评审；尚不构成通用DAG模型编排、审核发布服务包、实际准备度或完整冷会话办理闭环。必须保留UNKNOWN/PARTIAL/NEEDS_INPUT与现有执行者访问阻塞，不把模板内部记录覆盖当Case成功。

1. **合法新Run协作访问**：现有应用只有读取Runassignment、检验本人分派/接受，没有创建运行访问的受权产品入口；全新Case当前确无访问。安全下一步是冻结既有身份/运行范围的授权前置与拒绝矩阵，明确由哪个已授权流程准备合法访问。未获得相应授权方案前，该步骤阻塞；不建身份、不自动grant、不复用旧Case授权或靠手改数据库使演示通过。已有授权Case可继续原办理和回读。
2. **审核规则准备度**：现有目录为合成工程资料服务；已有V1ServiceSpec受控结构/三值合同与/api/contracts/service结构检查（STRUCTURE_ONLY、published=false），不能当发布服务。尚无经业务审核发布的有限资格规则和权威来源，安全推进应复用这些合同，不再编造一套规则语言。安全下一步是在原§5.3范围冻结来源、规则候选/人工审核/发布的合同及TRUE/FALSE/UNKNOWN独立oracle，明确目前哪些源或审核权限缺失。发布入口若要求新权限则停该步骤报告；不借既有材料核对权发布政策，也不编造条件或自动资格结论。

下一产品方向继续原F2-T01/T02：在已有记录范围内验证修订诉求和显式目标的来源/冲突与受控方案覆盖，不削减必需目标以求通过。完整协作与准备度在相应权限/真实来源未具备时保持上述阻塞。

仅本地，不push/新CI/外网/日志路线/真实模型调用，预算0、R4关闭。F1未签收/F2并行探索、旧Windows工程失败和未测范围保持；Server不是Win11。
