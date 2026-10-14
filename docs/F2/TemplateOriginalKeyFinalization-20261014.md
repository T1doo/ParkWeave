# 模板原采纳键的显式收尾与逐条句柄清理

接续 `f8ff5a46d917d864a23c99260abab59873c25790` 的 [模板独立部分办理](TemplateIndependentPartialPlan-20261014.md)。补件提交为 `41d8564ff2eef384f7879d62e107628a46ff9211`；由原 frozen-review.json 的 actual_chain 以 indent=2、ASCII转义及末尾换行精确恢复独审缺件，7808字节及 SHA256 `dfb0685e68a260e2787f374659f7a35c04c1a6767debdcbbf540b9aaca5aaf61` 与原索引完全一致，现已纳入Git跟踪。没有为补件重跑或改造原链。旧报告已修正23为页面HTTP、审核确认桥额外4次、共27次；403可按原权限路径写拒绝审计。

最终源码 `577db0879a080c685609e2bd5fcef5d4683beb1b`。GET `/planning-recovery` 仍仅核对精确原consumer键、不可变正文/指纹、原inner key、Case/Run/资料绑定、当前READ/PREPARE/EXECUTE及owner/来源/专员权限，等待后重新检查；成功GET不写业务表、日志或观察审计。当前拒绝审计不被误称零写。GET新增持久journal_state、journal_terminal、finalizable及精确收尾证明，但不会自行确认或解锁。

新增显式POST `/planning-finalization`：沿原consumer键串行文件锁，重读原回执及当前权限，调用者明确给定原正文SHA、inner key、日志状态和收尾原因。只有精确COMMITTED才能CAS确认；严格单调版本推进证明原参数永久不可能提交，或新持久首次明确拒绝，才能进入CLOSED_NOT_COMMITTED。CAS包含旧状态、inner key、正文SHA、旧结果及错误，取得日志写锁后再次核权限。同收尾参数返回原终态，异参冲突，原因和指纹持久保留。POST只允许日志收尾，不调用ADOPT、不改原成功事实/资料/计划/资源。响应明确journal_command=true、journal_read_only=false；随后GET证据仍journal_command=false、journal_read_only=true，幂等POST不宣称每次都新增写入。

普通REFUSED仍可能重新ADMITTED，不能独凭它确认永久拒绝。新首次实际发送或发送前明确拒绝以REJECTED_FIRST_SEND及FIRST_错误码保存；只在新consumer请求的首次尝试产生，旧REFUSED重试不会伪装首次拒绝。其旧consumer键已不可重发，显式收尾才解除后续新键阻塞。CLOSED旧外键永不发送；CONFIRMED同参仅返回缓存原结果。NOT_OBSERVED、当前403/409、超时、坏句柄、缺请求/日志和不匹配证明均保持未决。迟到_unknown不覆盖已确认、首次持久明确拒绝或已关闭阶段。

终态禁重发范围是consumer外键。本片保留原产品API的独立当前权限合同：独审实际在首次拒绝收尾后，用已授权原API及inner key产生真实201回执；consumer恢复对此矛盾返回409，不把真实成功改成NOT_COMMITTED_FINAL。严格旧版本分支另实际证明延迟原API发送409。没有新增Grant、registry能力、跨租户访问或原执行协议放宽。

页面先只读核原键，再由用户填写明确原因显式收尾。发送收尾前持久finishPending，丢响应后只GET重查，不重发收尾或采纳；只有GET精确核实服务端持久终态才删除该条句柄。成功但未收尾的句柄保留。新句柄按actor/instance/external key独立命名，旧v1 base-name严格兼容；标记和清理前核磁盘内容，迟到响应不会覆盖或删除另一原键。当前actor的列表逐个打开指定原事项及精确磁盘键，所选键缺失不回退到另一条，不批量清空或静默驱逐。清理后冷读原已采用计划可继续；其他未决仍阻止采纳，整体PARTIAL、全部目标和人工项保留。

最终根冻结九模块：**212唯一PASS、0FAIL/ERROR/SKIP、2WARN，164.623秒，exit0**。独立最终另窗：**12唯一PASS、0FAIL/ERROR/SKIP、2WARN，13.682秒，exit0**；原HTML NodeVM **25断言PASS**，不是后端授权证明，重复窗口不加总。225项冻结文件hash一致。

实际原HTML→ASGI→owned PostgreSQL容量链38断言、87页面HTTP：8个真实成功原键保持占位，第9次采纳在发送前被容量限制阻止；首ADOPT及首收尾响应各在实际提交后丢失，冷页只GET核服务端终态，仅清第一条且其他7条保留，第9个Case采纳随后成功；再明确单清第二条，余7条，9个Case/9次ADOPT/2次收尾，无自动业务执行或授权变化。另一原办理链32断言、23页面HTTP加4审核确认桥调用共27，独立P1核验后整体仍PARTIAL并接原结果/总览。所有恢复GET都有业务/授权审计和日志快照不变断言；收尾POST仅日志变化。

真实PG parent锁等待被pg_stat_activity观测：ADD_EVIDENCE先提交200，等待中的旧inner key原ADOPT409，原键收尾CAS200，未生成计划。独审另验原consumer延迟发送与同键收尾串行竞争：原发送胜出后只确认精确COMMITTED，状态变化时旧CAS409而非伪造关闭。撤READ/PREPARE/EXECUTE、同body幂等/异原因冲突、冷engine、普通REFUSED/ADMITTED/STARTED未观察禁结束、矛盾实际回执409，以及迟到GET、坏句柄、同实例第二键准确选择均实测。

失败和旧窗口分开保留，见 [结果](evidence/template-terminal-20261014/results.json)、[命令](evidence/template-terminal-20261014/commands.json)、[原件及导出hash](evidence/template-terminal-20261014/sanitized-exports.json)。首红验2FAIL证明缺持久终态接口字段。第一次回归34PASS/1FAIL是旧测试在明确拒绝旧来源后立即提交新键，现先显式收尾旧键，保留来源推进/新计划/历史断言。早期35PASS、容量28PASS、独立12PASS等不算最终或加总；00cc开始窗口中途修精确选择，212PASS仅列被替代窗口。7b64的另212PASS后修POST响应只读标志，最终577db源码重新完整212PASS。独审首Node假Element缺removeAttribute导致失败，只修独审夹具并保留原失败；独审发现的矛盾回执误报和列表错键已实修、复验。公开导出仅脱敏4份log/XML的生成fixture会话repr，原私有失败、hash及XML统计保留，不修剪尾部空白。

本片没有schema迁移、部署、真实模型/付费调用、凭据/网络配置、安全prepare、main/F1/原F2改动或强推。浏览器NOT RUN，历史Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR仍保留，未启动、换URL或工具重试。host_case_once两审批仍false/null/null，SHA256 `c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a`。恢复缺证据或收尾未取得终态仍未决，容量仍为8个浏览器句柄；需原主体取得授权和精确终态后逐条处理，本片不自动清理未知操作或宣称完整Case生命周期。
