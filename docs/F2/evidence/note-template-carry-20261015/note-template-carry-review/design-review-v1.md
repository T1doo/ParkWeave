# 携注记兼容升级：只读设计审查 v1

状态：设计阶段，未冻结、未运行本批测试，不签实现 PASS。基线 `ed5d32b6bbcf261d802fe579a2daab16330a5879`。只写本目录，不改共享源码/Git/旧证据。

主方案 §7.5/§8、F3-T03、AT26/27要求历史保留、当前授权、人工锁、逐 Case 检查及破坏性迁移拒绝。root 的新 `/apply-note` 有界方向符合这些要求：只支持现有单 Case/原 instance 同谱系、严格 forward 同结构，以及单 MANUAL P1 正文；不增加目标、节点、一般迁移、发布权限或业务完成结论。

## 必须保持的实现门

1. 不能只删除旧 `owner_amendments` blanket gate。新模型在原11字段外显式 carry digest 与严格 bool true；新 patch/version 独立分派。原 Apply、StructureApply 的请求默认值、指纹和旧九键 patch 证明保持；原 route 携 note 仍拒，新 route 携结构增强也拒。已有无 note 的有限前向结构增强保留。
2. 同结构指原完整 goals/step contracts/依赖/registry/contract 相同，故旧 note `_plan_ref.steps_sha256` 与旧 note/ledger 事件原字节不改。note 本体含 revision/event_id/source_package 不改；carry 是单独迁移证明，不能伪造一条 NOTE 编辑或借旧 CONT 作新模板授权。
3. 验证 carry 的 note 必须按迁移事件之前的事件/ledger前缀重建；以后合法编辑、继续、再升级不能让早先 carry 历史失效。不可拿当前 `owner_amendments` 校验旧 carry。
4. material S 与 template.definition.source 分开。真实 Case 资料 S 变化先走原 note resolve、local ADOPT、VERIFY 并保持当前业务来源；KEEP/DEFER、后续 EDIT_RECONFIRM、UNKNOWN 仍拒。模板 source 变化由本次新 carry 绑定旧/新 template source、当前 M/资料和 epochs，全5失效；不要求一个 material 并未变化因而无法触发的后续 CONT，也不声称正文覆盖就是业务履约。
5. 新 carry proof 绑定 actor/park/org/Case/preparation/instance/原有效 release/目标 release、计划 UUID/revision/原采纳 fingerprint/immutable step hash、原 note/ledger prefix、当前资料完整双槽、原 check/明确 choice 和 scoped epochs。最后复读 UNKNOWN/变化须返回可恢复拒绝而非500。
6. 现成 `source_change_adoption.epochs` 有 principals/capability/preparation grants 等，但没有 case.create action_grants、parent/cases 自身 epoch。若承诺这些 ABA，需单独有界补充并最终复读；当前权限仍用原 auth lock/EXECUTE/PREPARE/action grant/current scope 守卫，不新增权限。不声称能防受信管理员在最后复读后提交的任意外部篡改。
7. 原历史 replay 在新 note/current carry eligibility 前，但在当前鉴权后；旧 key 不因后来合法 note 编辑或目标失效而伪装成未提交。冷 GET 历史成功与当前 availability 分列；NOT_OBSERVED 不是最终未提交，generic409/5xx/transport 不自动清 handle/rePOST。
8. 原 PG parent→dispatch→Case 与来源 SQLite lease/最终 commit guards 保留。一次 apply 事务只追加迁移事件/有效模板绑定与明确受影响失效，不改正文、锁、业务预约/回执。失败整体 PG rollback；此前 SQLite 的明确 choice 可以保留为 choice 审计，不是迁移成功。
9. title/source 相同且 Case 当前，affected=[]，P1-P5/全部锁/旧证据保持。template source 变化 affected=[P1,P2,P3,P4,P5]，任一锁拒；原 UNLOCK 后 freshcheck/choice/carry，原5 VERIFY，不生成业务动作。
10.64预算继续预留 1 apply +受影响 VERIFY +所有现有锁的原 UNLOCK；sourcechange 无锁58可达64、59拒；title-only无锁63可64；一个 preserved锁62可、63拒。carry若不新增note/op事件，不凭空消费128机会ledger；若方案改为新增ledger事件，必须明确预算与proof，而非绕上限。

## 固定字面 oracle

`literal-oracle-v1.json` 共 38 个设计场景，全部 NOT_RUN；SHA256 `7ab53d8465e4344a2a7a5f6cb39aacdcfdd09b306629c97687c07690ae84d14c`。A/B 同初态但各自稳定 UUID，只实际选择 A 升级，B 全量原业务/计划/锁/历史保持。独立答案预先写死：title-only []/全5保留；template source changed全5/空保留；UNKNOWN拒绝而非伪造完整影响图。拒绝/预算/历史篡改、旧协议兼容和后续编辑/多跳另列，不以设计数代实际 pytest。

## 建议冻结后的完整模块范围

新 API/HTML 模块之外，至少完整覆盖 template_migration_independent/event_capacity/legacy/legacy_independent/nodevm_actual/ui_offline、template_upgrade/browser、template_structure_independent/proof_types/commit_expiry/nodevm_actual/ui_offline、plan_source_conflicts、manual_content_continuation/independent、原 template_full_chain、template_partial；共享 api/web 的原完整入口回归仍需 root 并集覆盖。后续检查实际 imports/路由/模型变化再定，不复用旧分数。

新增 focused oracle 建议：成功 title+source 两 Case 对照；旧v1/v2 note+旧迁移 parser 兼容；成功 carry→EDIT→再carry→冷GET第一key；最后复读 UNKNOWN/expiry/revoke seam；action grant/Case/plan/material ABA；P3锁及58/59/63/64、128边界；真实 PG 事件插入失败 rollback；真实 HTML commit-lost-reply冷 GET 与身份 ABA迟到403；新carry proof纯历史多字段单侧重算篡改矩阵。只限 Linux 合成，Windows/真实浏览器/正式AT/真实模型/生产仍未执行。
