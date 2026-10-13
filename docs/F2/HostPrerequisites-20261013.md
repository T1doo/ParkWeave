# Host 实际前提检查

源码 `59f503b1bc98ea4bdbfef4bb216a23e0a15d14b5` 在原 `LinuxHost` 增加 `inspect_prerequisites()`，直接检查当前进程、既有账号/组、源码和解释器/依赖的保护元数据。检查不读取审批/key/bootstrap 或源码内容，不连接数据库、不启动进程、不改权限；即使全部可观察项 PASS，也只返回 APPROVAL_REQUIRED，`can_start=false`，不发行 capability。原 start/approval/runtime 保护保持；真正启动仍核完整内容 hash 和签名。

**当前真实元数据结果 BLOCKED，host/IPC NOT_RUN。** 保存环境 UID/GID 1000、无 supplementary groups，所需 `pwci_ipc` 组不存在，仓库源码 owner 为 1000，解释器 owner 为 65534。账号/组候选仅用于诊断，未采纳为 trial 身份。审批/私有输入和数据库/业务 ACL 均 NOT_CHECKED。实际观察脚本在准备 layout 前读取了公开源码/解释器 hash 并调用只读 Git；`forbidden_action_attempts=0` 仅覆盖受 guard 的方法调用，不能称整个脚本没有内容读取。

精确阻塞：

- 原 host `_approve` 必须 euid0；还须不同非 root API/writer 身份、既有共享 IPC 组成员资格、root 保护的完整 source/interpreter/dependencies、root 私有签名审批与数据库创建证明、writer 私有 DSN/key、sealed FD 和 host 观察的双端点。当前没有这些满足合同的预置条件。
- [GitHub 官方 runner 说明](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)确认标准公共仓库 runner 免费、Linux 提供 passwordless sudo；这仅说明技术能力，不证明本项目预置身份/组/私有输入已满足，也不授权新增这些配置。旧 controller 实际使用 useradd/groupadd、chown/chmod 和私有密码/key 准备；两次旧一次性入口均已消费，不能复用。
- 旧 worker 的 app SQL 角色仅 SELECT 及 authorization_audit INSERT。原取消需要资料/dispatch/Case 行锁以及 Case/local lifecycle 状态和事件事务写入；旧 app 无这些技术权限。需先审核最小业务 SQL 权限或独立业务连接方案，同时保留 app 无 assignment/identity/control-system 写权，不能直接采用宽泛授权。

因此本轮未启动新 runner、sudo、host/IPC/PG、身份/组或凭据配置，没有用同 UID reference 或模拟结果替代真实链。后续若提供已满足上述条件的受保护环境，或另行明确批准精确临时身份/保护/私有输入及最小 SQL 范围，才可独审一次最多 25 分钟的真实 host→原普通 Case→首次接单前取消验收。

本轮主测 **114 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，覆盖完整原纯 restricted adapter 模块、新 20 个边界用例及诊断白名单一致性；3 个受改路径前后 hash 无漂移。独审自有 **11 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，原授权/启动/runtime 13 个关键函数 AST 保持，结论限定 PASS，不与主测相加。原 27 项真实 PG/Case 验收及旧失败档案均未重跑或修改。

证据：[实际当前环境观测](evidence/host-prerequisites-20261013/root/actual-environment.json)、[独审](evidence/host-prerequisites-20261013/independent/review.md)、[完整性清单](evidence/host-prerequisites-20261013/manifest.json)。功能改动仅原 host、相关测试及 5 个测试 ID 注册；本报告保留 BLOCKED/NOT_RUN，不签完整 host 链。
