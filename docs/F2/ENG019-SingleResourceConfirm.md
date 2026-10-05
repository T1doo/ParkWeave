# ENG019 单资源本地合成确认

实施前冻结，基线da69ea6。原V1 F2-T03最小延续，不实现组合确认或真实外部预约。独立reviewer只读检查5849..da69的容量/DB时钟/期限/锁序/当前授权/回执/UI，未发现实质finding；未重跑测试，未来确认不在审查范围。

仅本人有效HELD可转CONFIRMED；显式expected_revision必须同时等于占位固定版本与当前登记版本。principal→key→resource稳定锁序，锁后DB clock_timestamp，当前企业角色、READ/EXECUTE、资源READ/HOLD Grant重验。当前enabled、authority、开放区间、缓冲和容量重验，容量排除本条占位自身，但计入所有其他有效HELD及CONFIRMED区间。规则变化需要释放后重新占位，不修改原输入/期限。

CONFIRMED仅表示本地合成账本确认，不代表外部受理/真实预约/线下履约。原expires_at保留为占位确认截止历史；确认后不再按该TTL释放容量，容量按固定区间及缓冲参与冲突。区间结束不自动宣称履约。显式release兼作本地取消，CONFIRMED→RELEASED，HELD过期仍EXPIRED；旧回执不可改。相同key回放当前授权后返回原回执和当前状态，不重新确认/延长/恢复释放。不同key对已确认/已释放/过期记录拒绝。确认状态和回执同事务，失败全回滚。schema10→11只扩状态/action约束，无新增应用权限。

冻结验证C01生命周期/重启/取消/历史与容量；C02过期/释放/版本/停用/窗口/容量拒绝；C03并发同key/不同key/释放竞争；C04当前撤权/tenant/role/指纹；C05回执失败回滚/旧迁移历史；C06实际浏览器确认/取消及迟到响应保持上下文。初始NOT_RUN，实际成绩后记Log。

仅项目内本地代码、PG/API/browser测试及commit；不push/Actions/备份/上传/新凭据/真实provider，预算0。F1未签收、F2 NOT_PASSED、Win11未验证、R4 DISABLED、完整36AT6EX NOT_RUN；Windows明细收到优先F1。
