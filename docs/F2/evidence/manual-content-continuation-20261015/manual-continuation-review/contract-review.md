# 保留人工内容后继续：独立设计审查

基线实核 `7cfb1336bbfbf856c37808a66ec6f00067b6f966`，初读 tracked clean。读取主方案 §7.3–7.5/§8、F3-T03/AT26、原固定变化批合同、原说明/来源采纳/服务步骤实现和相关测试。原代码/合同输入以 exact Git blob 摘要保全；本批合同另记 SHA-256。未运行业务测试、大窗或模型。

本片合同方向可接受：当前 owner、同 Case/plan 的 P1 协调说明；三版本 B/M/S、原文承载检测、明确继续后原 ADOPT/真实办理/受影响 VERIFY。它没有把普通 KEEP/DEFER 改成解决，没有授予新权限，也不是一般语义合并。MERGE 保留原 M 的完整连续逐字片段，比仅要求原 M 行集合更严格。

46 个独立设计场景在 `literal-oracle-v1.json`。预期集合是先行字面值：A 材料变化只影响 A P1–P5，B P1–P5 保留；owner 可选容量变化影响双方 P2–P5，双方 P1 保留；UNKNOWN 扩大本 Case 重验且拒绝继续。只在测试时把这些符号替换为原 UUID，不调用待测闭包/图/编译器生成答案。设计场景、pytest 节点、传播观测、步骤对、HTML 模式必须分别计数。

## 必须核对的安全门

1. **三个真实版本。** B 是该 note 当前来源锚对应的原捕获两槽材料包，逐字复证本 Case 历史行；M 是当前手工正文、修订与 hash；S 是服务器实际当前两槽材料。锚重绑后，旧 B 和原手工正文仍完整存在于事件历史，不能改旧行或伪造旧逐槽核验。来源、source_kind/label、id/version/hash、slot 唯一性、完整包和当前 epochs 都校验，不能只校验一个正文摘要。
2. **字面条件。** 对 S 使用 `splitlines()`，以 `line.strip()` 判断空白行，但比较原行；不 trim、不折叠空格、不忽略大小写、不做 Unicode 归一；重复行按多重集。零条和超过128条是 UNKNOWN，不许空集真值放行。缺失列表保留原行及缺失次数。该结果只能表述“原文承载”，不能表述义务/资格/事实/履约已满足。
3. **动作不混用。** 原 KEEP_MANUAL/DEFER 一直待处理；KEEP_AND_CONTINUE 不接收正文且保留 M 字节；MERGE_NOTE 必须明确提交完整稿并包含 M 完整连续片段和 S 条件；原 ACCEPT_SOURCE 仍精确复制 S。每种选择都只记录协调决定，note 继续 MANUAL，不设置真实材料事实、核验包、权限或业务完成标志。
4. **锚相等也不能绕过。** 新继续重绑 S 后，普通 EDIT_NOTE 删除条件而保留同 source_ref，原 `adoption_blockers` 的“锚相等立即返回”不能再直接解门。重建有效继续事件及双向证明，核当前稿的条件承载；删除后两条原 ADOPT 路径必须拒绝。删除再补回后要重新预览/明确继续。定案为任何后续 EDIT 均使旧继续决定失效，即使条件仍完整或正文完全相同；需要新的明确继续，不能默用旧 M 指纹。
5. **原锁仍是业务门。** P1 锁下新继续与合并都拒绝；KEEP/DEFER 可留下原待办决定但不能解锁。A 材料变化时任何 P1–P5 受影响锁都拦原 ADOPT；容量对照中未影响 P1 锁和锁证明逐字保持。原 UNLOCK 不等于重新核验。
6. **当前有效性不从历史继承。** UNKNOWN、不能复证 B、来源失效/撤回、非当前 head 或终止卡、服务绑定变化、未支持 compiler/schema 都不能继续。过去 COMMITTED 可以按当前读权限作为历史观察，不能恢复当前资格。SOURCE/M/plan/card/权限 ABA 必须用修订/epochs/账本前缀/页面 generation 拦，而非只比最终文本或当前授权布尔值。
7. **原全部入口一致。** 预览 `can_adopt`、有 opportunity_proof 的原同计划 ADOPT 和无该 proof 的原局部入口，都调用同一当前 note 门。不能只禁 UI。当前无 note 行为和旧 key 原参重放保持；携 note 非局部 replacement/template apply 仍拒绝，未实现跨计划 carry 不因继续决定而开放。
8. **独立历史版本。** 命令仍原 schema1、同字段结构，仅增加两动作；原 request/default 字段、fingerprint、事件/账本和原验证器语义不变。新增继续证明为 `proof.version2`，按保存的 proof.version 分派，不能以 current parser/compiler 重解释旧历史。双向 ledger/plan proof 校验应能拒绝单边篡改、重算单边 hash、重复/错槽、bool/float 别名及假前缀；无递归验证环。
9. **同一事务和最终复读。** 原 plan + opportunity 同 PG 事务，异常两侧回滚；scope/key 锁后重新核当前权限/Case/Run/版本，来源锁等待后最终复读。命令暂态 preview 的 parent xmin 会因自身保存/原 GET 观察推进；持久的继续语义证据必须与这个短时 basis 分清，既不能立即自失效，也不能删除 source/authority ABA 保护。
10. **预算和后续真实办理。** 64/128 原上限不扩；预留本次决定、所有原 unlock、ADOPT、实际待核验步骤所需事件。决定后重新 GET 原影响、显式原 ADOPT、必要补料/审核确认及其他业务操作、逐受影响 VERIFY，再从目标证据/工作清单读结果。原 UUID、六目标/合同、旧业务事实与事件前缀不改；影响当前有效性与历史存在分别比较。
11. **页面恢复不冒写。** 展示三版本、逐条缺失次数和字面局限；候选稿不自动拼接或承诺满足。digest 等待期间稿/原因/勾选/context 改变不发送；保存 opaque 原请求引用后才 POST，不存正文、原因或 token。未知结果只 GET 原 key；NOT_OBSERVED 保留句柄；只有精确 COMMITTED 或原精确无写拒绝证明才能按原规则释放自己的引用。
12. **迟到隔离。** 身份/Case/plan/generation/revision 及来源卡切换均绑定；迟到成功、403、坏 JSON/transport 不能清新上下文。当前403清当前私有视图，不丢未知结果句柄；冷 GET 历史成功与当前 UNKNOWN 可并存。不能用 generic409/422 释放句柄或全清其他 tracked lease。

## 冻结后证据建议

正向至少两条原完整 HTML→实际 loopback HTTP→ASGI→自有 PG：保留原 M（先明确原 EDIT 补足条件）→重新继续→原 ADOPT/原业务办理/全部 affected VERIFY；明确追加 MERGE 同闭环。每条在开始先固定原六目标/P1–P5 当前 VERIFIED 的双 Case 初态，保存正文、UUID、历史/业务行、未影响锁逐字段对照。

拒绝至少覆盖来源未知/坏 B、少一行/少一次重复/一空格不同、M完整片段丢失、P1/P3锁、删条件后锚仍相同、来源及权限 ABA、跨租户/owner、异参同键与迟到/冷 GET。每次拒绝比较业务事实/历史不变；原 authorization_audit 拒绝记录与原 GET 观察 invalidated 的限定变化单列，不把它们误算业务修改或悄悄放宽全库断言。

完整受影响模块范围建议依据实际冻结 diff，从上一批90消费者集合重新评估并加新组件/独测完整模块；不给旧成绩续签。原脚本、collection/JUnit、source/all-tracked before/after、runner/plugin hash及独立字面 oracle 先冻结，再计数。Windows、真实浏览器、正式业务AT、真实模型、生产和分支CI仍未执行，不能由本批 Linux 合成证据代签。
