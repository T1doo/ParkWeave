# ENG049：同顺序回归耗时与自有fixture数据库清理

在ab445a9代码基线上一次有效、独立进程的Linux全套剖析：996项，990PASS/0FAIL/0ERROR/6WindowsSKIP，JUnit290.942秒、监督进程292.2438秒，无截止触发。154份源码hash保持。逐项去参数耗时见[evidence CSV](evidence/eng049-local-profile.csv)，汇总见[JSON](evidence/eng049-regression-timing.json)。不把此修改前全套结果称为修改后完整回归。

Linux该轮收集序号579的plan_revision恢复测试call .222073秒，累计结束193.4168秒；preparation的三个参数序号598–600，call .084722/.074337/.079196秒，累计结束207.2141/207.4409/207.6705秒。Windows实际收集序号未观测；最后成功写入的快照移动不证明某一测试挂死。全套setup累计126.532362秒、call145.538738秒、teardown17.793493秒；最长call5.008075秒。每个fixture建库、单事务迁移18版本、seed和授权产生累计成本，但Windows600秒究竟为累计预算、SQL等待还是泄漏仍UNKNOWN，不能仅凭Linux较快定论。

285个1Hz样本：Python主进程活连接最多2，累计打开12784（不含observer），主PG的pg_stat_activity总行最多7（含背景进程），idle-in-transaction/锁等待/blocked各最多1，自有fixture数据库最多1，线程最多5、可见子进程最多3、fd最多20。observer查询1.3762秒，无查询错误。未观察持续累积；短峰值/其他隔离PG/child连接未完整覆盖。最后样本仍在末个fixture中，数据库1/线程3/fd19不是最终零；监督器随后精确回收自有后代独立记录，不能替代数据库最终证明。Linux监督器不证明WindowsJob性质。

首轮私有profiler被已有故障注入的全局os.replace影响，1057ERROR记录无效，保留原始证据，不算产品失败/通过。捕获独立时钟/序列化/写入引用后，故障隔离定点33PASS5WindowsSKIP，再进行上述唯一有效完整剖析。阶段监督阈值32秒含启动宽限、总600秒，无无限重跑或提高600/900。

独立发现common fixture在yield之前迁移失败或TestClient退出失败时跳过DROP。修改前两条故障注入实际FAIL，清理拒绝条目因旧helper未实现SKIP；测试自身finally清理其准确新UUID库。现将成功CREATE之后全部初始化、client进入/退出和yield纳入保护，仅DROP此次成功创建的fixture_UUID；维护连接2秒、锁1秒、statement5秒，不force/终止连接/改角色。清理失败给原异常附类型note，保留原失败。第一次修改后定点7PASS1FAIL是新测试对含note异常使用锚定regex的断言错误；改为严格核验原exception.args和独立note后，最终合并定点139PASS2WindowsSKIP14.23秒（含该三条、两旧目标及CONFIG/session/生命周期/诊断）。此修复不宣称已定位Windows600秒根因。

独立cross_module_review未发现清理修改阻断。下一次已授权标准Windows CI仍保持600/900和runner权限。ENG048内外两个实际Job路径OWNED_TREE_STOPPED与四个专用native性质逐项UNAVAILABLE分列，不自动转PASS。模型预算0、R4关闭、F1/F2未签收，Server不是Win11。
