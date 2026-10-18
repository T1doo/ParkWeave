# 已有资源方案批准：可信宿主只读通道

基线 `2e3cc3023c42fcbacae1e8bef5a34e8061644d82` 已获父级有限独审通过，普通开发分支 `dev/f2-resource-approval-host-read-20261018` 接续原 F2-T03/T04/T07 的已有记录接入。当前代理唯一写源码/Git；独审代理只读或在明确冻结后用私有镜像独测。没有创建真实身份、Grant、分派、目录、批准、凭据、信任根或部署。

## 本片完成的生产接口

此前 `configured_app(resource_plan_approval_provider=...)` 只允许可信 Python 宿主传回调；已有批准的正向证据是进程内工厂组合，普通子进程缺 provider 只能不可用。本片增加 `resource_approval_host_read`：普通工厂可以从显式公开配置构造只读 client；独立可信 host 可以把**已经存在的合法 adapter** 接到固定 dispatcher。仍没有真实来源 backend 或 host 安装器。

`PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG` 最多16KiB，仅有三个字段：

| 字段 | 内容 |
| --- | --- |
| `schema_version` | `parkweave-resource-approval-host-read/1` |
| `binding_path` | 已获准发布的既有受保护 public binding 绝对路径 |
| `binding_sha256` | 上述原字节的精确 SHA256 |

拒绝重复键、多余字段、布尔摘要、相对路径、凭据、模块名、任意URL或写入开关；同时提供该配置与 Python provider 也拒绝。未配置保持原行为；配置存在但无效则启动失败，不退回看似可用的 provider。加载器不发现来源、不连接数据库外的网络、不安装服务或从环境加载代码。

public binding 的固定 schema 为 `parkweave-resource-approval-host-binding/1`。字段为 `source_id/source_kind/backend_contract_id`、`api_uid/api_gid/host_uid/host_gid`、`socket_path/socket_device/socket_inode`、`host_pid/host_started/boot_id`。backend合同ID是宿主已知 adapter 合同的公开标识，并非自报证明。生产加载只接受 `EXISTING_AUTHORITY_ADAPTER`；要求现有 root 保护的常规文件及祖先、精确摘要、不同的非root API/host UID、实际API UID/GID和既有IPC组；每次RPC前后重读该受保护pin。socket祖先限原保护主体，socket须0660、原device/inode/owner/group；核实际进程四项UID/GID、启动代次、系统boot ID、连接后SO_PEERCRED及路径无symlink。任一项未知或变化均拒绝，没有65534/rootless/Windows降级。

这些检查只证明连接到了被既有 host pin 指定的进程，**不证明该进程收到的业务记录真实或批准有效**。已有来源真实性、批准主体授权依据、当前head与撤销由独立 adapter 的 `verify_existing` 继续完成；transport不能以正文的APPROVED/verified或自己的响应关联SHA替代它。

## 固定只读协议与预算

本地 Unix stream RPC 仅允许 `READ_EXISTING` 和 `VERIFY_EXISTING`。请求绑定完整原 `Lookup`（Scope、当前viewer、可选原批准ID）、source/backend合同、pin SHA和随机请求nonce；验真请求另带原文及SHA。响应必须精确对应请求SHA、nonce、pin和来源；拒绝重复键、截断、额外字段、非法类型和超限。源原文最多64KiB，wire frame最多128KiB。错误只给固定不可用代码，不回显来源正文、异常详情、令牌或密钥。没有COMMAND、APPROVE、ACTIVATE、CONSUME、URL读取、重试或第二来源fallback。

一次原批准读取的2READ＋3VERIFY共享2秒单调时钟预算；中间的固定原ID二读、当前身份/来源复核及最后验真不会重新起预算，最后post-pin检查后及返回前再次检查期限。首次READ和首次VERIFY沿原算法尚未解析批准ID；之后的二读和后续验真固定原ID，错误原ID仍由原 `_read` 拒绝，不能退回latest。并发请求使用独立ContextVar窗口，嵌套窗口拒绝、退出清理。预算限制的是该轮RPC的允许时段；不承诺阻断内核文件系统调用或原PG检查的硬超时，也没有给任意Python回调套一个无法安全停止的后台线程。

host 的 `ReadOnlyDispatcher` 只转发既有 reader/verifier，不生成、签发或写批准；server接受**已有监听descriptor**，检查原path/进程身份，并校验来连API peer，最多8个处理线程。没有bind/unlink/chmod、身份创建、进程启动、代码加载或自动发布pin。来源adapter须自行限制IO；阻塞adapter最多占这8个host处理槽，client预算到期会关闭API侧RPC，不能无限延长API事务。stop只停止accept循环，不宣称能取消任意既有backend调用或替宿主完成部署/回收。

## 继续复用的业务门

原 `runtime.selected`、`preparation.entry_context`、`ApprovalRecord/Scope`、原初次采纳证明、P1材料/目录来源、权限xmin代际、数据库绑定、两次原文比较、当前主体与批准者权限、最终source head和DB时钟均保留。新增 `ReadOnlyApprovalProvider.read_window` 是可信宿主的IO生命周期接口，默认None保持旧provider行为；不提供任何权限。

结果仍固定 `execution_authorized=false`、`approval_consumable=false`、`decision_writes_enabled=false`、`run_read_access_granted=false`、`production_installation_verified=false`。原P2 action_scope仅注册动作定义，不能当某份Deliver正文、资源组合、时段/数量/费用或原子消费批准。没有接入 `IsolatedPlanApproval.before_delivery/consume`，没有绕开它的隔离fixture门；Run READ访问批准也不能替代资源方案批准。

现有入口仍要求明确SYNTHETIC Case/Run/资料/目录。本片没有把它们改成REAL。`formal_preparation_entry` 的未知专用来源合同仍保持UNAVAILABLE、reader/verifier均不调用；新的只读通道不解除该门。

## 可继续编码与必须取得的输入

| 范围 | 已可由本项目编码 / 仍需实现 | 来源或运维必须给出的既有输入 |
| --- | --- | --- |
| 可信provider跨进程接线 | 本片已实现公开pin加载、固定client/dispatcher/listener组合及工厂接线；无需先创建真实权限 | 已获准的受保护public binding、既有API/host UID/GID/IPC组及可读/proc/Unix socket实例、host adapter组合 |
| 具体批准源backend | 应据其现有协议实现只读查询、原ID选择、验真和有界IO；本仓库尚未提供真实backend | 来源source_id、现有只读接口或脱敏文件结构、原记录ID/revision、明确方案/动作/来源绑定、原批准主体及授权依据 |
| 批准当前性与真实性 | 应实现来源专用签名/发行者与current-head/撤销核验；不是transport响应关联 | 已存在的公开信任/验证协议、签名覆盖与canonical规则、当前head/撤销接口、UTC有效期语义和用途限制；不要求私钥或新凭据 |
| 正式资料/Case/Run/采纳方案 | 专用解析/核验、四对象关系、主体映射、正式来源指纹及批准映射仍须项目实现；不能删SYNTHETIC判断代替 | 规范source_domain；四对象稳定ID/类型/关联；owner/reviewer/park/org；revision/服务版本/指纹算法；既有采纳决定、Run回执语义、当前主体用途/字段授权及撤销合同 |
| 当前本地既有记录读取 | 继续原受限DB/会话/READ、本人PREPARE或原REVIEW_ASSIGNED、精确Case/Run/已确认材料/目录/含P2的原采纳方案 | 合法已有记录及受限DSN、原身份和当前权限；此类本地Grant不自动证明正式源主体授权 |
| 正式批准消费与资源执行 | 本片未实现；须另做精确Deliver绑定、独立审批权、旧批准撤销/原key幂等消费及资源同事务协议 | 上述动作的现有授权/批准语义与来源合同；只读VERIFIED或测试批准不能补齐 |

来源提供方应先提供上述结构、公开协议说明及有权使用的脱敏样本；拿到后专用adapter/映射/核验代码仍由本项目开发，不能泛化为“只等外部凭据”。正式数据可通过独立只读来源接入，不必先迁移现有合成表；若要在本地持久化正式对象，需另明确迁移/存储合同。

## 验证范围

本片正在开发验证。最终源码冻结、完整模块实跑、独审、raw/public哈希归档和实际远端结果在收尾补记；开发失败不改写为通过。

正向测试明确使用SAME-UID `SYNTHETIC_CONTRACT_FIXTURE` lab，仅替换 `_load_binding` 的生产安装边界；真实socket/peer/进程、固定协议、普通工厂、PG/API和原页面仍实跑。未修改的生产loader实际拒绝该lab。当前沙箱 `/` 与 `/tmp` 的owner为65534，不能证明root保护的真实不同UID安装；另用仅protected-file DI测试身份拒绝分支。这些都不创建真实批准或宣称真实来源成功。Windows/Win11、正式AT/AT35、真实业务/来源/批准、正式host部署、模型和现实资源履约均未验，完整项目尚未完成。
