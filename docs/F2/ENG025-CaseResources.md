# ENG025 服务Case与合成资源组合的持久关联

基线18f9f5670960a3affdf6d11455a89fc4aaaebb16。原V1产品§5.2/5.4/5.5、6.2/7.4、F2-T03/T04：资源有归属/版本，批准绑定关键前置，变化重验保留历史，释放预约是独立动作。只覆盖当前合成资料整理Preparation对应Case，原文/角色上限不改。

企业本人读取已确认资料，明确选择自己有权读取/操作的已确认两资源组合，给理由并提交prep revision+当前关联revision。服务器锁当前授权、资料版本、资源/组合与Case，以同一事务写不可变关联版本和组合归属。组合只能归一个Case，防止重复计资源承诺；同Case新资料版本可重验同组合或改选新组合，保留旧版本与旧归属，不自动释放旧预约。跨Case共享/拆份和转移归属尚未定义，明确拒绝，不发明共享规则。

关联不重复占用或确认容量，不是通用ServicePlan/Approval。写只接受LOCAL_CONFIRMED资料、当前资源READ/HOLD、CONFIRMED完整组合、仍未结束的使用时段与当前规则版本；HELD/过期占位不是组合，已取消/时段结束/规则变化/另一Case归属明确拒绝。当前READ先于历史重放，撤权拒绝；actor/key指纹、prep/关联CAS、稳定资源锁和不可变记录同事务，失败不残留归属或版本。

读显示关联创建快照、当前组合及Case/资料状态，分开CURRENT、PREPARATION_CHANGED、RESOURCE_CANCELLED、RESOURCE_WINDOW_ENDED、RESOURCE_RULE_CHANGED；任何一项不适用都不称已履约。资料重开不删除历史或释放组合；资源整组取消仍走原接口。原Case实际只NEEDS_INPUT，暂无Case重开/关闭API，此片不能发明它已实现。服务执行者无新资源Grant/API访问，自己的回执关联已有Case，不能越级操作资源；通用分派/接单/通知/真实履约不在本片。

冻结L01当前归属/版本/幂等/不重复容量；L02跨企业/园区/角色/未有权/当前撤权；L03取消/时段结束/规则变化/重开/重新核对/旧资源仍占用；L04同/不同key并发、两个Case竞争同组合、取消竞争与失败回滚；L05不可变权限/13→14及重复标记历史；L06真实UI选择/持久reload/跨角色/迟到/草稿/桌面320/390，唯一新截图目录。初始NOT_RUN。独立6.1sol medium只读审查，最终源码冻结聚合回归和实际结果后记。

仅本地修改测试commit；不push/newCI/export/upload/backup/LIVE，不重试拒绝日志下载。F1/F2未签收R4关闭、Win11/whole36AT6EXNOT_RUN，Windows失败明细待用户，预算0。

## 独立审查与具体修复

case_resources_review（用户指定6.1sol medium）仅只读本工作树源码，未执行API/DB/browser或读取私有runtime。发现三项P2：同Case迟到成功会覆盖新组合/说明草稿；候选未计当前HOLD；处理新草稿前的return使当前403不清私有视图。均修复：保留仍可操作的选择，提交冻结完整草稿，刷新期间禁用表单，仅草稿一致时清说明；409/422迟到错误不污染新草稿，当前Case/身份403仍清视图；候选检查HOLD，无EXECUTE只读历史。最终源码复审未发现剩余实质缺陷。忽略迟到UI不等于服务端POST回滚。

## 最终实际结果

L01—L05新增29项真实PG/API测试全部PASS，覆盖持久关联/重启读回、相同key并发与跨Case指纹冲突、当前角色/企业/园区/撤权、资料重开/明确重验、换组合保留旧归属与占用、取消竞争、读取/重开竞争、已结束/规则变化/停用、确认后占位TTL过去仍有效、hold ID不能伪装组合、CAS/失败回滚/不可变权限、真正schema13无新表升级14及标记重跑。并发使用真实PG线程，但未控制每次调度交错，不声称穷举双方等待顺序。

L06冻结后Linux低权限API/独立worker/PG/Chromium实际界面PASS：新诉求资料补正/新版本/人工确认→两资源组合→页面选择并保存Case关联v1→reload读回→资料REOPEN不释放→人工再核对/确认后关联v2→获派执行者三版本回执/企业纠错核对重开→显式整组取消两条RELEASED→原关联历史和RESOURCE_CANCELLED仍可读。此时Case仍NEEDS_INPUT，通用Case重开/关闭未做；合法SYNTHETIC assignment仍由测试owner准备，不能称产品已分派/接单。另一企业隔离/执行者代企业决定403。旧通用候选事实补充/澄清/取消真实browser也PASS，事实UNKNOWN，原历史保持。

最终五页面mock-response oracle：generic7、preparation23、resource31、receipt18、新Case关联16，共95/95检查PASS；新16项含完整草稿/选择迟到成功、失败重试key、当前403清私有视图、旧Case/身份/导航、刷新/版本守卫。这是页面时序测试，不称后端授权测试。初轮17/17包含错误的改草稿后403保视图预期，独立审查后废弃该预期，以最终16项为准。

全量工程584PASS/0FAIL/1WindowsSKIP/2既有WARN，180.06秒；121个含JS的src/test/script字节与冻结哈希一致，compile/JS语法/diffcheck通过。首轮21个fixture lookup错误、随后TTL fixture一个不存在列/两个时间约束失败均保留日志，修正测试fixture后通过，不修改生产有效期规则来迎合测试。最初真实browser通过但运行期间源码仍修订，不作为最终冻结证据。

新增14张真实截图使用独立eng025-ui-verified目录，已查看桌面关联与320失效历史；320/390无横向溢出，CSS字节保持。审计55张登记图hash匹配（既有41+本片14），3旧覆盖与3恢复缺图仍不可复验，不用新图替代。原V1源文、33保护文件、旧roles全部字节前缀均保留；仅新增不可变关联表SELECT/INSERT权限，无核心角色上限变化。细节见[evidence/eng025-acceptance-summary.json](evidence/eng025-acceptance-summary.json)与[截图审计](evidence/eng025-screenshot-audit.json)。

此片只把当前资料服务Case与合成组合从测试手动关联推进为产品API/UI持久关联。注册服务有限DAG/目标覆盖、一般ServicePlan/Approval、通用CaseStep/运营分派接单、通知/全业务Outbox、模板/冷会话、真实身份/证明/资格/履约及完整原F2端到端仍缺。仅本地commit后停止，不push/newCI/备份/Library/导出/上传/LIVE；F1/F2未签收、R4关闭、Win11/whole36AT6EX NOT_RUN，Windows Server失败37324704568明细待用户，Server不能代表Win11。
