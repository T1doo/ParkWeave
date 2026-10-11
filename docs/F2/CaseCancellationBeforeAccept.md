# 普通合成 Case 首次接单前取消

从原远端 `dev/f2-resource-alternative-times-20261011` 的 `e40bd24329ec21bd881ee7521e63e32a8ee3c13a` 建立独立开发分支 `dev/f2-case-cancel-before-accept-20261011`。本片对应原产品 §5.5、§7.1、§7.4 的有限撤销流程；不等于完整 Case 生命周期。

完整源码及测试提交为 `557528da70d905859d7fd09dc0b4ed8f5545af51`；功能源码首次提交为 `4d1967ab7691a7dc3203c5214fb1fbe95ceba34c`，之后仅修正模板测试的显式局部采用流程。398 路径最终清单 SHA256 `5571352ab2d645d7739f4e727c2ba1188d169c919c3109bc263aec0c3592100b`，交付前零漂移。扩大回归之后 125 个产品文件没有变化。

已有资料的普通 SYNTHETIC Case，原建单 Run 必须 SUCCEEDED，原 operation 必须 VERIFIED，精确建单回执及来源指纹必须核实。未分派、OFFERED、DECLINED、WITHDRAWN 可取消；任何历史实际 ACCEPT、receipt 步骤、本地关闭历史、隔离执行或不支持的来源均拒绝。取消后恢复、首次接单后或履约后取消不在本片范围。

企业原 owner 每次按当前 READ/PREPARE 授权读取，提交还要求 EXECUTE；请求绑定精确 Case UUID、资料修订、生命周期修订、来源 SHA、明确布尔确认和非空原因。取消状态与不可变事件同一 PG 事务提交。同 key 同参返回原结果，异参冲突；原事件与当前持久状态不一致时拒绝成功回放。客户端丢响应后只 GET 原 key，NOT_OBSERVED 保留未知句柄，不自动重发 POST。句柄最多八个，只保存 actor/Case/事项/key/修订/期限，不保存正文、原因或认证令牌。

| 入口或旁路 | 取消后的行为 |
| --- | --- |
| 原材料命令、用途声明/确认、事实包、整理草稿、复用目标、诉求、准备度、机会、资料异议 | 现有授权及 parent 锁之后，明确业务写守卫拒绝 |
| 计划采用/命令、局部修订/人工锁、计划 Approval、模板升级选择 | 拒绝业务写；历史 GET 不追加隐式失效事件 |
| 分派/再次分派/交接、执行者 `_parent` ACCEPT/DECLINE、旧 receipt CREATE、receipt `_parent` 命令 | parent → dispatch 顺序锁定后拒绝；检查全部实际 ACCEPT 历史 |
| 资源关联、方案关联确认、组合交付内部 `_bind_locked` | 拒绝 Case 关联/交付，保留旧预约、claim、link 和容量占用 |
| 本地验证/关闭/重开、P1–P5 隔离预览实际执行 | 拒绝；已有有权历史读取保留 |
| 原 outbox 消费、通知列表/打开 | 重查 Case，未投递旧通知 SUPPRESSED；既有通知历史可读，不再可接单，不伪造 WITHDRAW |
| 原独立占位释放/组合取消 | 按原当前资源权限独立执行，Case 取消不会自动释放 |

`scoped(write=True)` 仍用于部分 GET 的 FOR UPDATE 序列化，新增 `business_write` 独立表达实际业务写。普通业务写持有 parent SHARE/UPDATE 至事务结束，随后纯读 Case 状态；取消取得 parent UPDATE → dispatch UPDATE → Case UPDATE → 本地账本 UPDATE。资源操作原锁序保留。parent 锁同时保护尚不存在的首次 dispatch/receipt；真实 owned PG 等待分别验证取消先/ACCEPT 先，以及材料、首次分派、方案采用、资源关联双向竞争。

schema 30 只扩展原 Case/本地生命周期状态和原事件 action CHECK，不新建 Grant、registry 或权限。只允许具有当前原签发创建票据的自有 Linux 临时合成 PG 安装；保留的旧 schema 29 没有该票据时不迁移，接口明确报未安装。原 Windows/native 安装路径未扩大。schema 29 手工回执交接在 29/30 保留，同时明确要求原 29 前置存在。

页面确认明确说明不可恢复、原成功建单及历史保留、预约仍占容量及独立释放入口。历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 原样保留；本任务未启动浏览器、未换 URL 或工具重试。实际 UI 验证限定为离线 NodeVM DOM/fetch doubles 和完整脚本语法检查。

| 实际验收窗口 | PASS | FAIL | ERROR | SKIP | 范围及后续核对 |
| --- | ---: | ---: | ---: | ---: | --- |
| 根任务取消专项 | 86 | 0 | 0 | 0 | 77 项真实 PG/ASGI，9 项离线 NodeVM |
| 根任务扩大回归原窗 | 1227 | 4 | 39 | 1 | 36 个完整相关模块；原失败完整保留 |
| 根任务事实澄清复验 | 66 | 0 | 0 | 0 | 修正两项旧 schema 测试 Oracle，保留原迁移拒绝 |
| 根任务模板完整复验 | 33 | 0 | 0 | 0 | 原错流在基线和本片均复现；只修 fixture 显式 ADOPT/CAS |
| 根任务 API/worker/授权/机会复验 | 82 | 0 | 0 | 1 | venv 安装缺失构建工具和项目后，三个完整模块复验；原生 Windows 项跳过 |
| 独审冻结原窗 | 270 | 2 | 0 | 0 | 两项旧 schema Oracle 失败，原窗不改签 |
| 独审事实澄清复验 | 66 | 0 | 0 | 0 | 完整模块独立新 PG 窗口 |
| 独审额外边界 | 7 | 0 | 0 | 0 | legacy receipt 实际锁等待、旁路、冷读及原因权限 |
| 独审模板补审 | 35 | 0 | 0 | 0 | 完整模板 33 项及原错流/修正保权历史 2 项 |

独审结论 **LIMITED_PASS**，绑定上述完整源码/测试 SHA，无本限定切片剩余审查阻断。各窗口分别记录，不相加为单次全通过。按相同测试标识取扩大原窗与三组复验的最新结果，1271 个唯一标识中为 1270 PASS、1 SKIP、0 FAIL/ERROR；这是多窗口索引。初期产品缺陷、审查夹具错误、集合错误与基线失败的原记录及哈希均在机器证据中。

安装后进程复验退出 0，但结果后有 `pgserver` atexit 清理临时 `pg_wal` 的 `FileNotFoundError`，原 stdout 完整保留；后续检查对应数据目录已不存在且无存活测试 PG 进程。该诊断独立记录，不能把此窗口表述为无清理异常。唯一 SKIP 要求原生 Windows 11 x64 的 reparse/ADS/ACL 与干净生命周期。

最终源码 SHA、独审、实际测试结果和各失败窗哈希记录在 [机器证据](CaseCancellationBeforeAcceptEvidence.json)。原失败 stdout/JUnit 留在本地 `.runtime/case-cancel/`，不以失败窗成绩替代最终版本，不将测试生成的临时认证值写入交付文档。全仓测试、真实浏览器、Windows/native、完整原 AT、生产迁移和部署均未执行；后续在既有授权范围补足这些验收前提，再评估完整生命周期。
