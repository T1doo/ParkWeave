# 普通受信 writer 的显式激活界面

本片在原单 Run 访问面板补上 ACTIVATE，复用既有激活 API、受信 WriterClient 和原 key 查询；不实现安装器或政策发行器，不创建、发布或采用真实身份、Grant、分派、目录、政策、批准或凭据。正常启动缺少合法配置时仍准确拒绝。PRODUCTION 合同枚举不证明已经正式安装、具有真实来源或通过业务验收。

## 发布中断窗口

先修补 `1259eae7c1369573b36af884583370d8656a4686`：普通写工厂要求 binder 先构建未发布 bridge，调用者附上 runtime scope 后才发布，并在未完成时清理自己持有的 bridge。原 binder 的默认发布行为保留，新增发布参数只接受严格 boolean。

三个回归分别覆盖原 binder 的精确 return trace 中断、调用者属性发布后立即中断、严格参数及旧默认；不以 after-return 的 before_invoke 中断冒充原缺口。此前 a5bd 证据的清理保证只覆盖调用者已收到 bridge 的窗口，本片才覆盖 publication/return 间隙。

这不使保护文件撤回与远程 VALIDATE→COMMAND 原子化，也不替代原 writer 的权限、到期、撤销、幂等和事务最终校验。

## 用户操作与恢复

只有原生 DECISION 状态及视图同时明确启用、两份 authority 期限有效、status.read_only 为 false、视图非只读、PRODUCTION_CONTRACT、writer_history_verified 为 true、activation_enabled/can_activate 为 true、当前企业经办人、APPROVED、尚无实际访问且来源/版本/租约/摘要/UTC 期限完整时显示激活表单。REFERENCE、隔离 fixture、缺标志或坏版本均无激活 POST。

表单展示 Case/Run、资料版本、材料摘要、现有执行者、批准人、决定/Run/激活版本、租约、策略摘要及 UTC 范围。提交同步重核当前条件和显示快照，要求独立确认及非空原因；原因按原模型的 Unicode White_Space 规则归一化。正文严格为既有 Activate 模型九字段，不采用额外用户字段。

POST `/api/runs/{run_id}/access/activate` 后，即使收到 2xx，也只自动发送一次 GET `/api/runs/{run_id}/access/commands/{original_key}`。前端不凭 POST 回执或签名形状认定提交：必须由原历史接口明确 writer_receipt_verified，并核对完整原正文、Run/key/动作/原因、激活版本及原 source/owner/executor/approver/lease/validity，才结清这一请求。随后另读当前状态，历史 receipt 的 true 不赋予当前访问权；已撤销或到期的合法历史仍可核结。

超时、409、422、未观察到、错误 namespace、错误正文/来源/目标/期限/版本、未经验证的结果均保持 UNKNOWN，只允许原 key GET，不自动重 POST，也不建立另一 Run 命令。期限计时器隐藏操作但保留 UNKNOWN 的 GET。迟到 200/403 仍通过原 generation/token/Run 门；实际 token input 清理能阻断 token ABA。

严格历史核结后，仅结清 path/key/token/完整原 body 相同的原 entry 操作；不放宽全局写门或清其他操作。当前 403 或导航清理私有内容时，仅保留本页内存中的 kind/Run/key 编号屏障并显示编号，禁止另发。该编号不是授权或持久恢复凭证；清除正文后的屏障不会仅凭当前状态自动解除，页面刷新也不是旧操作未提交的证明。完整正文仍在内存的 UNKNOWN 可继续用原 key GET。

## 有限验证与保留失败

直接运行 `tests/test_ordinary_runtime_write.py` 的 24 个 unittest，以及 `tests/test_native_run_access_activation_offline.py` 的 45 个 unittest：33 个新增完整页面 NodeVM 激活场景、12 个原 NodeVM 场景。旧脚本与断言不改。合计 69 个唯一方法；独测全重叠，不相加。最终固定 SHA、输入清单、原日志、耗时、独审及远端核对见本片 evidence 中的 validation 和交付回执。

独审先批准设计，继而发现并推动关闭 Unicode 理由归一化和前端 entry 操作未结算两项 P2；最终静审无新增 P1/P2。开发 v1 单个 verified 场景通过；v2 的模块类别名导致 12 项重复，共 53 次执行、41 唯一，5 个 token 用例因 Node DOM 替身缺 classList 失败；补齐替身并移除别名后 v3 的 41 唯一通过。补 P2 回归后的 v4 为 45 唯一通过。原失败和警告逐字保留，开发窗不充当冻结证据。

1259 的独测只执行一次 24 方法，原子进程通过；首版结果解析器受跨行 warning 影响误计 23，汇总失败也保留，修正解析既有日志时未重跑。其镜像 182 项 PRE/POST 零漂移；共享 POST 如实记录后续获准修改的 web.html 一项。

NodeVM 使用完整页面脚本、最小 DOM 与合成 DTO/mock fetch；没有浏览器、网络 API、真实 writer、IPC、PG、安装或实际 assignment。24 方法的 MemoryConnection/protected binder/RPC DI 也不证明真实 writer 权限算法或数据库并发。未启动或迁移原材料专用库，未调整旧源码 pin。

## 普通实际运行仍缺的输入

以下均须来自已有合法记录或以后另获授权的实际配置；本片没有生成或发布它们：

- 已有普通 LOCAL PostgreSQL 应用连接、符合限制的 API 角色及真实来源接线；企业当前 PREPARE、专员当前 REVIEW_ASSIGNED，以及精确 service/version/catalog SHA256/xmin 的合法 preparation_catalog。缺少任一项不得从 IsolatedPlanApproval 或 reference fixture 替代。
- 精确 preparation/Case/Run 与已有来源证明、当前合法主体和能力；本激活接口当前仍要求其原本验证的 SYNTHETIC 本地 Case Run、LOCAL_CONFIRMED 材料和一致 review/material 摘要，不能据此宣称真实正式来源已接通。
- 已依法采用、独立具名且限于该 Run 的 PRODUCTION writer policy、有效来源/主体/期限及独立批准记录和 lease；现有执行者 READ/EXECUTE、企业权限、独立审核权限仍由原 writer 检查。需要原 REQUEST→独立 APPROVE→有效激活策略→本人显式 ACTIVATE，测试记录均不能代替。
- 已安装并受保护的原 writer 程序/进程、分离的 API/writer UID/GID 与数据库角色、精确 IPC/ACL、有效 policy/key 与 endpoint pin；两层 root 保护绑定记录、各自 SHA256 和与当前来源一致的代码 pin；严格 PARKWEAVE_RUNTIME_WRITE_CONFIG，且不与只读配置混用。

普通安装与政策发行的代码/实配仍有后续工作；没有合法文件和服务，仅加入 JSON 或使用本表单不会产生写权限。完成同 Case 全流程还需资源、合法 pack/journal、资源关联、分派本人接单及后续原入口逐步核验，不能预置 assignment 代替。

未进行真实安装、迁移、激活、服务/浏览器/真实模型调用或身份、权限、SQL、IPC、网络配置变更。Windows 正式 AT、无夹具新安装到同 Case 完整 P1–P5 的正式 AT35、真实业务场景、完整 F2 和项目整体均未验证/未完成。main 与旧材料日志、凭据、数据库和固定 ZIP 保持原范围。
