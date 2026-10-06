# ENG043 只读ACL检查修复与回归等待调查

按新增授权仅本地修复、合成验证和独立审查；不push、新CI或增加600s/900s。基线为ENG042结果提交d76354d；远端最后确认9801259，本轮未联网改变远端。真实模型/预算0、R4关闭，F1/F2未签收，Server不是Win11、36AT6EX NOT_RUN。

## 已证实且已修复的检查缺陷

旧native_acl_check独立PowerShell没有Stop/总catch。受控metadata/SID双桩执行精确旧脚本证明：Get-Acl读取错误、owner转换错误、第二条Allow身份转换错误均可能最终exit0；最后一种可重复使用前条$id。这些是本地SYNTHETIC代码反例，不能把实际ENG042非零失败解释成相同错误。

新检查直接调用GetOwner(SecurityIdentifier)和GetAccessRules(true,true,SecurityIdentifier)，绕开显示名/NTAccount翻译。脚本设置Stop、Get-Acl ErrorAction Stop并catch固定exit5；空规则集合仍按原owner/root合同验证，null/读取异常拒绝。owner仍必须当前SID，Allow仍只当前SID/SYSTEM/Administrators，root仍必须保护继承；没有放宽合同或改原新目录初始化代码。

现有非零返回分别固定为ACL_OWNER_MISMATCH(exit2)、ACL_ALLOW_REFUSED(exit3)、ACL_INHERITANCE_REFUSED(exit4)、ACL_INSPECTION_FAILED(其他)，沿已有有界ASCII协议输出，不含对象路径、SID、私密stdout/stderr。root reparse仍拒绝。本轮未对实际Windows对象运行Get/Set ACL或调整权限。

Setup在原配置排他写入后新增最终只读检查，将新sessions/config纳入完成条件；失败不报完成、不修复或删除已创建/原有文件。Setup固定诊断沿现有stdout→native_suite→安全annotations传播，不新建诊断层，已有config拒绝的stderr合同不变。PS5语法仅静态复核；本地portable PowerShell的双桩和类型方法反射不是Windows ACL验收。

## 等待路径与证据边界

已有test_native_command后代将缓冲print放在marker前，但未flush，父看到marker时可能尚读不到输出。已改为flush=True再写marker。受控真实进程的旧/新排序反例以release文件握手锁定观察时点，finally仅回收本次启动的进程；此改动修测试观察竞争，不修改产品回收策略。

受控Event/ThreadPoolExecutor实验先确认future.result(timeout)超时，再定时释放任务，证明with退出仍等待运行任务。它不是现有业务测试死锁证据，未据此改变业务SQL/线程池实现。Windows subprocess.run(capture_output)超时后的PIPE EOF风险与run_acceptance普通文件输出必须区分；后代仍活不能单独证明普通文件输出会挂住父等待。没有识别本次实际Windows具体测试或600s超时原因。

OWNED_REGRESSION_DESCENDANTS仍OPEN：ENG041受控实验证明直接父超时后自有后代可存活，当前产品路径尚未修复。没有以本轮flush修复或PG停止替代后代回收证明，也不声称Windows CI已修。

## 独立复核与验证

Windows检查复核确认严格SID合同、只读行为、Setup最终检查和PS5语法未发现阻断；跨模块复核发现两个新反例的调度竞争，已采用release握手及超时确认后启动timer，复核确认无剩余阻断。两位均未修改文件、执行真实ACL或触发push/CI。

相关回归首次195PASS/2既有WARN/20.81s；随后稳定性和Setup suite分支调整的5项PASS。最终冻结完整本地回归922PASS/0FAIL/1WindowsSKIP/2既有WARN/270.92s，148份源码hash与冻结一致；结果见[evidence](evidence/eng043-readonly-acl-and-waits.json)。完整成绩只对应该冻结源码，不代表真实Windows/PS5、F1/F2或全部AT签收。

## 权限审批边界

当前代码修复只改变只读解析和失败判定，无需对实际对象赋权。ENG042具体不安全对象/owner/Allow/继承仍UNKNOWN。若后续原生检查证明实际权限必须变更，应先报告准确对象、原/目标owner或DACL项、必要性与影响，得到用户确认后才能修改；本轮没有可据证据确定的权限变更目标，也未请求泛化权限或实施修复。

原环境、备份、既有运行记录均保留。后续是否普通push/一次标准CI由用户另行授权。
