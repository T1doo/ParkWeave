# 最终 wheel 安装态 · 本地来源批准链 · run12

[唯一一次 hosted run12 / attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39727224730) 限定 PASS，job `119653813456`。实际执行源码 `afe0d53495c171a8f7943497409845255adebb6e`，Chrome `155.0.8059.39` 正常 sandbox；1200×1000 桌面视口。job69秒，浏览器步骤27秒，工作26.739秒、附件扫描截止27.325秒；未重跑。终态依据原附件 result.json 的 PASS 与真实步骤/job成功；stdout 的 PENDING_FINALIZATION 不是终态。其观察对象去除明确的观察字段、对应scan时间后与附件对象精确一致。step summary正文未独立读取。

使用上轮已离线构建的最终产品 wheel，997588B，SHA256 `84d566f3644b55b3164855abf64b50ac6cb756be9cd98301951ede1a1c7378bf`；产品包源码为 `8944bb31cb8755b693b534f0d78605cc62455ead`，所有190包成员仍逐字匹配本次执行HEAD。独立 venv无system-site-packages/pth/可编辑安装；从已准备的精确锁定分发复制依赖，以no-index/no-deps安装wheel。实际setup/API/两个worker均以-I/-B运行、无PYTHONPATH，前后核全部190文件和每个加载的ParkWeave模块来源；setup实际读取安装包SQL，API实际读取安装包web.html。复制的四个可信脚本仅承担原合成实例准备，不能作为工作树ParkWeave导入后备。wheel构建/安装期间零依赖下载；原CI bootstrap网络取锁定依赖及已接受许可的精确字体仍有执行，父级已明确允许，不称整个job离线。上轮candidate中的范围问答现已解决。

两个全新虚构输入的初态通过原API及NO_MODEL worker准备，未冒称浏览器新建输入。当前页面实际完成：

- 第一Case：预检→明确PROPOSE→APPROVE→首次资源交付。提交已成功后，故意只中断一次真实200的原回执GET响应；页面保留原键，刷新页面后点击只读恢复，核得同一资源交付回执并读取CONSUMED。账本PROPOSE/APPROVE/CONSUME；效果为组合1、成员3、回执1、claim1、Case关联1。
- 另一独立Case：预检→PROPOSE→APPROVE→REVOKE，页面交付按钮禁用。借第一Case的批准ID向第二Case交付，及使用第二Case已撤销批准提交，两次受控API检查均409且声明的业务投影无变化，第二份三条holds仍HELD。
- 受控API以第一次原body/原key重复POST，恢复相同回执且不再消费。不是额外DOM提交或并发压力验收。
- 仅在此自有合成实例撤销原owner的一条READ授权；保留同一页面会话，点击读取，两个实际GET403独列，六处私有资源/交付/批准视图清空。

累计37 POST＝26前置API＋8真实DOM（含2只读预检）＋3 API负例/原键重复；77 GET＝57响应事件记录＋1实际成功但被故意中断的GET＋19启动探测。两个403不计成功。24个可信DOM点击、6条业务原键/响应对应证明。硬界仍为工作270秒/绝对360秒/job10分钟、POST40/GET400（含启动探测）、两个worker、一次合成READ撤权、10文件8MiB；无越界记录、无pageerror。

setup PostgreSQL PID2523、运行PostgreSQL PID2544、API PID2552及wrapper均exit0；两个postmaster标记消失，原API端口连接被拒绝。不是全数据库不变或冷重启证明。

六张未改动真实截图已人工及独审核阅：[提出](01-local-proposed.png)、[批准](02-local-approved.png)、[已提交但原GET被中断](03-local-committed-pending.png)、[原回执恢复/CONSUMED](04-local-consumed-recovered.png)、[另一Case撤销](05-local-revoked.png)、[READ403清屏](06-local-read-denied.png)。第3图的“Failed to fetch”来自故意中断GET，不代表POST未提交。中文在这些视口可读；683码点静态集合/两条fontconfig链保持，原根页资源批准与CONSUMED视口各23个实际可见节点有glyph来源记录。原共享helper的rendering_observation_scope仍残留guide/page_ready标签，原result未改；实际详细stage/node记录与截图为准，不签guide、全部683字形像素或手机实机。

官方附件ZIP原件2278403B，SHA256 `46fdc3a44374f68941a22edc9d9a879b6a0d99be55090dff4213e0a3432ec9ba`；九件解压2508858B，wheel也在该原ZIP内。官方API decoded job log原件307147B，SHA256 `317c9b3b82728d16668836dff1a2e373a7d754d7ef4c85fb324364f31c7f66c5`，不是可能截断的CLI log导出。result SHA256 `9a56685c32b21c24fc3d3980298175644a9d7ea304df61c67285013fe183f3c0`。installation-redacted.log是带边界标签的完整已捕获组件输出拼接，不称单一原始流；八段原/公开hash一致。字体二进制、会话文件、私有环境不在证据包。

独审`/root/summary_review`限定PASS，无阻断P1/P2；只读独核原件哈希、安装来源、预算、事务、退出及六图。来源标签残留和summary未独读已明确保留。此次没有新增pytest产品用例执行，不与上轮API预检/六guard或旧run11重复加计。全局及四片collection另留原件：9445 cases/399 files、2393/2309/2403/2340，679 raw/HEAD绑定、稳定身份多重集合精确一致；collect-only不是9445测试通过。

本片不签新浏览器intake、该安装版冷重启、390px批准链、P1–P5完成、外部正式来源/AT35、Windows原生安装/owner/DACL、真实模型、全DB不变。LOCAL批准仅为本项目自己的明确决定账本；合成演示不冒充外部业务系统已接通。
