# 普通资料事项 CaseStep 业务准入合同

基线 `7b98f454bee96947f2bc1c824a2b50c10939e77a`。沿原V1§5.5/F2-T04，普通应用在已有合法资料事项上分派一个本地人工回执步骤，获派执行者本人接单/回执，企业独立核对，原站内通知打开及已读；API/worker重建后读取同一原记录。本片不代表全Case/P1–P5目标完成、现实履约或正式AT35。

## 普通业务准入

显式 `PARKWEAVE_CASE_STEP_MODE=CURRENT_PREPARATION` 选择原资料事项的步骤办理路径；缺省保留原默认路径，未知值拒绝。选择仅决定业务路由，不发行权限、permit或批准。API与原worker调用同一个配置函数；与任何Native read/write配置、isolated provider、正式来源及独立demo/provider互斥，启动或当前操作发现混合即拒绝，不捕获Native拒绝fallback。

仅消费原LOCAL Store、已安装原业务schema、当前合法会话和同园区/企业的既有preparation/Case/成功case.create Run/VERIFIED operation。企业为记录owner，历史READ须当前READ/PREPARE，新业务写须原EXECUTE；专员为记录reviewer，当前READ/REVIEW_ASSIGNED；执行者为既有同域service_executor且当前READ，接单后只访问原步骤。分派是专员对原本人资料事项的一次显式业务OFFER，不写任何身份、Grant或Run访问授权。目录、资料确认、业务fence与原P1/P2门复用；缺合法输入准确拒绝。普通SYNTHETIC无需正式外部五证明，原协议仍只接受明确SYNTHETIC资料服务。

普通服务从当前数据库原preparation确定参与方，不依赖全新空库、进程内fixture nonce、预配置参与者白名单或发行对象寿命。现有IsolatedCaseStepAssignments的发行门、原marker及其有效窗全部保留，普通路径不得读取、转换或接管其历史。任意active/inactive run_assignment、Native列历史、legacy dispatch/receipt、混合/未知/损坏marker继续拒绝；不删除历史消除拒绝。原Native与legacy guard保留。

## 共用事务与持久性

复用原CaseStep业务事务、CAS/原键幂等/ACCEPT→receipt CREATE证明、最小投影、最终锁等待后的权限/来源/期限检查，不复制另一套办理算法。原表/event/outbox/inbox不迁移、不新增权限表。普通原OFFER记录独立可辨的业务合同、精确preparation/Case/Run/owner/reviewer/executor、资料修订/hash、目录hash/xmin及身份/Grant代际；合同标签和编号只标识原业务记录，不授予权限。完整原首事件/fingerprint/后续前缀证明仍必需。

首次OFFER截止取数据库时间起最多300秒，写入原事件，后续API/worker进程均只能读取该原截止；重启、同键重试、撤销恢复、材料恢复、重新配置不续期。每Case仍仅一次OFFER，无续授/重派；无自动ACCEPT/回执/ACK。执行者在撤权、材料/目录/身份代际变化、截止或终止后不可读写。owner/reviewer按当前本Case权限读取最小历史、OPEN/MARK_READ，不继承隔离provider的1小时寿命；过期历史不变为可办。WITHDRAW按当前负责专员READ/REVIEW_ASSIGNED和原事务终止，不依赖被终止执行者权限或原offer仍有效；ACCEPT/SUBMIT/ACK等新业务继续受原首次截止与完整当前代际约束。每事务上下文局部不可变，不把不同Case参与方写入共享服务对象。

原通知队列在LIMIT前隔离普通/旧隔离/legacy lane；普通consumer仅处理本业务合同，不能消费或SUPPRESS旧隔离及未知原件。完整证明后才能按当前recipient权限送达或SUPPRESS；重复消费/OPEN/MARK_READ不重写首次时间戳。API和worker独立重建可处理同一原普通事件，不需要共享Python对象。过期执行者拒绝/抑制，owner/reviewer保留当前有权的最小历史。False只表示一次有界扫描无进展，不保证排空。

## 验证及保留边界

必须有独立普通configured_app子进程和原worker进程，普通API启动前仅原自有合成fixture准备既有身份/Grant/目录；运行期经原接口创建资料业务，不用fixture发行CaseStep依赖。从原列表按钮导航验证OFFER→本人接单/回执→企业核对、站内通知→打开→独立已读；API/worker重启读取原UUID/时间戳/截止且不新增权限。完整HTML Node VM配真实loopback HTTP/PG可验证DOM交互，不冒称真实浏览器。

定向负例含缺/撤销PREPARE或REVIEW_ASSIGNED/READ/EXECUTE、错owner/reviewer/组织/园区/执行者、代际ABA、材料/目录变更、原offer到期、终止、旧隔离marker/legacy/Native污染、默认与混合配置、并发重复消费及锁等待跨期限回滚。保留失败原件；上片69和原129不整批重跑或转计。

可设计项目自身合法初始化接口及在自有合成fixture验证，但本片普通启动不seed、不修Grant、不迁移、不建真实身份/目录/批准/凭据。实际首次管理初始化仍需明确既有管理主体、目标和授权清单，生产writer安装/policy/key/独立审批另属原受保护流程；不安装、不扩roles/权限、不重试root/seal拒绝。真实浏览器、Windows、正式AT35、真实来源/业务、模型及外部消息均NOT_RUN；项目未完成。
