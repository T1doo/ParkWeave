# 单次host→Case候选：完整wheel锁与useradd边界修正

新冻结源码 **e99bcf24e3da4cab6feee05e21f3a4d4fcaca3b7**。它替代旧源码8ea7060509e6e91aacaf06a2bce7f14997225000、旧候选b1045910bc2ad51242fbc8d743a6895a0d7b17c7作为下一次审批依据；旧commit、旧报告及43项旧原件保持历史原样，不激活旧候选。最终交付HEAD由远端核对及交付响应给出，后续仅本文/公开证据追加，审批必须绑定新的最终HEAD。

原五个顶层版本不足以固定传递依赖。现在仅支持固定标准ubuntu-24.04 / Linux x86_64 / CPython3.12 / manylinux_2_17，`dependencies.lock.json`和`requirements.lock`锁定完整19包版本、唯一wheel文件、官方SHA256/bytes、原Requires-Dist和选定闭包，psycopg仅binary extra。普通用户只下载公开wheels，逐项读取项目PyPI JSON核官方hash/size，离线验证真实19wheel集合/字节/hash/metadata；不安装包，不做root动作。完整锁及wheel约束可复核，不以本机已有包代替新锁。

未来经批准的bootstrap在保护的新T/source内加载锁：pip download固定cp312/manylinux_2_17目标、require-hashes/no-deps，下载仅T/private/wheels；离线核精确19集合/bytes/hash/metadata后才用no-index/find-links/require-hashes/no-deps安装至新site。顶层与全部传递版本均已显式固定，不动态补依赖，其他架构拒绝，pip两阶段各90秒。解释器/源码保护、默认关闭和原owner证明逻辑保留。[审批清单](HostCaseCancelTrialApproval-20261013.md)已更新具体锁与阶段边界。

useradd新增`--no-log-init`，纯DI逐项对比两条完整命令，禁止初始化既有lastlog/faillog UID条目；`--system`仅改变system账户行为，不能替代该标记。[shadow 4.13原实现](https://github.com/shadow-maint/shadow/blob/4.13/src/useradd.c#L2054-L2064)明确由`!lflg`控制这些重置。本轮未执行useradd/groupadd，未修改系统日志/权限或账户。

根最终相关纯测试 **132 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（新依赖/命令11、旧candidate62、diagnostics59）。首轮 **131 PASS / 1 FAIL**保留：合成EmailMessage自动折行导致测试wheel的Requires-Dist与原锁字串不符，修为原字串后同ID通过；真实19wheel离线校验未发生该失败。独审新纯测11PASS与根重叠，单列，不相加；独审额外核19真实wheels的hash/metadata/Requires-Python/目标tags/标记extra/闭包。独审未发网络请求，仅比对根已获取的官方PyPI投影，不能宣称其亲自访问官方网络。

执行状态仍 **21 NOT_RUN**，不签实际root安装、真实host/ACL/Case组合、传输丢包或SIGKILL全清理。approval仍false/null/null、执行分支未创建；无runner、临时root安装、OS安全设置、SQL权限、随机凭据配置或激活。本轮依赖下载和公开元数据读取不授予未来执行权限。

唯一待批准激活差异仍仅原approval.json三字段：approved=true、source_sha=本轮最终交付完整HEAD、approval_ref=USER_CONFIRMED_HOST_CASE_SECURITY_ONCE_20261013；父任务须先取得具体清单安全动作确认。不得绑定旧SHA、改源码、再跑旧入口或追加授权范围。
