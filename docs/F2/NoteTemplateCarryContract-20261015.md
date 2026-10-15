# F3-T03 / AT26–27：携本人注记的同结构兼容模板采用合同

基线交付 `ed5d32b6bbcf261d802fe579a2daab16330a5879`，仅当前同 Case、同 owner、同模板谱系、同 scope/service/version/参数 schema/registry/contracts/required_goals/steps 的前向兼容版本。只保全原单 P1 的 MANUAL 协调正文，不增 Case 目标、节点、边、UUID或发布权限，不开放携注记结构增强、非局部计划替换或通用迁移。既有有限合成 Release/ParkInstance、模板前向增强和真实来源手动刷新均保持，main 只读。

原升级 HTML 显示旧/新模板版本及来源、当前注记全文和 MANUAL 身份、当前两槽实际材料、受影响/保留步骤及锁冲突，用户先原 check/choice，再重新 check，另行明确勾选携注记保全及原采用确认并给原因。原 Apply 与 StructureApply 的字段、原缺省 dump/指纹、旧事件封闭验证保持；新增独立 NoteCarryApply（原 Apply 加 expected_note_carry_sha256、严格布尔 true 的 confirm_note_carry），独立 `/apply-note-carry`，原 key 恢复仍为 `/apply-requests/{key}`。旧 /apply 与 /apply-structure 对携注记继续拒绝。

新 TEMPLATE_UPGRADE 事件仅额外保存版本化 note_carry 证明，独立纯验证分派。保留注记完整原值（text、origin、revision、event_id、source_ref、source_package等）、原 note/机会事件、双向链接及所有历史逐字不变；不将 MANUAL 改签 SOURCE，不生成核验包或新事实。原完整步骤合同不变，旧 note 的 _plan_ref 验证不放宽。carry 证明绑定 actor/Case/Run/instance/plan/修订和完整步骤合同、注记全文、note历史与机会账本前缀、当前及原捕获材料全文和行 epochs、当前授权/业务来源 epochs、旧新 release/source、原 check 与明确 choice、受影响/保留集合；hash 不纳入其自身 sha 字段。最终复读与原事务/CAS/源租约保持，拒绝源或权限 ABA/撤权/迟到/同 key 异参。

来源分两类：当前 Case 材料 S 变化或未知时，原 KEEP_MANUAL/DEFER、继续后再 EDIT、缺条件等冲突不能用 carry 消解，须先沿原合法 note 编辑/继续/合并、原局部 ADOPT、实际必要办理及 VERIFY，再重新检查与确认 carry。旧继续事件不授权新模板。若目标模板 definition.source 变化，本次 fresh carry 明确绑定旧/新模板来源和当前 MANUAL，是新的跨版本保全确认；它不代表语义义务、资格、事实或履约满足。沿原迁移规则全 P1–P5 失效，随后原必要业务操作及五步 VERIFY→六目标证据/清单。不强制无法触发的“材料未变却再次材料 CONTINUE”。目标模板来源完全相同、仅标题/说明改且当前 Case 真实来源干净时，affected=[]、全部步骤和未受影响锁逐字保留；不能把同模板来源泛化成 Case 无需重核。

破坏性、未知/失效/撤回来源、非 MANUAL、多注记、不同谱系或目标/步骤差异拒绝。仅原实际受影响步骤的锁构成冲突；拒绝不能自动解锁，原 UNLOCK 后重新预览。64 计划事件需预留本次升级、所有受影响 VERIFY 和原锁 UNLOCK；128 机会事件不扩。carry 不写机会事件，不制造额外额度。旧继续/旧 carry 不沿用到新 target、新注记或新源；每次都需 fresh 显式 carry 确认。

实际应用沿原 PG 事务和模板源读租约，失败完整回滚，业务事实/资源/预约/回执不回滚或重演。同 key 同参回原事件、异参拒绝；结果未知不重发 POST，热/冷页面只 GET 原 key，NOT_OBSERVED 不代表最终未提交。当前授权优先于历史回执，页面主体/instance/target/generation 变化隔离旧响应，当前403清私有内容。只读不得隐式修改业务事实。

验证使用原完整 HTML→真实 HTTP/ASGI→自有 PostgreSQL，固定字面场景先于实现，独立实现/独测/独审在私树，root 唯一共享集成/Git 写者。完整受影响模块在同一冻结 SHA 从头回归，保留所有失败和有限安全重试，再冻结独审、正常开发分支推送及归档。Windows、真实浏览器、正式 AT、真实模型/B0–B2、正式治理与现实履约、生产和无现有触发的本分支 CI 均保留未执行边界。无强推/部署/新费用/凭据/安全权限或真实模型调用，不绕访问拒绝。按10月15–22日一周目标接续。
