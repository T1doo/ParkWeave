# Host prerequisites 独立代码审查：限定 PASS

冻结源码 `59f503b1bc98ea4bdbfef4bb216a23e0a15d14b5`；沿用 gpt-6.1-sol / medium。仅只读审查与本目录自有纯反例，没有修改源码/文档，没有 PG、IPC、网络、真实 host 启动或权限动作；原27及根114均未重跑。

独立自有反例 **11 PASS / 0 FAIL / 0 ERROR / 0 SKIP**。根已有窗口 XML 核对 **114 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，与独审计数分列，不相加。新增提交确实只改3文件，增加20个参数化实例、5个注册测试ID；根源码前后hash与当前文件一致。

`inspect_prerequisites` 仅调用 UID/GID记录及路径、文件名、owner/mode/size元数据检查，不读取approval、key、bootstrap、DB内容，不连接、不启动进程、不签发live capability。全部观测PASS时仍返回APPROVAL_REQUIRED；private/SQL项仍NOT_CHECKED，can_start及三个授权/连接布尔均false。自有反例确认结果不能交给start/_spawn/_claim/_publish变成权限，也不改变controller的_live_approval/_consumed/_owned状态。BLOCKED优先于UNKNOWN，异常值不回显。

`_source_metadata_check` 是原 `_code_check` 的完整源码树扫描原样拆出；AST核对成立。真实 `_code_check` 仍先读取受保护解释器并核验hash，再做metadata扫描、逐源码hash验证，metadata PASS不能覆盖内容hash拒绝。原 `_approve`、`start`、action guard、claim/spawn/publish、runtime授权、host ticket和API binding的AST均完全未变。

当前环境仅 metadata 观测为 **BLOCKED**：当前uid1000，指定IPC组缺失，sourceowner1000、interpreterowner65534；private/SQL仍NOT_CHECKED，实际host/IPC **NOT_RUN**。根 observer 在guard范围内forbidden_action_attempts=0；其准备layout阶段先读取了公开源码/解释器hash，因此“不读取内容”的结论精确限于inspect调用，不扩张为整个observer脚本。

**现有保存环境不能在不扩展权限的条件下满足原host。** 原host继续要求受保护的root launcher、既有分离身份与IPC成员关系、root保护源码/解释器/依赖、原签名approval/key/creation/private bootstrap及SQL边界。官方标准runner具有passwordless sudo的根侧资料只意味着潜在的已授权安装机制，不等于现环境通过；root保护、membership及原Case取消所需SQL app rights仍需实际核验，不可由metadata倒推。未采用nobody/gid诊断候选为真实trial身份。

无阻断代码发现。限定PASS只签metadata观测改动和纯反例；真实host/IPC、DB及原Case验收均未签。证据见review.json、static-checks.json、results.xml、stdout.log及自有test_review_probes.py。
