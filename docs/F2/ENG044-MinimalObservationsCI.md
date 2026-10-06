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

实时只读预检：原origin dev head98012592da107a26c1aa9a06b9b29a1f7a595874，本地ENG042结果/ENG043为其后续提交，没有远端独有提交。待最终正常快进push及唯一标准CI终态；不dispatch/rerun、不下载原始logs/artifacts，不换代理或身份。实际ACL对象/原因与最后测试ID待该次证据，结果终态后补录。
