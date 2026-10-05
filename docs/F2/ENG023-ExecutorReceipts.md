# ENG023 最小获派执行者合成办理回执

实施前，基线c2f3465。对照原V1 F2-T04、产品5.5/7.4；计划对照见V1Status。不存在执行者办理回执模块，旧Operation LOCAL_CASE_CREATED仅建单；准备资料LOCAL_CONFIRMED也不是办理完成。

只用于已人工核对并由企业LOCAL_CONFIRMED的合成资料整理服务。企业为该Preparation建立一个本地回执步骤，绑定当前prep revision/review hash、Run/Case/Service版本及当前合法run_assignments中的service_executor。API不创建或修改assignment/身份/核心Grant；明确合成owner测试setup可准备假执行者/已分配样例，未增加真实身份。service_executor核心仍READ，无通用EXECUTE/CONTROL/材料/事实/其他事项权；回执写入只由固定角色+本人步骤+当前READ与现有assignment的交集允许。

步骤AWAITING_RECEIPT→执行者SUBMIT→RECEIPT_RECORDED；企业ACKNOWLEDGE只表示本地核对该当前回执→LOCAL_ACKNOWLEDGED，REQUEST_CHANGES→CHANGES_REQUESTED，再由同获派执行者追加新版本；企业REOPEN在已记录/本地核对后有理由重开→AWAITING_RECEIPT。不删原回执，不把文本“已完成”当真实业务成功，Case/Run不自动关闭，资格NOT_EVALUATED/外部NOT_SUBMITTED/线下NO_EVIDENCE。回执只接收显式SYNTHETIC文本、来源版本/标签；服务端计算sha、记录actor/id/time/version，不导入真实文件/签名证明或发消息。

每次当前授权先于幂等重放，actor/key互斥→Preparation锁→步骤锁，3s锁边界，CAS step revision，企业决定还绑定当前receipt sha。接收回执与步骤/不可变事件同事务，失败全回滚；同key原输入回放原回执+当前状态，其他输入/跨步骤冲突。仅本人企业或当前获派执行者能读；执行者看必要事项与回执，不返回企业facts或材料正文。当前身份/role/park/org/READ/assignment变化立即拒绝，企业不可代执行者SUBMIT，执行者不可企业核对/重开。

父资料state/revision/review hash变动时读历史但显示DEPENDENCY_CHANGED，任何新决定/提交拒绝；不自动替换旧材料或重新绑定。这是原计划变化/修订未实现的依赖边界，不自创新业务补偿。企业纠错/重开只对仍有效的原合成事项。

冻结验证R01生命周期/来源hash/旧Case不闭/重启历史；R02跨role/tenant/未获派/代提交与其他工具权限拒绝；R03当前撤权/版本/sha/父资料改变；R04同key/指纹/并发与失败原子；R05迁移重复/历史最小权限；R06真实执行者/企业browser、纠错/重开/重复/迟到草稿守卫与窄屏。初始NOT_RUN，后记实际结果。独立只读6.1sol medium审查关键边界，不继承已有资源审查结论。

仅本地有界切片和提交；原V1/角色上限不改，不发外部通知，不push/CI/备份/export/upload/LIVE。F1未签收/F2NOT_PASSED/R4DISABLED/Win11及36AT6EXNOT_RUN，Windows明细到达优先F1。


## 实际工程结果与限制

冻结最终全量555 PASS/0 FAIL/1 Windows SKIP/2既有WARN，176.33秒；新增回执PG/API36项均PASS，111个src/test/script含JS字节与冻结一致，不据此签收整项AT或阶段。R01—R05覆盖生命周期三版本/来源hash/旧Case不闭/Store重建、跨role/tenant/未获派和工具拒绝、当前撤权先于重放/锁等待3s后409和提交后403、父state/revision/hash、同key/指纹/不同key并发、事件故障全回滚、当前回执跨步骤FK、精确12→13/重复标记历史保留与最小表权限。

R06真实低权限API/独立worker/PG/Chromium企业/专员/执行者表单链PASS：新资料双槽人工核对→企业确认→测试owner仅为新合成Run建立现有assignment→企业创建步骤→执行者v1→企业纠错→执行者v2→企业本地核对→重开→执行者v3→reload历史。分配准备明确在测试owner完成，不称运营分派UI或真实身份接入已实现。执行者企业决定403、另一企业列表隔离、来源纯文本与身份清旧材料、320/390无横滚；独立实际持久详情桌面/窄屏/全页截图已查看，用户视觉签收待定。18项新真实页面mock-response排序守卫PASS，不能冒充后端授权测试；旧双角色资料流程与旧资料/资源排序再次回归。

独立6.1sol medium reviewer `/root/executor_receipt_review` 两次只读公开源码/测试/文档与fixture/browser/oracle，无实质finding；未运行API/DB/browser/测试或读私有runtime，运行成绩来自实现者，审查不替代生产审计。首轮正常沙箱PG无法启动，正式本地测试执行获得自动批准后64项相关用例PASS；后续首轮补充35 PASS/1 FAIL为故障fixture只改父state却未清hash违反旧CHECK，修正显式fixture后冻结全量通过。失败输出留.runtime，不计PASS或删除历史。

33个原V1/Windows/R4/角色保护文件及当前基线roles SQL整个prefix字节保持；旧ENG020/021命名证据22张hash一致，新增图.runtime/eng023-ui、旧资料最终图.runtime/eng023-preparation-ui。既有准备browser曾使用固定.runtime/f2-*.png滚动输出，本轮首次复跑已覆盖这些通用文件；未能还原其上次字节，不能称全部历史截图均保留。改为可选--screenshots且默认唯一目录，最终再次验证新目录，避免后续覆盖；明确命名的旧阶段截图均未改。

局部步骤未做通用CaseStep、运营分派/接单完整语义、通知送达已读、真实证明/签名核验、改变父材料后的显式重规划、全业务Outbox、模板/新企业冷会话及完整目标链。Case目标仍NEEDS_INPUT、无资格/外部/线下成效。详细证据[eng023-acceptance-summary.json](evidence/eng023-acceptance-summary.json)，提交后本片停止，不接下一切片。
