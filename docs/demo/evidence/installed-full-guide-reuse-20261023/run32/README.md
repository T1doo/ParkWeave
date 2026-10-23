# run32：安装态完整本地办理与独立复用候选，实际失败

受测源码 `04502e1df34d4e2a3a376070335d4bcb8889270f`，tree `7be1240653a6640a183a21ac8f9e0b5ac383dcfd`，parent `2bb03bdfd3047813e112f9058761c4decfa84258`。[官方run32/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39898433308)，job `120234158439`，唯一执行 **FAIL**，未自动重跑。只新增验证驱动，并改workflow/font/run绑定与原始指纹；src/tests、旧驱动／监督器／最终化未改。本次不是产品新增，也没有完成39次闭环。

冻结目标是同一隔离合成实例、原安装态DOM办理：A企业首办→专员审核→企业确认采纳→P1显式VERIFY→3份HELD及LOCAL提出／批准／交付→P2 VERIFY→专员分派／执行者接单→P3 VERIFY→执行者SUBMIT／企业ACK→P4 VERIFY→本地REVALIDATE／关闭→P5 VERIFY→目标／TXT；B空材料目标先复制A原目录，再提交独立诉求，经独立REVIEW／CONFIRM／ADOPT后仍未办理。设计A30+B9 DOM POST、其中4无key纯预览和35唯一key写入，仅为候选合同，不是本次实测成功数。API准备写入在驱动中为0，实际完整计数因下述报告缺口未保留，不冒称已被运行计数证明。

实际A通过准入时根270秒钟已用10.819秒，预留235秒；A监督器约 85.114秒后记录work_wait TimeoutError，operation_status FAIL，worker_returncode -15。监督器原85秒操作截止／90秒含清理上限未改。根报告ADMIT_A的AssertionError是子进程失败后的控制器断言，不能当作具体业务接口错误。工作进程没有写出最终browser-result-A，root responses/screenshots为空、request_budget/current_control缺失；这表示进度记录缺失，绝不表示0业务请求。本次无法精确确认最后请求、成功数量或原拒绝正文。B未准入、worker1未启动，没有目标/TXT产物。

官方附件仅5文件：2张原1200×1000 PNG、wheel、组件日志、result。作者与独审查看原图：01显示LOCAL方案已批准，保留合成警示；02显示执行者当前人工合成回执v1、全文和内容hash，仍待企业核对。第一图在交付点击前，第二图不证明企业ACK或后续VERIFY。无A五目标图、B390图、TXT或failure-guide.png。截图不能拼接旧run称闭环通过，也不代表整页视觉／正式来源／真实履约通过。

构建安装wheel无下载；hosted bootstrap沿现有锁文件与批准固定Noto/OFL另列。191包文件已从实际wheel逐字对受测Git及安装manifest，setup/API/worker0各2次隔离证明，worker1无运行证明。实际9个自有绑定进程均已退出，subtree_complete true、remaining子进程／session空；监督器对4个出生校验pidfd发送SIGTERM是本次清理事实，非全程无信号。API／PG／wrapper均exit0、监听REFUSED、cleanup_errors空。只一代PG，没有冷启；临时目录保留，不能签目录删除。附件扫描在根起点 96.683s，终态result FAIL＋官方job/step failure＋exit1；stdout PENDING_FINALIZATION不是PASS，summary正文未独立读取。

执行预算未扩：10min job、依赖3min、270s根工作／360s发布、每段原90/85s监督；40POST／400GET／2业务worker，最多10文件8MiB。只运行一次attempt1，不自动补跑，不改sandbox/CSP/权限。6组离线边界和假SDK故障检查、23个JS解析、74个静态ID检查、761原始指纹均准确另列，非真实浏览器成绩／pytest数量；未重复旧大套件。

确定下一缺口是失败诊断保全：当前仅worker finally写最终报告，原监督器截止终止时会失去在途请求／阶段账本。需先最小持久化已脱敏进度，再据实际阶段分析A耗时；不能以缩短必要等待、改原监督器或放宽断言掩盖。具体产品失败尚未知，本轮不重新执行。Windows/native、正式source、LIVE、正式AT35与C0均未由本次代签。

[完整官方日志](ci-original.log)为API原工具返回全文，非CLI截取：208949字符／210867B，SHA256 `f0e8dbd89cb0376163524077bad80959b81aafa8a0317fc76580a493f3e4d7b7`，5段存盘回读逐字一致，独审另核原件。官方artifact.zip 1429643B，SHA256 `5101afd0b19b3e37d977d7e98132085cffba10a86020c63ab73d2aaf4593438b`。内部ZIP保留原5成员不改；外层[证据包](evidence.zip)另含官方run/job/artifact元数据、同份全文日志、冻结驱动、离线检查、发布证明、wheel核验、实际独审、visual-review、validation和checksums，不执行其中候选脚本。

外层ZIP 1560387B，SHA256 `414bac40b07259251cd35ba6811a16c035dda842f18216bdbf1ebe104fabf3a9`。普通Git整批非强推发布源码已回读，无blob待批、新凭据或持久安全配置。
