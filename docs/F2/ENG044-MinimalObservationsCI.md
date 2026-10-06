# ENG044 最小对象/最后测试观测与单次标准CI

用户授权仅补两项观测，独立复核/定点验证后连同ENG043普通推送dev/f1-foundation，并监测一次既有标准CI。没有JobObject产品修复、实际权限/身份变化或600s/900s调整；后代回收仍OPEN。原环境及备份保留，预算/真实模型0，R4关闭，F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN。

## 观测合同

ACL原受检对象全部保留，owner/Allow/根继承合同和现有reason不变。只在拒绝时沿已有lifecycle标记附加acl_object=ROOT/SESSIONS/CONFIG；其余既有受检路径没有这三种标签，不能误标ROOT。读取身份失败尚未访问对象时不标对象。内部PowerShell仅返回单个固定对象行，Python拒绝未知/多行/非ASCII/超过32字节的元数据，保留原非零拒绝；不公开SID、路径或原始错误。PS5仅静态审查，portable PS metadata双桩非真实ACL验收。

回归进度的同一≤512byte原子UUID绑定文件写phase和active_test_id；参数部分丢弃，ID必须在现有静态白名单内。重复键、未知ID、非字符串、错误UUID、超限/破损快照整体拒绝为UNKNOWN。超时仅一次读取同一快照，沿现有summary/annotations发布最后成功记录的阶段/ID；它不是确定根因、挂点或失败测试。完成后的JUnit失败ID机制保持独立。

现有1024byte lifecycle标记、8条annotations、每条2048/总16384 UTF8字节含LF边界保持。active ID也占全局25个测试标识预算，整体标识裁剪和省略计数保留；annotation标识去除tests/及.py路径格式。清理覆盖主故障时严格保留合法可选对象字段，避免对象与故障混杂。

## 验证与独立复核

受控PS覆盖三种对象；真实pytest子进程分别在setup/call/teardown停留，使用合成文件及借用的白名单函数名验证去参数ID快照，不声称执行该原业务测试。超时父通路验证只读一次快照；恶意对象/ID、多行、重复键、UUID/长度、ID全局预算及原发布链有定点断言。最终定点264PASS/0FAIL/2既有WARN/24.20s；[证据](evidence/eng044-minimal-observations.json)。最终修改文件hash冻结一致，业务源码/工作流/身份/权限及原600s/900s、PG/app停止代码未变。

两位独立只读复核通过；Windows复核发现初始ROOT误标和主故障字段集合问题，已修并补定点反例。跨模块确认stdlib依赖、原子阶段/ID、超时证据边界、ID预算/注入防护无阻断。未据本地验证声称解决Windows。

## 同步与CI状态

实时只读预检：原origin dev head98012592da107a26c1aa9a06b9b29a1f7a595874，本地ENG042结果/ENG043为其后续提交，没有远端独有提交。普通快进push3提交至8da8e4a95f90965ae06fd4b990abd02e047b4364，并ls-remote精确核验。唯一标准[run37450539320](https://github.com/T1doo/ParkWeave/actions/runs/37450539320)，attempt1、event=push、同head，已completed/failure；不dispatch/rerun、不下载原始logs/artifacts，不换代理或身份。实际终态如下，未再push或运行CI。


## 实际终态及证据限制

唯一run37450539320、attempt1、head8da8e4a，job/check112225754857已completed/failure，最终正常API确认同head仅一run；远端dev仍精确8da8e4a。4条安全notice、最大383/总969 UTF8字节含LF、1测试标识，数量/字节/ID及对象枚举边界实际核验，case省略0。harness2PASS/2FAIL/1NOT_RUN不是pytest计数或阶段签收。

Setup_native外层exit1、BoundaryError/private_acl/ACL_OWNER_MISMATCH/SESSIONS：新最终只读检查已明确SESSIONS owner SID不等于该检查进程当前SID，内部对应exit2。未公开或观察实际owner SID，不能认定其为Administrators/SYSTEM/某账号。SESSIONS owner比较即拒绝，因此其后DACL和后面的CONFIG检查没有执行，不能补PASS；也不据此断言CONFIG安全或DACL需要更改。Doctor/Start及lifecycle API/browser因SETUP_FAILED未继续。

完整回归仍为regression_run/TimeoutExpired、counts MISSING。同一原子快照最后成功记录pytest_call及test_plan_revision::test_after_artifact_and_terminal_run_outbox_atomic_recovery_no_new_call。对应[既有测试](../../tests/test_plan_revision.py#L107)，无参数/原始输出。这个标识不证明其本身死锁、具体回调行、累计耗时原因或后代因果，也不能把本次具体ID追溯填入旧CI。

外层native_suite685.157s、exit1、timed_out=False、cleanup=NOT_NEEDED；发布器及owned PG Stop success，pg_status exit0/0.016s、pg_stop exit0/0.219s、均无超时。外层未超900s，内部600s未改。PG停止与外层结束不证明所有测试后代回收，OWNED_REGRESSION_DESCENDANTS仍OPEN，JobObject方案未实施。

两位独立只读终态复核确认上述边界。下一阶段可对该既有测试的具体等待/故障恢复通路做独立受控复现，后代回收独立实现；不将最后记录当确定根因。本轮没有权限修复。若后续需要改变SESSIONS owner，必须先报告精确对象/目标owner/必要性并获用户确认；不能凭当前owner mismatch顺便改DACL、CONFIG或放宽合同。

本轮终态记录仅本地文档提交，不再push；该结果仅对应8da8e4a源码，不声称后续文档提交经过新CI。原阶段门、R4关闭/真实模型预算0、环境及备份保留。
