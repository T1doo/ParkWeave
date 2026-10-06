# ENG047：已授权新建 session owner 修复（本地完成、同步阻塞）

用户2026-10-06 11:30UTC明确同意最小方案；实现仅Windows测试 `seed-synthetic` 首次创建 `.runtime/synthetic-sessions.json`。`CreateFileW` 使用 CREATE_NEW/share0，不继承handle，按默认安全描述符创建；只请求新文件的 GENERIC_WRITE/READ_CONTROL/WRITE_OWNER。使用专用非 impersonating CLI 进程 TOKEN_USER，在同一独占handle上调用 SetSecurityInfo(FILE, OWNER_SECURITY_INFORMATION=1)，DACL/SACL参数不设置。不启用privilege或改身份，不打开已有文件，不修改CONFIG、ROOT或扩大SID allowlist。依据：[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)、[SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo)。

设置前后读取owner/DACL/control，同当前用户EqualSid验证，DACL字节与全部非owner控制位一致（仅允许SE_OWNER_DEFAULTED位变化）才移交CRT并写session正文。SACL无写入标志，不请求SACL访问/特权。任何创建/设置/验证失败保留新空文件并停止，不重开/覆盖/放宽权限；Linux沿用原排他文件与chmod路径，Windows不再调用无SID作用的chmod。

两位独立只读审查发现并关闭fdopen失败双关风险：`open_osfhandle`移交成功后outer立刻清空HANDLE，再包装文本流；包装/关闭fd失败均不再CloseHandle。低层fake分别覆盖fd关闭成功与失败，保留原异常及清理失败标志。无剩余静态阻断；源码、计数和XML SHA256见[evidence](evidence/eng047-session-owner.json)。

本地最终定点 **129PASS/0FAIL/5WindowsSKIP/1既有WARN/0.68秒**，4份源SHA256一致：owner路径fake及失败排序、已存在拒绝设计、其他路径拒绝、DACL变化拒绝、CRT移交、Job候选、诊断/annotations与准备回归。5个原生用例SKIP分别是1个session owner和4个JobObject；当前Linux不能证明WindowsAPI或真实子树退出。JobObject为ENG046已独立审查的候选，随本分支等待同轮验证，结果必须与owner/lifecycle分列；600/900、runner与权限配置保持。

新环境首次无凭据GitHub根HEAD通过默认网络/代理失败：curl exit7，`Failed to connect to proxy port 8080 after 0 ms: Could not connect to server`（代理地址脱敏）。未换代理/身份/策略或替代网络路线；没有执行远端查询、push或CI。用户已授权普通push及一次原标准CI，但该步骤**待连接恢复**，未取消也未假称完成。推送前仍需实时比较origin/dev/f1-foundation，未知冲突先报，不force/reset。

本轮Setup/Doctor/Start、回归阶段/精确ID、Job原生验证、清理均NOT_RUN/NOT_OBSERVED；上次37450539320的SESSIONS owner失败与最后pytest_call/recovery ID仅为历史记录，不能当本轮成绩。原环境/包保留；实际Windows权限操作0、真实模型/预算0，F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN、R4关闭。
