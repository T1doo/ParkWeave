# 当前真实启用审查合同：未授权、未执行

审查对象是冻结源码 `a1e602238606d4e20c0a42e4dbb5be900113675f` 的精确 Run READ 桥及接单一致性元数据报告。此文档是待审合同，不是安装脚本或启用指令。当前状态 **NOT_AUTHORIZED / NOT_INSTALLABLE_ON_NORMAL_CONFIGURATION**；所有真实主体、对象、安装目标及期限仍待负责人明确。测试通过不能补全这些字段。

## 必须明确的对象和责任

| 项目 | 待审的具体合同 | 当前状态 |
| --- | --- | --- |
| 主体 | 已有企业 owner、独立访问审批人、同租户执行者的精确主体 ID；审批人独立于申请人/受益人 | 未指定；不创建账户，不从资料 REVIEW 推导审批权 |
| 范围 | 一个 park/org/Case/Run，READ 能力，明确 UTC 起止及权限版本；不得使用通配范围 | 未指定；不能复制夹具许可或 lease |
| 审批动作 | 原 REQUEST、独立 APPROVE、REVOKE；审批来源版本与实际访问投影逐次重验 | 普通配置默认关闭；来源与 PG 非原子，投影未完成须保持拒绝 |
| 办理对象 | 原资料准备、明确 OFFER/本人 ACCEPT、唯一回执步骤；材料版本/hash 与当前整份租约绑定 | 需真实合法记录与原有动作权限；READ 不授权办理写入 |
| 软件成果 | `synthetic.accepted-handoff-report` v1，仅 `LOCAL_SYNTHETIC_HANDOFF_REPORT_CREATED`；企业独立 ACK | 合成接单一致性元数据；无服务履约、资格、机构受理或目标完成含义 |
| 安装 | 精确数据库/来源存储/运行主体、创建与生命周期证明、最小 schema 写权限及维护责任 | 当前仅支持自有全新临时夹具的同进程发行证据；正常持久安装路径尚缺代码和审查 |
| 数据生命周期 | 报告、访问审计、材料及历史的合法保留范围、备份、停机与恢复责任 | 临时体验正常关闭即删除；不能当持久交付环境 |

## 开关与接口的当前事实

普通 `parkweave.api:configured_app` 不安装桥或执行 provider。`GET /api/run-access/status` 在原身份/READ 校验后返回关闭状态；精确 `/api/runs/{run_id}/access` 和 `/access/commands` 无桥时拒绝。`POST /api/executor-receipts/{step_id}/execute-local` 无 provider 时在数据库/计划检查前拒绝。

Linux 临时体验需启动器同时显式收到 `--enable-isolated-run-access --fresh-fixture --enable-isolated-local-execution`，且同进程创建证明、数据库端点及发行字节匹配。它不能通过一个环境变量变成正常安装，不能对既有库套用测试证明。启动器可在自己的新夹具上增加 nullable `service_step_receipts.adapter_execution`；此行为不授权对真实数据库迁移。用户体验方法见 [CurrentRestrictedExperience](CurrentRestrictedExperience.md)。

真正安装前，应另行交付可审查的持久安装生命周期实现、精确对象清单、最小权限差异、当前授权证明及撤销/恢复核验方案，再由有权负责人审查具体操作。此文档没有 SQL GRANT、数据库手改或绕过证明的替代路线，也没有执行任何真实启用。

## 需要审查的风险与验收边界

访问扩大可能暴露同一 Run 的企业私有记录；审批来源与 PG 投影不同步可能造成假成功显示；租约过期、主体停用或撤销后旧报告不能继续作为当前证据；重试必须绑定原 key/正文，不能从响应丢失推断未提交。服务端同事务成果只覆盖这项元数据生成，不能证明任意外部副作用可回滚。

报告和 ACK 均不能使 Case FULFILLED。原 PR0 的业务成果应来自用户明确原目标、注册服务承诺的实际交付及独立核验/反馈；现有接单存在性不满足这些判据。当前逐项差距见 [PR0-CoverageAt-a1e6022](PR0-CoverageAt-a1e6022.md)。下一项离线价值应围绕原目标与实际资料/交付缺口，而非增加接单存在性报告；具体范围留在本轮冻结回归和用户说明完成后确定。

本轮模型预算 0、R4 关闭，不执行模型调用、真实 Grant/凭据/owner ACL/security 修改、部署或 main 合并。F1 未签收、F2 并行探索；Windows Server 工程测量不是 Win11 原生验收。原环境和备份保留。

本候选完整 Linux 工程回归为 2422 PASS、9 native SKIP、0 FAIL；原始证据见 [冻结证据索引](../integration/PR0-a1e6022-FrozenEvidence.json)。这不授予真实启用权限，不代表完整 PR0 签收。
