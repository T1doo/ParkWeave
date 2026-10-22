# 安装包与本地批准浏览器候选

产品源码冻结于 `8944bb31cb8755b693b534f0d78605cc62455ead`；验收脚本冻结于 `f97a2aec3654b34b1b9592606bea8bda771160f2`。本目录 wheel 为 997588 字节，SHA256 `84d566f3644b55b3164855abf64b50ac6cb756be9cd98301951ede1a1c7378bf`。原有 builder 离线构建；独立 venv 从当前已安装的精确锁定分发复制依赖，再以 `--no-index --no-deps` 安装该 wheel，构建/安装期间无依赖下载。不是整个 hosted job 离线的证明。

最终安装态 API 预检实际耗时 11.477 秒：两份独立虚构输入，经原 API/NO_MODEL worker 建立初态，第一份以 API 提出、批准、交付，账本为 PROPOSE/APPROVE/CONSUME，效果数量为组合1/成员3/回执1/claim1/link1。共30 POST（26初态、4API批准交付）、22 GET（含15次启动探测）。setup、API、两个 worker 均使用独立安装环境的 `-I -B`，无 PYTHONPATH/system-site-packages/pth/可编辑导入；前后各核190个包成员，实际观察 setup 打开 SQL、API 打开 wheel 的 web.html。setup PostgreSQL、运行 PostgreSQL、API 均 exit0，标记消失，API端口拒绝连接。

六项确定性 guard 检查另行覆盖请求累计额度、原键与跨Case/外源拒绝、后台主错不可变PASS、主错与清理错并存、setup超时确认清理及停止未确认。它们不是六项产品或浏览器通过。独审发现并修正了后台终态、原键守卫和 setup 超时清理三处脚本P2；最终再收紧wrapper/子进程退出竞态，已由同一组guard覆盖，不重复API业务窗。

`validation-originals.zip` 保留五轮安装API预检的完整已捕获组件、结果、安装来源记录及 guard 源码/输出。前三轮分别因配置 JSON、快照 SQL 列名、API 结束审计未落地失败；第四轮 API-only 通过；第五轮为独审修订后的最终 API-only 通过。没有将这些调试轮次计为额外产品测试。`verification.json` 列每个原件哈希及精确范围，不含会话文件、配置环境或依赖二进制。

当前真实浏览器尚未运行，没有截图或新增 CI run；原 run11 不签本版本。候选拟一次 run12/attempt1：DOM 提出→批准→首次交付，截断一次已成功的恢复GET后刷新页面只读找回原回执，CONSUMED；另一Case明确撤销，另核跨Case/撤销提交409、同原键重复不再消费、同身份READ403清除私有视图及自有API/DB停止。累计计划37 POST/硬限40、GET含探测硬限400、两个worker/一次合成READ撤权；工作270秒、终末360秒、job10分钟，沿用正常Chrome sandbox、已批准固定字体/OFL、10文件8MiB及凭据扫描。暂无 workflow/font gate 切换。

阻塞仅是依赖范围澄清：原 hosted bootstrap 会联网取得现有锁定依赖；“不下载依赖”若仅限定 wheel 构建/安装，可复用；若限定整次CI，则需已有离线依赖来源。异步问题尚无答复，未启动 CI、未下载新依赖或字体。正式来源AT35、Windows原生安装/owner/DACL、真实模型、浏览器本片仍未验。本地来源仍只表示本项目自己的决定账本，合成数据不冒充外部业务接通。

`collection-originals.zip` 是冻结脚本源码后全局与四片实际 collect-only 原件：9445 cases/399 files，2393/2309/2403/2340；稳定身份多重集合精确一致，679条 raw/HEAD 内容绑定。不是9445项测试通过，也不是Windows验收。
