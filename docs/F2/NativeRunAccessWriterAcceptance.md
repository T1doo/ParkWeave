# 独立 scoped writer 交付验收

可复核源码：`b1f241182ec8d44f64a8e7ea5d782472590c0b00`。基线 `9ea666620bdf9b88bca395e7ccf471ec7901a038`；其祖先原资源分支 `e40bd24329ec21bd881ee7521e63e32a8ee3c13a`。正常独立开发分支 `dev/f2-native-run-access-writer-20261012`。本片推进原普通 SYNTHETIC Case 协作链的默认关闭政策合同及独立 writer，并复验首次接单前取消、写入口封锁、历史和资源边界。不是完整 Case 生命周期或生产启用。

## 已实现

当前企业 owner READ/PREPARE/EXECUTE、精确 Run/Case/资料与权限版本、原键、原因和严格确认；具名同租户已有独立 park_specialist 明确 APPROVE/REJECT/REVOKE，一名已有 service_executor 的限定 READ。UTC 最长一小时，审批只缩短，一份 policy 一次 REQUEST，不续授、不覆盖 legacy/isolated assignment。

API 仅原 app 连接和受信公开 scope/pin；拒绝私有 writer Context，无 owner DSN/签发 key。独立子进程内部再验真实 session、当前权限、版本和来源，事件与 assignment 同一 PG 事务；HMAC 签发完整 typed command，验证双端点/有界线程，按原 parent → native Run → assignment 顺序。旧 APPROVED、assignment、test permit 和伪造 app JSON 不自建权威。生产 configured_app 保持关闭，reference CLI 拒绝 PRODUCTION。

取消后历史/Run 成功事实与资源占用保留；业务写仍由原 Case 服务端守卫拒绝。资源不自动释放，原独立释放/组合取消按原权限操作。真实 API、writer 与同 physical PG stop/start 后只能明确 rebind 原 policy/key/pin，期限不变；无通道/换 key/换库默认拒绝。元数据参与者按受信 scope，原键 GET 区分 raw history 与认证状态；页面只有原正文和认证均可核对才清 UNKNOWN，无自动 POST。旧普通 Native 默认 null 确认不改变旧指纹。

[业务/技术合同](NativeRunAccessWriterContract.md)与[待决生产安装/权限方案](NativeRunAccessWriterInstallationPlan.md)说明具体有限边界。

## 最新实际执行

| 窗口 | PASS | FAIL | ERROR | SKIP | 唯一 ID |
|---|---:|---:|---:|---:|---:|
| root 25 个完整相关模块 | 1070 | 0 | 0 | 0 | 1070 |
| 独审：完整 writer/NodeVM + 自写 PG 反例 | 78 | 0 | 0 | 0 | 78 |

root 实际 2026-10-12 06:26:27.030879–06:37:22.489495 UTC，exit0，655.459 秒；416 个源码/合同文件首尾零漂移，源码清单 SHA256 `84df792b3331214c01f0454ec74390c801573d65c9a05a00fe75175156428cc8`。独审独立 86.142 秒、420 文件及 probe 零漂移；两者精确重叠 68 ID，另有 10 个独立 ID，不能相加冒充同一窗口或互不重叠覆盖。

真实 owned PG/ASGI/子进程验证包括：权限/跨租户/owner 确认、合法未签 JSON 及跨 Run 指纹投毒、同异键/CAS 并发、事件/assignment 故障全回滚、八 writer 命令真实 parent 排队时 VERIFY 与业务 commit、ACCEPT/REVOKE 两种锁序、锁等待后的资料/期限变化、业务提交到期回滚、旧通知与迟到 UI、Case 取消后容量及独立释放、原 P1–P5 人工本地链与显式方案修订、API/writer/PG 真重启、撤权/重授不复活、真实 9ea 旧 receipt 同键兼容。SQLite 仅用于既有隔离候选模块回归，不替代上述真实 PG 锁验收；页面为实际脚本离线 NodeVM，未启动浏览器。

root 完整模块（实际 argv）：

- `tests/test_native_run_access_writer.py`
- `tests/test_native_run_access.py`
- `tests/test_native_run_access_activation.py`
- `tests/test_native_run_access_offline.py`
- `tests/test_case_cancellation.py`
- `tests/test_case_cancellation_before_receipt.py`
- `tests/test_case_cancellation_reconciliation.py`
- `tests/test_case_cancellation_offline.py`
- `tests/test_preparation.py`
- `tests/test_service_dispatches.py`
- `tests/test_executor_receipts.py`
- `tests/test_dispatch_notices.py`
- `tests/test_dispatch_notice_pagination.py`
- `tests/test_dispatch_notice_page_offline.py`
- `tests/test_case_resources.py`
- `tests/test_resource_combinations.py`
- `tests/test_case_resource_delivery.py`
- `tests/test_case_lifecycle.py`
- `tests/test_case_lifecycle_recovery.py`
- `tests/test_case_goal_results.py`
- `tests/test_service_plan_manual_lock.py`
- `tests/test_service_plan_recovery.py`
- `tests/test_case_path.py`
- `tests/test_f2_t07_full_chain.py`
- `tests/test_isolated_run_access.py`

原始 JUnit SHA256 `010ed6e2a854d472bb5984ca0aead4b9f1974eb20e58afa3d20418c6c2f48a6b`；原始 stdout `23d81b05037cce05fc7f7db5afdfb99860cacb4ce4ed10d676aa70d71f8daf16`。[根运行记录](evidence/native-run-access-writer-20261012/root/frozen-final-actor-guard/run.json)、[JUnit](evidence/native-run-access-writer-20261012/root/frozen-final-actor-guard/results.xml)、[结果/原失败映射](evidence/native-run-access-writer-20261012/root/delivery-result-summary.json)和[独立限定审查](evidence/native-run-access-writer-20261012/independent/DELIVERY_REVIEW.md)均可查。独审原报告中 root RUNNING 是签署当时事实，原样保留；最终 root 完成由上述独立根记录证明。

## 失败原样保留

下表是各自真实窗口，P/F/E/S 分别 PASS/FAIL/ERROR/SKIP；开发窗口有各自源码清单，不能转为最终源成绩。

| root 窗口 | P / F / E / S | exit |
|---|---:|---:|
| actor-before-cas-repair | 10 / 0 / 0 / 0 | 0 |
| child-interpreter-repair | 5 / 0 / 0 / 0 | 0 |
| cross-run-key-reproduction | 0 / 2 / 0 / 0 | 1 |
| expanded-writer | 38 / 3 / 0 / 0 | 1 |
| fixture-registration-repair | 0 / 0 / 5 / 0 | 1 |
| frozen-final-actor-guard | 1070 / 0 / 0 / 0 | 0 |
| frozen-related-final | 219 / 1 / 0 / 0 | 2 |
| frozen-related-regression | 1052 / 0 / 10 / 0 | 1 |
| independent-boundary-repair | 79 / 12 / 46 / 0 | 1 |
| initial | 0 / 0 / 5 / 0 | 1 |
| metadata-recovery-legacy-repair | 5 / 0 / 0 / 0 | 0 |
| partial-frame-capacity-repair | 1 / 0 / 0 / 0 | 0 |
| request-api-dto-repair | 137 / 0 / 0 / 0 | 0 |
| review-defect-repair | 7 / 1 / 0 / 0 | 1 |
| signed-body-ui-compatibility | 23 / 0 / 0 / 0 | 0 |

两轮初始夹具 ERROR 为缺 fixture 注册及子解释器错误解引用，未安装依赖；扩展三 FAIL 为 SQL 伪造样本先被原状态机拒绝及错误 health 路径。DTO 轮 12 FAIL/46 ERROR 是新增字段被旧 API 入参拒绝；跨 Run 原键旁路真实修前 2 FAIL；压力轮一次 socket backlog errno11 拒绝已保留、停止该连接动作，不重试或扩大权限。77e 广窗 JUnit 为 1052 PASS/10 teardown ERROR（stdout 1062 passed 另含10 teardown错误）；旧 T07 输出文件存在，原证据未覆盖，最终为每轮独立 evidence 目录。3824 窗已有 nonowner/CAS 1 FAIL，安全停止该失败窗口，220 个已执行 ID、exit2，剩余项未执行。

独审原 7 PASS/2 FAIL 确认未签 target 元数据泄露和原键认证缺失，实际旧 receipt 1 FAIL 确认 null 指纹兼容回归；3824 独审 77 PASS/1 FAIL 确认权限/CAS 顺序。最终相同失败 ID 全部 PASS，保留原 BLOCKED/原始来源。[独审旧报告](evidence/native-run-access-writer-20261012/independent/PRE_REPAIR_REVIEW.md)。独审 wrapper 首次过严 clean 前置退出（pytest/PG 未运行）、9 PASS/51 setup ERROR 的 workspace 目录契约拒绝及三个旧模块加载/前置 1 FAIL 窗均另分类；守卫未修改，被拒创建动作停止，后续使用原允许 /tmp UUID 自有夹具。所有 raw 的哈希与脱敏副本在[归档清单](evidence/native-run-access-writer-20261012/archive-manifest.json)，失败仍失败。

## 推送前诊断清单维护（另一个源码/执行窗口）

业务代码与两个合同仍逐字节等同上面的 b1 源码。随后 `9ed74263e74ee534930076f5e74b59f65f5c7ede` 只更新 `scripts/windows_ci/diagnostic-test-ids.json`：1886→1918，新增32个本片已有 AST 测试函数名，无移除，不接受参数数据，不是 API 权限或业务 Grant/registry。完整 CI diagnostics 纯 unit 模块先实际58 PASS/1 FAIL复现名单缺项，维护后59 PASS/0 FAIL/ERROR/SKIP，source416零漂移；不启动PG。原通用runner scope标签须按此实际范围理解。[补充来源映射](evidence/native-run-access-writer-20261012/support/diagnostic-source-mapping.json)。独立同模块另实际59 PASS，全部59 ID与根诊断窗重叠；[QA尾片独审](evidence/native-run-access-writer-20261012/support/independent/qa-tail/QA_TAIL_REVIEW.md)。此59与b1广窗1070/独审78分开，不声称同一次执行；原失败及原b1签署不改。

[独立归档审计](evidence/native-run-access-writer-20261012/support/independent/archive-audit/ARCHIVE_AUDIT.md)实际核1989 core，24 JUnit与31 static，旧3022全集/Gitbytes零变化。core SHA256 `f1422bc5247062b640ebcaf538b22a9a053d305a64c8c87c78c39fdd6a8ed6fe`保持。支持出口另有52件闭集，不递归增加core；[支持哈希清单](evidence/native-run-access-writer-20261012/support/support-manifest.json)。首审计oracle遗漏旧根文件的exit1、QA维护后严格b1/current源断言的预期exit1均原样保留并分类；这些不是业务测试成绩。CI尾片JSON身份name/classname等按实际JUnit字面保留，未用路径脱敏改名。

## 未运行与下一步

本片未执行全仓 4384 基线，不把此前其他源码分数转签。本次选定25模块全 PASS；其他模块 NOT RUN。生产安装/真实生产 assignment/技术权限扩大/新增真实 Grant 或 registry/部署/付费模型/Windows 原生 IPC/完整正式 AT35/PR0/LIVE 均 NOT RUN。浏览器 attempts=0；历史 Chromium data: `ERR_BLOCKED_BY_ADMINISTRATOR` 未重试、未换 URL/工具。

原 main=`31e7acb7e53bb1ab6465b9daae59de28757f7583`、dev/f1-foundation=`b58cf201de3d6ca4e249bec3e8544ea53163807a`、资源 e40 与 activation 9ea 远端不改。交付仅正常独立分支 push，最终完整交付 SHA 与远端一致性由交付消息及实际 Git 核对给出。

下一步先确定真实生产具名身份、受保护 policy/key/pin、数据库对象/最小 DML 或窄函数及 Windows 传输方案，形成具体差异再另获安装授权。当前 reference 合成 PASS 不证明同 UID 的生产 OS 隔离，实际生产受限 writer 尚未安装/验证；默认关闭维持，无本片开发能力阻塞。
