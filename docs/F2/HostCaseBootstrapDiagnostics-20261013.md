# 离线bootstrap诊断与固定Ubuntu标准库复制修正版

冻结源码 **b71dd9d0329712b581e1c088116eaa7ef7adba63**，独立开发分支 `dev/f2-host-case-bootstrap-diagnostics-20261013`，基于失败报告交付e06311dca0c6133fa807a6cbc8b40597a22202c9。后续提交只增加本文及公开证据，最终候选完整HEAD由远端核对和交付响应给出。approval仍false/null/null，没有激活、CI重跑或任何新系统安全动作。

原bootstrap将资料复制、解释器/标准库、依赖、密封FD、子进程及JSON/schema/source/exit检查全部折叠到PROTECTED_RUNTIME/FAILURE。本版每项都有独立封闭check_id/substage，并覆盖controller前置检查、主要阶段、逐资源清理及私有日志保存失败。公开记录仅 `case/substage/check_id/source/line`；不投影异常消息、类型、trace hash、路径、argv、stderr或凭据。line来自冻结代码对象的严格身份（强引用、is），还须属于该对象实际co_lines编译行集合且0..10000；外来代码、克隆code对象及伪造9999行不能冒充，0表示未知。诊断至多32条，case/source/substage/check组合由固定枚举验证。原异常仍可在已允许的新T/private保留，不将私有trace送到控制台。

普通用户从[Ubuntu官方公开包目录](https://archive.ubuntu.com/ubuntu/pool/main/p/python3.12/)读取四个amd64包：libpython3.12-minimal和stdlib的3.12.3-1、3.12.3-1ubuntu0.17，仅用dpkg-deb读取tar元数据；没有提取、安装或改系统文件。两版本都包含 `/usr/lib/python3.12/sitecustomize.py -> /etc/python3.12/sitecustomize.py` 和 `_sysconfigdata__linux_x86_64-linux-gnu.py -> _sysconfigdata__x86_64-linux-gnu.py`；alias正规目标在同版本minimal包，root/0644。原“一律拒绝”策略确与这两个官方结构冲突。

这不是旧失败根因证明：旧runner实际包版本/文件布局、私有trace及准确失败调用仍UNKNOWN。旧run38373923111仍保持1PASS/1FAIL/19NOT_RUN、cleanup=false，不回填新诊断、不改写旧失败或清理签收。

复制仅增加两个固定例外，要求exact `/usr/lib/python3.12` 根和isolated/no-site `-I -S`：外部site hook只省略，不读取/etc目标；sysconfig alias仅指向同根固定basename，使用O_NOFOLLOW打开、fstat确认root-owned/nonwrite/regular，物化为新正规文件。目标创建O_EXCL/O_NOFOLLOW，处理短写并关自有FD。其他链接、改目标、链式目标、非root/可写/非正规目标全部拒绝；不resolve或任意跟随。19包哈希锁、--no-log-init、原Case写守卫、身份/SQL权限和实际接受边界不变。[清单](HostCaseCancelTrialApproval-20261013.md)已同步这些精确例外及私有诊断边界。

根最新相关纯测试 **207 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（新故障注入75、旧candidate62、dependency11、diagnostics59）；独审最新 **89 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（75与根重叠，另14独立负面），不合并窗口。真实bootstrap/prepare控制流由虚拟文件、子进程和FD注入每阶段失败，真实安全动作被guard禁止；还测清理/私有日志异常、字段污染、代码对象克隆/伪造行、链接链/外目标/权限拒绝。根201/206等旧纯窗口保留。独审首次默认python缺pytest、包目标归属断言错误、错取206窗口为207的审查脚本错误均保留原件并纠正，不隐藏失败、不算产品真实测试FAIL。

独审限定结论 **LIMITED_PASS_OFFLINE_DIAGNOSTICS_FIXED_STDLIB_COPY_AND_COMPILED_LINES**，五个变更路径Git blob/bytes/hash与冻结源码一致，无阻断发现。包兼容性结论限定所下载官方版本的tar元数据，不伪造旧VM运行证据。公开包清单、纯JUnit/日志、审查失败和修后原件、源码hash归档在 `docs/F2/evidence/host-case-bootstrap-diagnostics-20261013/`；四deb二进制只留runtime，公开归档逐bytes/SHA256核对。

最小剩余实测应先只验证新的保护环境准备和受保护解释器导入：仅新T、官方解释器/stdlib固定复制、19wheel哈希下载/离线安装、sysconfig alias与no-site核验、封闭阶段诊断；在真实身份创建前停止，不创建用户/组/PG/角色/业务数据或随机凭据。此prepare-only新入口尚未实现和批准，须先形成单独可审入口及精确范围，取得新的一次授权才可执行。准备通过后，原host→Case取消21项组合验收仍是另一个剩余实测范围，不能用本轮纯测替代。

本轮没有生产部署、真实模型/付费调用、凭据或网络配置、权限扩大、强推、浏览器尝试或旧CI重跑。旧执行入口9a5808b01b807712d272c6180990cc2e3969b1d7/run38373923111许可已耗用，当前代码不复用该入口来试跑；main/F1/F2及旧候选、执行、失败报告远端均保持原SHA。最终交付响应提供新的源码/候选完整SHA、远端一致及未提交/未推差异。
