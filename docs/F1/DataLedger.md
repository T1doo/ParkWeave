# F1来源冻结与痛点假设

来源台账为本轮新建，未收到原材料包/真实园区数据库。

| 来源 | 来源/授权范围 | 完整性/真实性 | 当前用途 |
| --- | --- | --- | --- |
| 两份用户V1设计 | Library指定文件；用户授权保存与项目开发 | docs/sources/V1原件、manifest、字节/行/hash；原API缺1终止LF已核对还原 | 设计要求；不等于政策/真实企业事实 |
| 合成身份与事实 | 本项目tests显式owner setup、自建fixture | SYNTHETIC/USER_ASSERTED_SYNTHETIC，三企业两园区；无实际园区许可声明 | 隔离、Grant、冲突/缺证据、UNKNOWN路径 |
| fixture_effects | 显式FAULT_INJECTION第二事务 | 故障模拟，不是外部服务回执 | 丢响应/核对/去重/失联工程 |
| 合成纯文本文件 | 管理员自建UTF8 fixture≤16KiB | SYNTHETIC_FIXTURE，UUID/size/hash/私有目录；无宿主导入 | 路径/下载/注入/权限工程 |
| 官方接口说明 | ModelBoundary中公开官方文档URL，2026-10-05核对 | 协议字段说明；没有调用模型或拿到Park回包 | 离线HTTP边界格式；不作为实际模型效果 |
| 原生Windows资料 | 用户自报Windows11家族 | 精确构建/架构/服务/安装权限未实测，NOT_RUN | 后续原生验收准备 |

业务痛点假设来自用户设计：企业诉求需跨服务、材料、资源与角色协同；信息冲突/缺证据和变更需要核验。它们尚无真实访谈、基线时间、完成率、真实目录/许可或收益数据支撑，不能称真实试点效果。F1-T06冻结字段和测试来源，不以合成通过替代AT-31/32后续真实比较。

## 2026-10-18 AT32 无试点披露修订

上段为 F1 历史记录，末句把 AT31 真实比较与 AT32 来源披露合并，范围过宽。本修订明确取代该末句的门判断：AT31 的真实效果比较需要其适用输入；固定 AT32 允许没有真实试点时核查输入、输出、反馈和报告引用，如实披露无证据即可。合成、MOCK、FAULT 和冻结证据 REPLAY 可按原方案用于各自适用的技术验收，不都等待正式来源合同。

| 当前类别 | 来源与本次使用范围 | 原执行类型与可支持的主张 | 缺项／限制 |
| --- | --- | --- | --- |
| 用户设计／衍生规格 | 两份指定 Library V1 原件及其 manifest，用户授权本项目保存、开发和核查；衍生设计／固定 AT 是项目文件 | USER_DESIGN_ARCHIVE；原件字节核对与要求追溯 | 本地恢复 LF 后 hash，无独立上游 hash；不建立真实政策／企业事实，也不推断公开再许可 |
| 自建合成初态与输入 | tests、普通 LOCAL_SYNTHETIC_DEMO 合同及受审 DOM 记录；身份、Grant、目录、分派属于显式测试初态 | SYNTHETIC_FIXTURE；普通本地 HTTP／PG／Chromium 工程，demo producer 明示 NO_MODEL | 自动化角色 REVIEW／CONFIRM 不是园区专家或真实用户批准；不授予普通正式来源权限 |
| 模型模拟输出 | F1 http-smoke 与 ModelBoundary 的历史及 ENG007 更正 | MODEL_MOCK；字段形状、离线控制、LOCAL_CASE_CREATED | 没有本次 LIVE 调用或真实效果证据，不能把本地成功当外部受理 |
| 故障输出 | eng003-gateway-smoke 的 SIMULATED_RECORD；最近旧403延迟交付记录 | FAULT_INJECTION；前者模拟效果，后者本地真实 HTTP 加运输注入 | 旧403不是当前执行者撤权；模拟／注入不证明外部履约 |
| 材料包／人工动作记录 | 实际合成下载文件与来源 preview／provenance，保留 SYNTHETIC 标签、版本及 SHA | NO_MODEL／LOCAL；导出字节、独立副本及自动化审核路径 | 包明示真实性未核验、政策 UNKNOWN、外部 NOT_SUBMITTED、目标未完成；不是有效资格或真实收益 |
| 协议／文献引用 | V1、DocumentReview、ModelBoundary 中既有公开 URL，仅追溯设计／协议参考 | PUBLIC_REFERENCE_ONLY；本次不访问、不验证现时规则或模型服务 | 既有核对日期不升级成本次实测；Sim2Act 原件／代码未收到，第三方再利用权不推定 |
| 使用反馈与价值指标 | 本受审包未提供真实园区试点、访谈、用户满意度或独立外部专家反馈；代码独审和脚本角色动作另列 | NOT_PROVIDED；只能报告技术测试和代码核查 | 无完成率提升、节时、收益或真实上线证据；不存在可据此计算的效果数字 |
| 本次 AT32 核查 | 冻结包、原证据逐项阅读与 hash 核对 | REPLAY + MANUAL_REVIEW_BY_CODEX；原执行类型另轴保留 | 核查不是新的产品运行、真实用户反馈或现实部署；Windows／LIVE／真实履约未执行 |

本次有限受审文件及逐项引用见 `../F2/AT32SourceDisclosureCase-20261018.json`；范围为该发布说明使用的来源类别、代表性输入／输出和列明报告主张，不声称逐条语义审计全仓历史附件或验证所有第三方 URL。新增来源或效果主张必须重新核查。缺失真实材料与许可被明确记录，不用测试 fixture、普通只读批准或 IsolatedPlanApproval 填补。
