# 接单后、首次回执前取消：交付证据

状态：**LIMITED_PASS，有限功能已完成实际验证，等待父审按正常独立分支签收**。范围冻结见 [有限合同](CaseCancellationBeforeReceiptContract.md)，原产品依据为 §5.5、§7.1、§7.4。前片交付 `396602aa4e4889cb32d6af89a2b32cc3e45b5029`、前片源码 `557528da70d905859d7fd09dc0b4ed8f5545af51` 原样保留。

## 行为和入口

企业本人当前 READ/PREPARE/EXECUTE，明确确认理由，绑定精确 Case、资料/生命周期版本和完整历史来源 SHA。新增 `/api/preparations/{id}/case-cancellation-before-receipt` GET/POST 与 `/recovery/{key}`；原首次接单前入口仍拒绝任何历史真实 ACCEPT。

新范围只允许核实成功建单的普通 SYNTHETIC Case，至少一次真实 ACCEPT，全部历史本地人工步骤均为精确 ACCEPT/CREATE 证明对应的空初始步骤，从未提交回执。合法换人未决/拒绝/撤回和材料换版重接单历史也检查全部世代。已有任何历史提交、决定、关闭、外部效果、隔离来源或无法证明的世代均拒绝；取消不支持恢复，不代表完整 Case 生命周期。

取消事件与 Case/local CANCELLED 同事务。相同原键同参返回原提交、异参冲突；新旧入口不能互换键。未知响应只 GET 原入口原键，不自动 POST 重发。当前权限和原事件/持久状态继续核验。预览计划和资源关联仅给出 id/revision/SHA，避免以 Case 权限导出已撤权的资源详情。

Run 成功、资料、真实 ACCEPT/CREATE、步骤、关联/预约和容量保留，不伪造 WITHDRAW，不自动释放资源。原独立释放和组合取消继续按其当前权限。新回执 GET/list、分派/通知和页面呈现 Case 只读；迟到回复不能重新激活写动作。

## 写入口和锁序

取消沿 parent UPDATE → dispatch UPDATE → Case UPDATE → local ledger 顺序。回执 SUBMIT 先 parent SHARE 再 Case 检查与步骤锁；其它写同样先 parent SHARE/UPDATE，至提交仍持锁。取消先赢则晚写拒绝；SUBMIT 先赢则取消拒绝；其它写先赢且改变来源，旧预览拒绝，刷新重新明确确认后才可取消。

| 实际入口族 | 服务端边界 |
| --- | --- |
| 所有材料命令、整理摘要、事实声明/选择/锁定、材料异议、复用、诉求与机会、就绪检查、规划记录 | `prep.scoped(... business_write=True)` 或持 parent 后显式 `case_write_guard`，在旧键 replay 前拒绝 |
| 分派 OFFER/REOFFER、ACCEPT/DECLINE/WITHDRAW、换人旁路 | `service_dispatches._parent` → `_root` → Case guard；执行者旁路也覆盖 |
| 所有回执命令、legacy CREATE、隔离本地执行写入口 | `executor_receipts._parent` → Case guard → step；本片拒绝隔离来源 |
| 资源关联、交付与计划批准/采用、模板换版 | parent 持锁的 Case guard；独立 hold/group 释放继续原权限 |
| 校验/关闭/重开 | `case_lifecycle._context` 显式业务 guard；取消后全拒绝 |
| 历史 GET，包括需 FOR UPDATE 的 GET | 保留当前读取权限；不以锁模式误判业务写；取消后禁止计划隐式失效写 |
| 旧 outbox 消费和通知打开 | 重核持久 Case 状态，保留历史但无可接单动作 |

schema 31 仅扩已有 local event action CHECK，保留原创建票据/当前真实 PG owner、事务与表所有权门。旧030/029重放夹具只在原票据和回滚事务临时移除后来版本标记；未来版本反例使用32。原 Linux 合成启动器识别31，旧30需要升级时仍因缺创建票据拒绝，不能追补票据或扩大授权。

## 已保全的实际测试窗口

| 窗口 | PASS | FAIL | ERROR | SKIP | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| root first | 73 | 8 | 0 | 0 | 新模块初窗；夹具 CHECK/FK、旧计划前置和助手 None 输入失败 |
| root ui-first | 22 | 0 | 0 | 0 | 原生产页面代码，离线 NodeVM；无浏览器 |
| root second | 304 | 1 | 0 | 0 | 5完整相关模块；旧029重放夹具残留31 |
| root third | 314 | 0 | 0 | 0 | 修正后5完整相关模块，含真实 PG 六类双方向锁等待 |
| root full-attempt-1 | 67 | 2 | 0 | 1 | 不完整70条，exit2，主动 SIGINT；source401无漂移；不能当完整回归 |
| root schema-integration | 138 | 1 | 0 | 1 | 5完整版本集成模块；真实 wheel 缺031资源，后续修正 package-data |
| root proof-and-wheel-fix | 164 | 0 | 0 | 0 | 新后端107、机会35及离线页面22；真实 wheel 安装/迁移成功 |
| independent frozen-review | 314 | 0 | 0 | 0 | pytest0；16测试/脚本中途漂移，runner1；不是最终冻结签收 |
| independent pre-fix-extra-probes | 9 | 2 | 0 | 0 | 真正复现两种损坏世代仍取消成功的产品缺陷 |
| independent proof-corrected-extra-probes | 11 | 0 | 0 | 0 | 同最终401清单；原两种缺陷拒绝且不写，未提交时运行 |
| independent final-frozen-review | 132 | 0 | 0 | 0 | 最终3fc6fa7/401清单零漂移；新后端107、离线22、迁移3 |
| root full-final | 1390 | 0 | 0 | 1 | 最终3fc6fa7；37完整模块，1391唯一ID，进程0，401清单零漂移 |

first 的8个失败原始异常全部保留：namespace/external 的旧 CHECK 和 closed_history 的 FK 在 API 前拒绝损坏夹具；plan 和 controlled-history 在已有接单后试图建立必须接单前采用的旧四步计划；三种回执决定助手无法由空 receipt SHA 构造请求。修正为自有测试库中的显式损坏、正确业务前置、合法注册计划采用，以及合法请求格式后再断言业务拒绝，没有改生产 CHECK/FK 或降低业务守卫。

second 唯一失败是029重放夹具只删30而留下31；只修其测试回滚事务。独审另发现非对象 JSON payload 的异常路径、未来版本测试断言和历史世代绑定疑点，静态发现与实际测试失败分别记录，不把静态推导计作实测 FAIL。

full-attempt-1 保留实际两个 FAIL：跨租户 fixture-b worker 返回0后 Case 数量0而预期1；其原失败没有 worker stdout/Run 状态证据，原因待复验，不假称已确认。另为旧迁移测试当前版本预期30而实际31。只向核实 argv 的本任务 pytest PID 发送 SIGINT，停止后的原 XML/log/源清单都保留；剩余标识为未执行，不能计为 PASS。第一次进程选择器因多匹配自行拒绝，未发送信号；随后按精确 argv 识别了本任务进程。

schema-integration 的唯一 FAIL 是实际 wheel 内没有 `parkweave/migration-031.sql` 的原 KeyError；修正 `pyproject.toml` 原 package-data 显式清单，不改测试包装检查。跨租户 b/c 同原 worker 一秒租约的独立实测均为 SUCCEEDED/VERIFIED、Case1，但不能恢复旧失败未记录的状态，也不能确认旧根因。原断言继续 Case1，补充失败时 worker stdout/stderr 和持久 Run/operation 状态，未放宽租约或业务要求。

独审自有 PG 的 pre-fix-extra-probes 为9 PASS/2 FAIL：后续 handoff/new_material 的 ACCEPT 与 CREATE 同时丢失全部扩展世代字段、原 REOFFER 完整时，原实现实际给 `can_cancel=true` 并 POST200。原输出、观察、修前源码快照均保留。修正为每次接受都与原 OFFER/REOFFER 扩展逐字节规范表示相等，后续实际接受必须有完整非空前驱证明；四条双/三事件剥除回归反例与先拒绝后首次接单正例已加入。

## 约束及交付核验

根任务为唯一源码/测试/Git 写入者，独审只读及独立自有运行时证据。分支 `dev/f2-case-cancel-before-receipt-20261011`；最终源码/测试冻结 `3fc6fa712f14820d88fcf8cd94fa70fcf6120e0c`，401路径清单 SHA256 `cb236fe42b8acf4c6cf2748d781106844bffd1b1201094d63827d3f6350309c7`。

最终根窗口在2026-10-11 13:45:17–14:11:51 UTC单次实际完成，进程1593.573秒、JUnit suite1591.251秒、pytest stdout汇总1591.28秒，1390 PASS/0 FAIL/0 ERROR/1 SKIP，退出0。上一完整36模块的全部1271测试标识保留，新增加107后端和13离线页面标识，共1391唯一标识；没有删测或把多窗拼成一次完整结果。401路径在前后、当前文件以及Git源码提交逐字节一致。原两个环境警告保留，无 atexit 清理诊断。唯一 SKIP 是 `test_native_windows_file_backend_gate`，原理由要求Windows11 x64 reparse/ADS/ACL与干净生命周期，不记为PASS。

64件可读原始证据脱敏副本及两端哈希见 [证据索引](evidence/case-cancel-before-receipt-20261011/README.md)。清单 SHA256 `b042b947c119656bd2ee40c4196f78a861070a80ecb7580ced73d144c9b10526`；全部原件/导出/payload SHA、字节大小和JUnit标识/时间/状态已实际核验。14个实际历史失败标识在 [逐项映射](evidence/case-cancel-before-receipt-20261011/failure-map.json) 都有同标识的另次真实PASS；旧FAIL和中断窗口不改签。独审132项与额外11项分别记录，正式 [LIMITED_PASS报告](evidence/case-cancel-before-receipt-20261011/independent/REVIEW.sanitized.md) 的签署时根完整窗尚在执行，这个时间边界原样保留。

完整根窗结束后的独立 [归档审查](evidence/case-cancel-before-receipt-20261011/ARCHIVE_AUDIT.md) 为LIMITED_PASS、无剩余归档阻断，逐件机器记录单独保存于清单之外；64件脱敏输出和计数均按原政策精确复现。审计发现的忽略缓存、静态代码路径粗扫描与1ms时差过严断言按 [证据索引](evidence/case-cancel-before-receipt-20261011/README.md) 保留诊断，未改原测试结果或原件。旧目录当前73文件集和字节均与396602一致。

下一步是父审按该源码SHA、完整窗口、独审与可读证据限定签收；后续若扩大到已有提交/确认/关闭或恢复，须另行冻结范围与并发/副作用合同。本片没有剩余已复现源码阻断，历史跨租户异常原因仍未确认。远端正常推送及最终未提交/未推差异以交付后的Git核验为准，不宣称完整仓库/AT或全生命周期通过。

浏览器 **NOT RUN**：保留历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR`，本任务0次启动或替代重试。Windows/native 仍受原创建票据适配器边界限制。部署、生产迁移、真实模型/付费调用均 **NOT RUN**；未配置凭据/网络，未增加生产 Grant/registry/角色，未扩大权限，未强推或改 protected 分支。

前片61个原始脱敏证据文件及其完整窗口保持，见 [前片证据](evidence/case-cancel-before-accept-20261011/README.md)。前片旧39窗口 stderr 缺失及推断原因、旧 atexit 清理诊断仍按原报告披露，本片不声称恢复缺失原件。
