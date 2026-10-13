# 准备探针新目录所有权日志边界修复

冻结源码 **2b4cfd9ed4ec34db913ff7bd6ac6f925f15da44e**，正常独立分支 `dev/f2-prepare-owned-log-fix-20261013`，基于上轮1938db5a50db11457230cfa75fbb1a75927981a9。后续仅追加本报告与公开测试/审查证据，最终交付完整HEAD由远端核对响应给出。两个approval仍false/null/null，本轮不请求或执行新实测，不创建激活commit/执行branch，不复用旧已耗用授权。

原run在root.mkdir成功前已有root变量，EEXIST后异常处理仅判断root非空便按路径保存日志，可能写入未证明属于本次的旧目录或symlink目标。本次仅在root/private分别独占mkdir成功、root owner/正规目录/受限模式/dev/inode全部核验，且再次确认root实例后才将log_ready设为true。此前失败一律failure_logs=UNAVAILABLE，不打开/写冲突路径、不采用旧目录进行prepare或清理。

日志写入进一步使用O_DIRECTORY/O_NOFOLLOW/O_CLOEXEC打开root目录，以相对dir_fd打开private，fstat重核两者的记录实例/owner/mode；只在已验证private FD内O_EXCL/O_NOFOLLOW创建固定0600新日志。日志已存在、链接、实例/owner/mode改变均拒绝，不覆盖旧对象；短写循环、零写失败闭合，nested finally保证log/private/root自有FD在任一关闭失败后仍全部尝试关闭。模式仅允许umask收紧请求的root0711，owner700须保留、不允许增加任何权限位；private0700保持精确。未增加身份、PG、业务、模型或权限动作范围。[原精确资源清单](PrepareOnlyTrialApproval-20261013.md)仅同步这一所有权/日志边界。

根最终相关纯测 **267 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（新边界12+旧255），独审 **21 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（12与根重叠，另9独立负测），不能合并计数。目录和symlink碰撞反例用普通用户真实tmp mkdir/EEXIST及原对象哨兵字节，验证既有T、T symlink、private创建冲突均不被采用或写入；root身份、claim、计时、准备、安全权限及外部子进程动作均DI或guard禁止。其余用虚拟FD核inode/owner/mode、相对打开、日志碰撞、短/零写与关闭失败。未实际执行root安全探针或工作流。

根初轮 **57 PASS / 1 FAIL** 原日志/JUnit完整保留：严格要求实际0711导致umask收紧为0700时提前拒绝，private碰撞测试未到预期阶段；修为只允许安全收紧后相关265PASS。独审发现的close异常跳过后续FD问题经nested finally修复，新增两反例后最终267PASS。独审原9PASS与后21PASS窗口也保留，不以新窗口覆盖旧失败或拼接计数。

源码diff --check PASS。公开纯合成测试/只读审查原件按独审safe-copy-list逐bytes/SHA256归档 `docs/F2/evidence/prepare-owned-log-fix-20261013/`，包括失败窗口和冻结证明；最终收尾归档审查仅留runtime、不递归归档。证据暂存diff --check实际FAIL/rc2，仅root-first原pytest日志和JUnit各一处trailing whitespace；原输出留runtime，保持原件字节，不裁剪或改写为PASS。

原actual run38373923111仍 **1 PASS / 1 FAIL / 19 NOT_RUN、cleanup=false、根因UNKNOWN_NOT_PUBLIC**；本轮准备实测 **NOT RUN**，新修正版也不证明已定位该11秒失败。成功清理与删除后timer失败事实的原资格不变。main/F1/F2、旧执行/候选/失败报告及两轮旧修复交付branch保持原SHA，无强推、部署、浏览器、模型/付费调用、凭据配置或实际安全权限动作。

下一步仅交父级复核本次新冻结源码和完整交付SHA；当前暂不请求新实测批准。任何后续实际运行仍须按已列精确资源与清理范围重新复核，不扩大成完整业务/模型/host组合测试。
