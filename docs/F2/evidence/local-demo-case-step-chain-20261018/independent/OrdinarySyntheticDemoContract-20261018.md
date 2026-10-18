# 普通合成演示：独立初始化与保留式启动

基线 `6067cd3070ef3987d9013b1f47768df667d3f612`。原设计§4.1、§12.4、§15及开发计划F1-T01/T03、F2-T06/T07、§13允许明示合成目录与可运行软件，不把正式来源协议缺失扩大为全产品阻塞。

已核原 `test_ordinary_case_goal_results.start` 从新资料/诉求调用旧确定性 planning-preview、明确 ADOPT，再接普通P1–P5。无需重写规划、放开V4/demo与CURRENT_PREPARATION的互斥，亦不使用旧Case或Run assignment完成演示。现有source-only ZIP不提供全新数据库配置，material-only启动器只有资料整理；本片不重复打包或替换两者。

新增独立Linux SYNTHETIC启动器：`setup`仅新建一套自有私有`/tmp/parkweave-ordinary-demo-*`集群/库和必要初态，`serve --state-dir`仅核对并复用该状态。普通API/worker不隐式setup/迁移/seed。无DSN、身份、权限、文件或SQL导入参数；不能选择或收编既有真实库。用户无需手改数据库、目录、Grant、pack/journal。安装与日常启动分离；失败保留状态/日志，不自动重试新建、删除或修复。

复用现有material-only的私有socket PostgreSQL进程/精确child停止和普通worker；不改其历史一次授权/状态。初始化仍走原fresh SYNTHETIC capture→CREATE→同进程receipt→Store.migrate32，不发明production receipt，不改原SQL/roles/schema/Native或默认来源算法。新集群只监听私有Unix socket，HTTP只127.0.0.1，既有非rootLinux/Python/依赖需先可用，无安装下载或安全网络权限扩大。

新初态精确为3个明示合成主体（owner、reviewer、executor），4条READ/EXECUTE capability、owner case.create、PREPARE/REVIEW_ASSIGNED、1条SYNTHETIC资料目录、2条SYNTHETIC资源及owner每资源READ/HOLD。field_grants、run_assignments及全部业务记录初始为0；无批准、分派或既成事项。所有技术ACL仅限新拥有的合成集群app角色，不给owner/superuser、身份/Grant/目录写权限或Native writer通道。会话仅私有文件保存，stdout/URL/仓库不含token或DSN；本地测试会话不自动到期，停止服务不等于撤权。

serve核源文件内容摘要、schema32、原集群system identifier/数据库OID、初始权限/目录/资源摘要与文件私有性；变化准确拒绝，不补配置、撤权恢复或重发旧receipt。源码绑定不要求Git元数据，必须包含产品运行文件、当前启动器及所用生命周期辅助文件；仅源码/文档提交变化不凭空给业务授权。状态marker只是自有合成现场绑定，不是生产信任或管理员批准。未知postmaster/锁/监听器不接管、不删、不杀；只停止本次实际创建的精确子进程。确认不了停止则保留现场并拒绝后续启动。

启动显式仅`PARKWEAVE_MODE=LOCAL`与`PARKWEAVE_CASE_STEP_MODE=CURRENT_PREPARATION`，API及worker均用同一受限app。保持Native、formal source、资源批准provider、IsolatedPlanApproval、LOCAL_SYNTHETIC_DEMO/V4 provider关闭，任何原互斥guard不删除/捕获fallback。P2使用原两资源组合及关联，不借严格资源批准路径。V4注册选择/模型与普通CaseStep组合不属于本片，不冒称已完成。

验证以真实启动器产生空业务库为起点，通过实际普通API与worker新建Run/Case，用户明确新诉求/双材料/REVIEW/CONFIRM/ADOPT，再原P1核验、两资源组合关联/P2、专员OFFER/执行者本人ACCEPT/P3、人工SUBMIT/owner ACK/P4、本地REVALIDATE/CLOSE/显式P5与原核对TXT；重启同一库读回同Case，再提交第二份不同输入另建Case，沿用同一主体的当前全局Grant按原算法重新授权，不复制旧Case/Run、材料或Case专属marker，不新发/续授权限、不写Run assignment。当前300秒步骤期限不续授，过期仍拒绝。新Case和本地关闭不声称资格、外部受理或真实履约。

还须覆盖空库/精确初态、普通app不能改权限、端口占用、旧状态/源码/权限变化拒绝、初始化和child失败保留、停止/重启只处理owned children及marker/截止不重写。独审有限固定oracle及最终SHA；失败、实际命令与导入来源保全。只执行新拥有的隔离合成测试，不执行真实身份/Grant/capability/分派/目录发布/批准/凭据配置/生产安装，不改main/强推/部署/真实模型/费用。Windows、浏览器正式场景、完整AT35和真实业务仍未验；项目未完成。
