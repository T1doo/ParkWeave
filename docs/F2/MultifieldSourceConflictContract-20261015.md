# F3-T02/T03：已有 Case 的双槽材料包确认合同

基线交付 `40092be0334a9891afcd478a9c0b1a1cfa54fe10`。本片补已有 Case 的显式、可选择启用的双槽材料包确认，并核验组合真实来源变化的影响并集。原六目标、P1–P5、UUID、历史、未影响锁和正式发布权限保持；不重做既有 IMPORT/REFRESH/IGNORE/WITHDRAW、局部 ADOPT 或影响图编译器。

旧 schema1/v1–v2 注记、历史解析、指纹和只读回执保持旧规则；旧模式的 summary-only 合法路径不追溯增加正文冲突。新独立端点采用封闭 schema2 请求及 v3 事件证明。GET 只读，不启用模式；首次用户明确 POST 确认当前两个材料槽和当前 MANUAL 正文，才对本计划启用包级检查。界面明确显示此选择的后续影响。

双槽均绑定实际 B（注记捕获材料包）、M（当前本人正文）和 S（当前材料包）的完整对象、版本、摘要及行 epoch。缺失/损坏 B、未知/失效/撤回来源不得确认或 ADOPT；机会标题和提示不作为事实或授权。need_summary 仅为 CONTEXT_ACK_ONLY：要求明确确认其新上下文，不要求把摘要逐行塞入正文，也不把 summary-only 伪称目录正文冲突。material_outline 实际改变或继承旧 v2 原文承载义务时，outline_carriage_required=true，沿冻结 exact-line 多重集规则；该义务一旦建立不能由后续 summary-only 确认降为 false。

新模式下任一槽变化或 MANUAL EDIT 均需 fresh 包确认。KEEP_AND_CONTINUE 保全 M 字节，MERGE_NOTE 须包含完整原 M 且满足必要目录原文承载；两者复用已有业务 action，不产生新 ADOPT/核验/发布权限。旧 ACCEPT_SOURCE、旧 schema1 CONTINUE/MERGE 在新模式下拒绝，防止隐式退出；原 EDIT 合法但保留待确认状态，KEEP_MANUAL/DEFER 只存待办。确认不复活旧核验、不推断语义义务/事实/现实履约。

P1 锁先沿原 UNLOCK，其他受影响锁仍阻断 ADOPT；保留步骤和锁逐字保持。材料任一槽变化仍由既有图聚合 P1 依赖传播到 P1–P5；资源/容量 P2–P5、回执 P4–P5、本地核对 P5，组合取字面并集。UNKNOWN 按原规则全 Case 阻断采纳，不从聚合 P1 证明虚构旧单槽核验。

确认绑定当前 actor/tenant/owner/Case/Run/plan/revision、卡片最新代次、原账本前缀、材料及当前授权/业务来源 epochs。原事务和最终复读拒绝跨租户/owner/撤权、迟到/ABA、同 key 异参；失败回滚。丢回执仅原 key 冷 GET，NOT_OBSERVED 不代表最终未提交；回执不代替当前授权。合法后续业务办理及 VERIFY 不反过来破坏历史证明。

独审先冻结 affected/preserved/UNKNOWN 字面矩阵，实现/独测/独审只私树并行，root 唯一集成/Git 写者。实际 HTML→HTTP/ASGI→自有 PostgreSQL 正向与拒绝、六目标证据及工作清单读取、完整受影响模块同冻结 SHA 回归，失败与有限安全重试原件保全后正常开发分支推送归档。按一周目标推进；Windows、真实浏览器、正式 AT、真实产品模型/B0–B2、正式治理/批准主体、现实履约及生产仍未执行。无 main 写入/强推/部署/新增费用、凭据、安全权限或真实模型调用，不绕访问拒绝。
