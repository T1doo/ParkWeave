# 合成目录修订与原 Approval 消费提交的协作

在原首次同 Case 合成资源交付范围内，目录现在保存有界不可变修订和独立发布指针。原 Approval 的来源绑定包含实际指针 UUID/revision/hash/state；相同正文重新发布、改后恢复（ABA）、撤回都不能复活旧批准。原目录投影和计划来源保持一致，来源变化仍须原明确 ADOPT/VERIFY，历史回执保留并显示 NEEDS_RECHECK。

消费在读取批准来源和取得任何成员资源锁前持同目录键的 shared 事务 advisory，直到原交付 COMMIT/ROLLBACK。合成 owner 发布先取同键 exclusive，再锁目录行、检查 CAS 并追加修订、移动源正文与 head。同协议内发布先提交则旧批零效拒绝；消费先持锁则 publisher 实际等待最终提交或回滚。首次安装也先稳定排序取所有原范围目录键，再取得目录 ACCESS EXCLUSIVE 安装锁、重读 schema 并执行 DDL/INIT；同键及不同键首次安装均串行化，不倒置 DDL relation 与 advisory 次序。

仅原已签发同进程 IsolatedPlanApproval 的自有新建临时 PG/原最多16个 Case范围显式启用。公开服务仍 synthetic-material-preparation@1，内部 source revision 只可修改合成来源的 revision，固定服务/目录主键/namespace/qualification/name/kind/id/statement不开放。setup只在原目录增加两个候选 JSONB 列及固定不可变前缀触发器，无生产迁移、发布API/环境入口、新权限/角色/Grant；应用目录仍 SELECT only，默认关闭。32事件上限实际可达，ACTIVE31预留最后明确 WITHDRAW32；重复key仅读原历史，不自动复活或重置。

实际不同 API subprocess PID与测试本身新建自有PG stop/start后，已消费 Approval 账本/head、原回执/关联/实际效果保留。system identifier/database OID相同、PG PID/postmaster_start改变；冷浏览器重新认证后只 GET核对原消费证明，原P2/goal读仍检查该证明，剥离回执引用后拒绝降级。没有用newStore/App代替重启，没有重签/复制 fixture nonce。未消费批准在新进程专用入口仍403，写入口关闭，旧 issued capability在PG重启后DENIED；这部分继续未签收。

精确运行源码 `20c0a568312e53c1c926927eda6d11c607c8e44e` 已独审LIMITED_PASS。根18完整相关模块分两窗：3模块79PASS/33.025秒（受控34.26952秒），其余15模块503PASS/584.543秒（受控586.276273秒）；独审自身18完整模块也分两窗：79PASS/48.806秒（受控50.097374秒）、493PASS/595.665秒（受控597.647948秒）。各方两窗无重复，分别唯一582和572PASS，不伪称一次总PASS，不相加为全仓。另独立11API/19.435秒、7实际浏览器/39.642秒、6安装边界/6.943秒、1实际新API写关闭/7.167秒共25额外PASS，均exit0、零FAIL/ERROR/SKIP且自然结束；本SHA无产品或观察器故障。331源首尾零漂移，manifest SHA256 `4c8710f177f372c096420c21791d2730a1476f5ed1f93bda1154372697fb3a70`。独审报告 SHA256 `33d5d095951fb09e88daf273a2fdceb79c765885e58fb29a645d6e639ec871e1`，公共副本与私有原件一致。

首轮2ccfae6独审实际复现首次setup先ALTER持AccessExclusive再等exclusive advisory，而消费已持shared又等relation的死锁；BLOCKED未合dev。原根578PASS不抵消该FAIL。原独立538PASS+1 observer ERROR/exit3是私有进度hook读取被CLI测试改动的sys.argv；17完整业务509PASS与另窗完整诊断59PASS分开记录，不重复诊断前29项。首次错误系统Python0tests启动故障、死锁原XML/日志/锁记录及旧hook都私有保全。修复前bc3合同先明确key→DDL顺序，再07c修实现与真实两序回归；旧窗口不替代新SHA最终验收。

第二轮07c63b17独审真实不同目录键首次安装竞争报DuplicateColumn，仍BLOCKED未合dev；旧根580PASS/622.022秒、独立570PASS/637.442秒与10API/7浏览器/1metadata PASS不抵消该FAIL。591ed合同先明确全部key→关系安装锁→重读schema；20c仅加owner安装锁与同/不同key及重复setup回归。实际_schema前后目录关系锁为空的独立实证保留，不凭隐式锁猜测扩修改范围。断联提醒后命令通道实际可用、Git干净/源码零漂移、记录哈希保全，没有重启写入者或因提醒重跑长测试；随后父任务澄清不要因通知重复挂起工作，而新源码必要完整相关回归应按原计划完成。最终20c先完成3个短模块，再以不重复这3模块的另一完整窗口补齐其余15模块；两窗分开记录，不能冒称同次18模块总PASS或将07旧PASS转签。

此前开发窗口有一次预览目录投影不一致产品FAIL、错误字段观察器FAIL和自有socket重启绑定观察器FAIL，原件保全；修后各个开发PASS只保留各自范围，不能相加作最终验收。只公开安全报告、最终PASS XML/日志、独立probe源码、实际重启/锁元数据与工件hash；失败原件不推送。

协作窗口仅在此固定合成 owner publisher与原 Approval消费之间关闭；可信owner禁用/绕过触发器或无协作改写所有独立锚排除，默认无Approval的其它资源路由不在保证内。正式ServiceRelease/ParkInstance发布、独立业务审批主体、一般DAG/在途兼容、真实政策/预约/履约/通知/分享/模型/Case完成没有实现或授权。全仓、完整原AT/EX、Windows未验收，Server CI未查询，旧a823a28未迁移；main不动、无强推/部署/凭据或安全网络配置改动。原资料异议与导出不重做。

入口：[实施前合同](CatalogApprovalCoordinationContract.md)、[机器核验](evidence/catalog-approval-coordination/verification.json)、[最终独审](evidence/catalog-approval-coordination/independent-review/report.json)、[首轮阻断](evidence/catalog-approval-coordination/blocked-2cc-review.json)、[开发窗口历史](evidence/catalog-approval-coordination/developer-window-history.json)、[工件哈希](evidence/catalog-approval-coordination/artifact-hashes.json)。实际候选/dev/main与未推送文件另见[正常整合](CatalogApprovalCoordinationIntegration.md)。
