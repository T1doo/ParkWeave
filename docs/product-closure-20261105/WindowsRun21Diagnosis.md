# Windows 隔离运行 21：组属性的精确失败点

运行：https://github.com/T1doo/ParkWeave/actions/runs/42038672968

用户授权使用 r7 定位一次。已持续跟踪到 completed/failure，无自动重试。源码 7602ccac0e6a2de762ff41cf4035aa35dd6240db，approval 4629d7c15f0a46f0ae39c88ceb33be463fbc1469。

## 这次取得的新事实

云端精确构建、传递、源绑定、私有解包和 CRT 检查通过。新增去敏诊断定位到 restricted_token_candidate._check 第 182 行，即组属性逐位相等检查；TokenFailure phase=QUERY_3，winerror=null。查询 API 已返回，随后软件自身谓词拒绝，不能归为 Windows 权限 API 调用失败。

原始去敏结果：windows-run21-native-result.json。工作台未启动，initdb、办理、重开未完成，整体 NOT_ACCEPTED。清理仍有拒绝记录，不宣称正常退出。

## 已审阅的语义与修正

微软 CreateRestrictedToken 规范规定，被禁用的 SID 转为 deny-only，清除 SE_GROUP_ENABLED 和 SE_GROUP_ENABLED_BY_DEFAULT；其他属性不用于该禁用行为。官方说明：

https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken

原实现要求被禁用组的全部其他属性位原样保留。改为只接受安全单调的变化：

- 仅明确指定禁用的组允许移除原有属性；必须有 DENY_ONLY，两个 ENABLED 位必须为零。
- 除 DENY_ONLY 之外，不得添加任何原来不存在的属性。
- 未指定禁用的组仍须逐位完全相同；组 SID 集合与用户/主令牌类型不变。
- 派生权限只能是原权限的子集；除已许可的 change-notify 之外，任何启用的权限仍拒绝。
- 不修改输入快照，不签发启动能力，也不放宽 owner/DACL、源授权或生产准入。

注意：run 21 的日志没有记录具体哪个组及前后位值。因此这是一项有规范依据、对应失败条件的兼容性修正，不能预先宣称它就是 runner 唯一根因或已完成初始化。新增组失败诊断仅输出 REQUESTED_DISABLED/UNCHANGED_GROUP 分类及 uint32 属性值，不输出 SID、令牌或 ACL，以便后续仍失败时精确区分。

## 本地证据与边界

相关 52 项测试通过，包括允许 OWNER/MANDATORY 等原有属性移除、禁止启用位或新增属性、未指定组不得改变、组成员/用户/令牌类型及权限护栏，以及去敏诊断回归。全部为受控快照/源码测试，不是实际派生令牌或完整原生办理通过。

第 21 次的单次授权已经使用；未自动追加下一次运行。

## 冻结的 r8 候选与下一次范围

本地临时提交 `5b0be26846cbab86e732e90a796f33cf02ae89af`；执行记录 null、工作流 disabled，未推送。

r8 已构建完成，53,760,849 字节，SHA-256 `aa9c56c04562d81261486af3aa89c181b4d4c3b7411f02371130a76321a6506c`。精确 manifest 记录在 ci-frozen-candidate-r8.json。

若用户允许再一次隔离测试，使用此冻结源码和包进行新的单次绑定；仍为现有临时分支、最多 25 分钟、合成数据，不改 main、不发布部署、不接真实数据/模型密钥，失败不自动重试。目标为验证修正后的组条件能否通过实际 runner 并继续后续初始化；如果仍有其他组差异，只取得有限属性值诊断，不自动扩大允许条件。
