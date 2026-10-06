# ENG036 固定合成协作模板：设计收敛

基线c2425a047d58fd49e5eb8ab6de205b6c4fe237fc。本轮交付设计与既有离线合同/持久计划验证，不实现新模板执行器或数据库表。原依据：[产品§5.2、5.4、6.3、6.4、7](../平台产品设计.md)、[F2-T02/T06、AT07/08/14/35](../分阶段开发计划.md)。808PASS是ENG035既有范围，不能签收本轮模板或完整F2。

## 原定义与实际差距

已有V1ServicePlan检查有限DAG、目标覆盖和服务版本锁；API明确STRUCTURE_ONLY、executed=false。ActionSpec只注册case.create/1，责任角色只支持enterprise_operator；不能把四个case.create包装成材料/资源/分派/回执执行。已有model_plans持久revision1→2是单动作建Case的离线规划/回执反馈，不能当复合ServicePlan或模板存储。当前资料/资源/分派/回执分别有持久版本和权限，但没有通用CaseStep身份/状态/前后置核验、统一受控适配器、不可变审核模板、参数实例化和计划级失效/恢复协议。

原模板要求审核后参数化服务包，新企业/材料重新授权核验，不能复制旧身份、授权、材料和结果。现有新Case/SYNTHETIC fixture只证明隔离；新Run执行者assignment仍由fixture owner准备，尚未形成无需手改DB的完整冷会话产品入口。原目标不得因缺服务从覆盖中删去；实际履约、外部受理、真实资格核验等不受本模板支持，必须显式列为unsupported/阻塞，不用本地记录完成替代它们。

## 建议实现边界与固定合同

仅一个草案release `synthetic-preparation-coordination/1`，四个稳定步骤P1—P4，固定单链P1→P2→P3→P4；不开放用户自定义边、脚本、任意工具或模型自动动作。下表的适配器名称是拟定义的可信绑定，尚未注册为ActionSpec。每一步都是用户显式调用已有业务动作；计划只组织前置和当前证据，不替用户确认/接单/核对。

| 步骤 / 拟绑定 | 当前负责人与操作 | 前置 / 交付及独立完成检查 |
|---|---|---|
| P1 材料准备 / preparation/1 | 企业owner补两槽材料，当前reviewer人工核对，owner确认 | 当前Case/Run、两槽来源/version/hash；当前LOCAL_CONFIRMED及review_sha256匹配；资格仍NOT_EVALUATED。 |
| P2 资源组合 / case-resources/1 | 同一owner预检、占位、确认本人两个不同资源并显式关联 | P1当前；组合与Case归属、当前资料rev/hash一致，两成员均确认且区间未结束/未取消；以锁后DB时钟判定CURRENT，预检不算完成。 |
| P3 分派与本人接单 / dispatch/1 | 当前reviewer分派；已有合法Runassignment的指定执行者本人接受 | P1/P2当前；offer固定当前资料rev/hash，ACCEPTED/current_offer及实际accept actor一致，同事务唯一receipt step；OFFER/DECLINE/WITHDRAW及通知/已读均不算完成。 |
| P4 回执核对 / executor-receipts/1 | 接单本人提交合成回执；当前owner核对或纠错/重开 | P1/P2/P3当前；当前receipt version/hash与LOCAL_ACKNOWLEDGED事件一致，无待纠正或重开；仅本地合成核对，case_goal_completed=false。 |

实例只接收新输入：当前已授权Case/Run引用、目标原文与完整required_goals、两槽新材料来源、当前可读服务版本、本人资源/UTC区间/数量、当前已有合法reviewer/executor候选。身份/tenant从当前授权解析，不信客户端tenant；旧计划/Case/材料/预约/回执ID不得作为“克隆模板”输入。允许重读本实例已有记录以恢复，不把其它实例结果带入。首片可绑定新建但已具备合法访问关系的合成Case，不声称解决新Run自动赋权或真实冷会话。

计划必须锁住template release版本+canonical hash、服务目录精确版本、四个可信适配器版本和验收suite版本。每个已确认步骤另存来源ID/revision/hash与责任绑定；资源检查包含资源ID/revision及当前capacity/buffer/open区间/enabled、组合/成员/归属及预约区间，不以通知送达替代业务证据。保存request_ref、plan_id/revision、完整目标覆盖/unsupported、typed input映射、责任与交付/检查。每个原必需目标必须有四步中可证明交付的覆盖或明确unsupported理由；任何必需目标unsupported则计划整体BLOCKED，不可确认可执行。草案不是现有V1 schema的扩展实现，不用虚假覆盖step ID通过原结构校验。将来持久计划用tenant/Case范围、不可变修订、服务端fingerprint、scoped idempotency key和expected_revision CAS；不挪用case.create的model_plans伪装复合计划。

计划读取重查当前READ、tenant/Case参与范围及既有PREPARE/REVIEW_ASSIGNED或Runassignment；不把EXECUTE加成统一只读门。推进按对应原业务写入口检查其所需当前角色、能力/资料/资源授权；仅该入口既有要求时检查EXECUTE，不给专员/执行者新增此能力。恢复重读与继续写入分别沿用读/写门，计划不是Grant缓存。写路径须在现有业务事务内锁定计划版本与源依赖再验证当前权限，避免页面检查后失权/改版的TOCTOU；各业务仍分事务，不承诺整条链一次提交。拟新增受控模板推进入口拒绝越序；现有人工入口的独立记录必须重验后才能成为本计划证据，不能仅靠UI按钮禁用保证依赖。

读投影按角色和本人获派步骤裁剪，READ/参与Case不等于全档案权：owner只见本人原入口可读数据；reviewer只见其资料/分派范围，资源仅返回授权范围内的前置是否当前；executor只见本人P3/P4的原分派/回执允许字段和最小前置状态，不带两槽正文、资源输入/快照、完整企业目标或其他人的责任。任何源无权则隐藏字段或拒绝，不用计划缓存作旁路。

首片不新增完整Approval：计划确认只能是本地前置检查，不等于执行授权或原§7.4 Approval。若后续引入一键发起/等价业务Approval，必须另绑定plan fingerprint、Run/Case/当前操作者、单调授权版本、有效期和关键源版本，提交时锁后重验且失效须重新确认；当前没有统一授权epoch/完整Approval表，不能用CAS或grant快照digest冒充，继续逐次既有人工授权。

拟锁序：当前actor身份授权锁→计划头CAS锁→原业务来源锁；禁止已有源锁事务反向再取计划锁。跨源重验沿现有case_lifecycle顺序：preparation→dispatch→receipt→resource UUID排序→组合/成员→Case，末锁后采DB时钟；现有幂等锁与参与者授权检查沿原业务路径，不重新排列为资源先于dispatch。适配器必须共享原业务事务连接，不能用独立事务的提前检查代替；将来实际实现前以O5/O6并发现有人工入口验证锁序兼容，未验证不能称已具备事务执行。

## 输入变化与恢复规则（冻结建议）

P1材料/来源版本或人工核对/确认变化：P1须当前核对确认，P2—P4计划证据标NEEDS_RECHECK；不删旧证据，不自动重发、撤回接单或释放资源。P2区间/数量/组合变更、取消或时间结束：P2—P4须重验；已持久接单与回执保留为历史，不假装未发生。P3拒绝/撤回/新offer或参与者撤权：P3/P4失效；已有接受后handoff不支持，BLOCKED等待规则。P4纠错/重开/新receipt版本：仅P4失效。上游恢复原字节也不自动复活旧确认，需当前身份显式重验；幂等重试只返回原结果及当前状态，不绕权限。

角色/tenant/授权变化：不可访问的数据立即隐藏/拒绝，计划不转给新身份、不新增grant。临时锁忙或进程崩溃保持可重验状态，重启由当前DB记录恢复，不当业务失败或自动重执行副作用。模板发布新版本不迁移在途实例；破坏性不兼容拒绝，旧release/hash与历史保留。计划最终仅LOCAL_RECORDS_CHECKED；Case状态另由既有明确授权入口决定，不自动关闭或FULFILLED。

## 拟实施确定性验收（不是本轮通过成绩）

| Oracle | 未来可执行首片必须满足的独立断言 |
|---|---|
| O1 合同 | 唯一四步/无环/完整目标覆盖、固定版本hash、拒绝未知字段/脚本/动作/越序；不支持目标明确阻塞，零业务写入。 |
| O2 新实例 | 两tenant新输入各有新plan/Case/材料/预约/回执标识；旧来源与授权不复制，不自动赋权；非法旧引用零业务写入。 |
| O3 正常链 | 实际PG/API四步依次完成，逐项查询原业务行/版本/actor/hash；计划结果仅本地记录，不靠构造器自身作为oracle。 |
| O4 失效 | 分别改变P1/P2/P3/P4，精准标记下游需重验、旧决定保留、无自动重发/释放；回到原字节不自动复活。 |
| O5 当前权限 | 三角色/tenant/撤权前后及检查后锁等待撤权：GET/推进/恢复均按当前权，未授权无副作用或内容泄漏。 |
| O6 CAS/崩溃 | 同key重试唯一结果；并发不同输入冲突，计划/业务版本绑定同事务；真实子进程崩溃后重启不重复提交。 |
| O7 版本 | 错release/hash/服务或适配器版本拒绝；新release不静默迁移旧实例，陈旧确认不能推进。 |
| O8 UI/冷会话 | 新会话不带旧token/材料/结果；三角色清楚前置/阻塞/不支持项；返回/token/迟到回复隔离。无现成assignment则明确阻塞，不用测试owner设置掩盖原AT35缺口。 |

## 下一真正产品决定

建议首片保留固定顺序和四个人工检查点，只组织已有合成Case，不增加执行者赋权入口。真正产品决定是：模板中资源确认是否业务上必须先于分派；新企业新Run的执行者访问由哪个已有有权角色、以什么明确审计操作取得；模板发布/审核人及兼容升级规则；接受后资源变化是否允许重验继续，还是必须人工重新协商/责任handoff。当前建议默认“资源先于分派、缺assignment/已接单失配明确阻塞、无自动handoff”；这些是设计建议，尚未用户签收或部署规则，不能从本地合同测试推定已决定。

原AT14的预览需要实际隔离写入及真实命名空间/资源/Grant不受影响的独立oracle，本轮STRUCTURE_ONLY或SYNTHETIC业务链都不能替代。当前草案只支持合成既有业务命名空间，不开放PREVIEW实例执行；未来另有预览适配器及隔离协议后，再验证预览前后真实表/容量/Grant无变化、预览记录有独立ID且不能被真实命令引用。AT14仍NOT_RUN。

本轮不改运行时代码/Schema/权限/动作注册、不push/newCI/export/LIVE，模型预算0。F1/F2未签收、R4关闭、Win11/36AT6EX NOT_RUN；Windows37420887816继续等待既有安全JSON，不重复催问。

## 本轮实际验证与独立复核

既有tests/test_v1_contracts.py及tests/test_plan_revision.py：29PASS/0FAIL/2既有WARN（15.77s），实际合成PG/API与MockTransport；确认结构合同不发布/不执行，以及单case.create的持久revision1→2/重启/旧回复拒绝范围。额外纯离线边界探针7/7拒绝：未注册材料/资源动作、专员责任角色、缺必需目标、自循环、陈旧服务锁、自由脚本；零业务写入。没有验证或持久化拟四步复合模板，不把拒绝能力冒称实现。

两位独立只读复核补清：读写权限区分、角色最小投影、完整Approval缺口与锁序兼容门、原模板§5.2及AT14实际预览隔离oracle。运行时代码/测试/runner的148个ENG035源hash全部保持原值；808已有范围不扩大，不重复完整回归来伪报模板成绩。证据见[evidence/eng036-template-design.json](evidence/eng036-template-design.json)。本轮交付短Plan及合同边界验证，供产品决定后另派实现。
