# 来源机会到原局部采纳：实施前合同

本环境从只含初始提交的 `work` 核实默认网络、远端指定分支及 main 后，普通 fetch 到 `6a035ef18f9db54c3563610fe27cd2e27f235747`，新建 `dev/f3-source-adoption-20261015`。main 为 `31e7acb7e53bb1ab6465b9daae59de28757f7583` 且为祖先，保持只读。没有旧进程/工作树或本地 AGENTS.md、.agents/skills；不恢复旧任务。root 为唯一 Git 集成者，后端和独测在分配文件内并行，无第二接续写入者。

依据原产品 §5.3、§5.6、§8 与 F3-T02/T03。已有 IMPORT/REFRESH/IGNORE/WITHDRAW、注册计划局部 ADOPT、VERIFY/LOCK/UNLOCK、目标证据和工作清单不重做。本片只补已有合成 Case 的来源机会进入原计划局部修订的闭环，不签收完整 F3 或原 AT24–27。

## 只读预览与明确采纳

`GET /api/preparations/{id}/opportunities/{card_id}/plan-revision` 在原 active owner、READ/PREPARE、同 Case/Run/tenant 下只读核对。只有最新代 PENDING_REVIEW、实际材料/目录绑定仍当前且目录可消费的卡片能作为定位依据。标题、note、reason 都是未核验文字，不参与事实差异或权限计算。

预览 scope 为 `SOURCE_CHANGE_LOCAL_REVISION_PREVIEW`，绑定 actor、preparation/Case/Run、当前 plan UUID/revision、机会 ledger revision/末事件证明、card UUID/version/basis、原 proposal SHA、实际逐步骤来源及集合指纹，列出直接变化、受影响、保留的稳定 step UUID 和阻塞原因。变更传播采用已有声明边 closure；真实来源与旧本人 VERIFY 来源比较，集合变化沿既有 dependency manifest。不能解释/缺 before/UNKNOWN 来源不得仅凭提示产生可采纳补丁。请求/服务/目录合同绑定变化继续原明确替换，不在本片迁移。

仍向原 `POST /api/preparations/{id}/service-case-plan` 发原 ADOPT，显式 `local_revision:true`，新增可选 `opportunity_proof={card_id,expected_ledger_revision,expected_card_version,expected_basis_sha256,expected_preview_sha256}`。该扩展只允许局部修订，未提供时旧指纹与行为保持。用户先查看分区，再独立明确确认并填写原采纳说明；机会文字不授权采纳，REFRESH 不采纳、不 VERIFY、不复活忽略/撤回/失效卡。读页面/选择卡片/导航不发 POST。

采纳在原事务和准备事项锁下复核当前身份、权限、全部原 goals、请求/资料/计划 revision、proposal 来源、ledger/card/proof 和当前真实来源；陈旧/ABA、撤回、跨 Case/owner/tenant、撤权一律拒绝新写。原 actor/key 幂等先验权限后恢复，同 key 异正文/异 Case 409。已成功旧回执可只读恢复，当前来源资格独立显示，不把历史成功当当前有效。

## 保持与重验规则

仅原计划追加一个 ADOPT 事件，不写机会账本或业务事实，不改 plan/step UUID、六个原必需目标、合同正文、旧事件/历史或未受影响步骤。受影响旧核验快照保留但对当前来源无效，必须再用原 VERIFY 逐步核验实际产物。源数据仍由对应原入口提交/核对，不由机会补丁伪造。

受影响人工锁阻止采纳，须原 owner 明确原 UNLOCK；解锁不重验。未受影响锁及其全部证明保持。原 64 事件和锁预留解锁额度保持，采纳前保证有界事件容量，不降低已有门禁。

独立答案：新增当前 owner 已有授权可选资源影响 P2 及其声明下游，保留 P1 核验/锁；本 Case 材料换版影响 P1 及下游，不能把旧 REVIEW/CONFIRM、接单/回执或生命周期核对当当前产物；其他 tenant 无关变化不影响本 Case。提示文字变化自身不能改变步骤来源。旧计划和六目标持续可读，最终目标结果/工作清单只是当前本地产物证据，无 Case 完成、外部受理或现实履约声明。

## 页面恢复、验证与边界

沿用原 service-plan 11 字段、640 字节、8 槽、24h opaque 恢复句柄，POST 前持久保存，不落正文/hash/token。丢回执、NOT_OBSERVED、解析异常保留未知，只 GET 原 key；冷刷新重认证后不自动重发。身份、Case、版本、草稿及 A→B→A 世代隔离；当前 403 清私有视图且保留句柄，迟到响应不能回填或清新视图。有其他未决写操作时不启动新采纳。

真实完整 HTML 脚本 → ASGI → 自有 PostgreSQL 正向/拒绝、受影响完整模块回归和冻结 SHA 独审分列，失败日志逐字保全。只使用指定环境、合成自有库与锁定依赖；不启动此前被拒的浏览器路径，不改安全配置、凭据、费用或权限。目录等 SELECT-only 管理员的最后读取到 COMMIT 竞争仍按原边界披露，不声称新线性化协议。正常开发分支推送前确认远端与冻结源码，无 main、force push、部署、真实模型。Windows、真实浏览器、正式 AT、真实模型、生产迁移/履约全部保留 NOT_RUN 缺口；现有安全 approval 不改。有界免费 CI 仅用既有适用触发器，不新增工作流或绕过拒绝。
