# 普通人工回执 SUBMIT 原键只读恢复

本片续接 F2-T04/T05、AT18–20；基线 `d5f69a8fe9f0d8860c0325d46a035a7dbbb7f49f`。它补足已有普通人工回执的未知提交恢复，不代表正式来源 backend 已接通。现有人工提交、企业决定、分派、规划与授权算法继续使用；不新增身份、Grant、分派、目录发布、批准或凭据。

## 用户与接口合同

普通人工 SUBMIT 原已有 actor/key/fingerprint 事务事件及原子回执，但只有 POST replay；详情历史 GET 不证明某个未知 key。新增 GET `/api/executor-receipts/{step_id}/submit-recovery`：原 key 放 `Idempotency-Key`，查询仅含原 preparation/Case/Run、原 step revision 和 preparation revision。严格拒绝重复、额外和非精确整数参数，响应 `Cache-Control: no-store`。

读取复用当前身份、READ、本人 executor、精确 Run assignment、tenant/park/org、actor/key 建议锁、parent/step 原锁序；等待后再次核验访问。根据原 actor/key 的 SUBMIT 事件、step、原 revision+1、receipt ID/version/实际正文 SHA、payload SHA 验证原子证据。按已存归一化正文/来源、原 revision 和事件保存的历史 frontier，重建原 `Command` 并使用原 `frontier_request/canonical/digest` 核对 fingerprint。没有另造指纹算法；后续 frontier 变化不把当前 head 填回历史。回执 version 必须等于该事件之前全部 SUBMIT 的序号，防止相同正文的其他版本替代原回执。

人工和本地适配器的事件都叫 SUBMIT；恢复同时拒绝事件的 `record_mode/adapter_execution` 字段和 receipt 的非空 `adapter_execution`。不是服务器本地生成报告恢复入口，也不是隔离 P4 preview/history 的替代。返回仅原事件与回执元数据，无正文、来源标签、token、可写视图、批准或权限。

COMMITTED 仅证明原人工提交已记录；后续纠错、ACK、新回执或材料变版不改写该历史，也不代表当前仍可提交。NOT_OBSERVED 只表示查询时尚未观察到记录；原请求可能晚到，继续阻止新写入。当前权限撤销统一拒绝，不能凭历史恢复访问。本接口代码不做业务 DML，但使用原授权及事务锁，不声称数据库级 READ ONLY transaction。

页面第一次 POST 前保存固定11字段不透明句柄：v/action、actor hash、原 preparation/Case/Run/step/key、原两版本及期限。不存正文、来源标签、token 或 frontier；每项最多640字符、每 actor最多8项、有效期最多24小时且不续期。坏/超限/过期/存储不可用均保留原字节并停止新写入，不删除未知句柄后重做。全局句柄前缀检查跨导航、身份切换和冷启动阻止另一写入；原列表/详情及核对 GET 仍可进入，其他身份不凭句柄获得授权。

成功回包也走相同原事件 GET 和当前详情 GET 再核验；未知回包由用户明确“只读核对原人工提交”，COMMITTED 后再明确“核对后读取当前回执”。不重发 POST，不自动 ACK/P4 VERIFY/办理。每层异步返回核身份/导航代次、同一内存句柄、原 raw 和期限；完整验证原事件仍在当前历史中，并成功渲染后才比较相同 raw 删除。`localStorage` 没有跨进程原子比较删除 API，不能声称任意跨标签页同步写入之间具有数据库级 CAS 原子性；本片覆盖异步等待期间的替换及迟到结果防护。正文草稿不持久化，等待期间新编辑不清空。

同一次原 POST 若完整解析出原 `receiptCommandExplicitlyRejected` 已登记的事务前正文422或 replay后、DML前确定拒绝409，才在同上下文/原字节下移除本次句柄，保留草稿并隐藏旧私有视图，要求刷新。任意其他409/422、网络错误、坏JSON不构成未提交证明，继续 UNKNOWN。

ACK/REQUEST_CHANGES/REOPEN、本地 execute-local、真实来源读取和正式批准消费均不由本片获得新恢复或授权合同。

## 正式来源已有代码与真实缺口

现有 `resource_plan_approval_read.py` 已有精确 Scope/ApprovalRecord、原 ID 固定二读、独立验真、当前主体/授权/来源/DB时钟重查；`resource_approval_host_read.py` 已有受保护 host binding、peer/pin/RPC相关性和共享2秒预算。继续增加通用 DTO、loader 或 verified 布尔值不会构成来源接入。

`formal_preparation_entry.py` 的五证明接口已经存在，但无来源专用结构/信任合同的成功分支，也不会调用未知回调。当前普通表仍限制 SYNTHETIC；仅做外部只读适配不必先迁移这些业务表，持久化真实业务另需其存储合同。来源专用读取、字段归一化、独立来源验真、主体映射及采纳映射仍是项目要实现的代码，不能描述成“只缺密码”。现阶段未知来源定义下，未发现可安全编码并产生正式正向结果的确定缺失映射，因此本片交付独立的原回执用户路径。

首个正式只读来源接入，最小输入如下；可用既有公开规范及已获授权脱敏样例，不要求访问凭据。

| 来源方需明确的现有合同 | 缺失时阻塞 |
| --- | --- |
| 选择一个实际来源域/source_id、合同版本及已有只读 API/文件形状、用途限制 | 专用 backend 读取/解析，不能猜模块、URL或表名 |
| preparation/Case/Run/已采纳 plan 稳定 ID、对象类型及关联；归属主体/租户；各 revision/service version/指纹覆盖与规范化 | 四对象映射与精确当前版本来源绑定 |
| 原 ADOPT 决定 ID、原主体、目标 plan ID/revision/hash、时间、状态、撤销；Run 成功及独立回执的业务语义 | EXISTING_ADOPTED_PLAN/EXISTING_RUN，不能以技术建单成功代替采纳或完成 |
| 源主体到既有本地主体的合法映射；原授权 ID/revision、Case/Run、用途/字段/角色范围、生效/期限/撤销 | CURRENT_SOURCE_SUBJECT_AUTHORITY；本地 PREPARE/READ 或角色字符串不能代替来源许可 |
| 既有 issuer/公开信任引用、签名覆盖、独立验真办法、current-head/撤销查询和时间语义 | 来源真实性、当前性与抗旧版本重放；旧签名或裸 true 不足以通过 |

可直接转给来源方：**请指定一个已合法存在、允许本次只读用途的来源，并提供现有合同版本/读取结构及一份已获授权脱敏样例：资料准备、Case、Run、已采纳方案的稳定 ID/关联/归属/版本/服务版本及指纹规范；原采纳决定的 ID、主体、方案版本与 hash、时间、状态和撤销语义；Run 成功与独立回执的含义；来源主体到既有本地主体的合法映射及原授权的 ID/版本、Case/Run、用途/字段/角色范围、有效期和撤销；既有公开 issuer/信任引用、签名覆盖、独立验真及当前 head/撤销协议。无需提供 token、密码、私钥、DSN，也无需创建任何身份、Grant、分派、目录或批准。**

正式资源批准可在上述首个只读来源之后独立接续；另需来源方既有批准记录对精确 plan/revision、动作/对象/来源摘要、批准主体及其授权、有效期/撤销的定义，才能实现实际映射。后续执行消费还需真实批准的单次消费/幂等/撤销及原交付事务协调语义；当前只读结果所有执行/消费许可仍为 false。`IsolatedPlanApproval` 必须保持隔离测试使用，不能导入普通批准。

## 验证范围和运行输入

最终测试/冻结/远端差异与失败原件另见 [验证记录](ReceiptSubmitRecoveryValidation-20261018.md)。本文件仅定义产品与来源输入合同。

普通人工回执运行仍需原受限 DB/迁移 schema、已有有效会话及当前 READ/本人精确 Run assignment、原 owner/reviewer 合法资料与已有 preparation_catalog、当前已接单回执步骤及可提交前置；缺项沿原接口拒绝，普通启动不补权。冷恢复另需未损坏未过期原句柄及当前原对象读取权。测试只在自有显式 SYNTHETIC fixture 初始化这些条件，不把合成批准、身份或目录带到普通真实运行。

Windows/Win11 原生、正式AT/AT35、生产不同 UID 受保护安装、真实主体/来源资料/业务/模型/现实履约未验；项目整体尚未完成。未知锁保留。不改 main、不强推、不部署，不新增费用或安全网络权限。
