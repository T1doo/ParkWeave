# ENG089：合法单 Run 协作访问的隔离候选

基线 `5cbff16bcdb5a8b447f64b57040db6452f1f048d`。本轮按用户原产品授权继续开发申请→独立审批→精确Run/角色/期限→撤销与审计，仅独立Mock/测试，默认关闭。未写真实assignment或Grant，未创建身份、凭据或修改权限/owner，未挂生产API；部署schema20、目录只读与ENG088候选发布原实现保留。明确可审核的启用决定见[一次性决定包](ENG089-ActivationDecisionPacket.md)。

## 合同与实现

复用Contract/PlanID/SourceRef/Validity、现有四角色READ上限及ENG088 canonical/hash工具。RunAccessConfig只有显式合成persona、现有READ的Mock事实、精确单Run permit、MockRun；SYNTHETIC命名空间隔离。每个Run最多一份当前请求/批准，没有通用ACL/任意动作/通配scope，没有实际Grant类型、身份创建或owner入口。独立mock-run-access-approver需显式APPROVE/REVOKE；prep-specialist-fixture-a没有这些能力，其资料审核权限不能升级为Run审批。

Run所有者发起请求，受益人必须同park/org且当前active的service_executor并有当前READ事实；固定capability READ。申请与批准主体不同，受益人也不能批准自己。批准期限只能在请求范围内，最长8h，不能超出当前申请人/受益人/审批者的父授权期限。未来起点在到期前仍不可读取；来源Run版本、owner、角色、READ、审批/请求能力或配置revision变化使旧批准不可用，配置revision必须递增，不会因撤权后重新配置而复活旧批准。

REQUESTED→APPROVED/REJECTED/CANCELLED；批准可REVOKED。修改对象/人员/期限需新申请、新独立审批，不覆盖旧审计/批准快照。保留64条操作预算并预留取消/撤销容量，批准快照payload不可UPDATE，audit events不可UPDATE/DELETE。专用*.run-access.candidate.sqlite3，未知/部分旧库拒绝且原字节不变；旧业务数据库不迁移为候选库。BEGIN IMMEDIATE写事务、BEGIN一致读；取得写锁及读取后重新取时钟/验证当前权限，返回快照前再查期限，防锁等待跨到期。失败完整回滚，两engine同key并发只有一个事件/一个批准，CAS冲突只允许一方提交。

命令绑定expected_revision、expected_run_revision、authority_sha256，key绑定actor+单Run+全body指纹；当前授权先于重放。只能重放仍是当前版本/当前合同/Run/有效期限的回执，撤销、过期、换配置或后续操作后的旧REQUEST/APPROVE不能恢复或重放成当前批准。probe必须绑定当前revision、Run revision、authority hash和lease_id，每次重新查当前范围/权限/角色/期限；旧上下文不是凭据。

STATUS只给当前Run owner、具名受益人、该Run显式审批/撤销主体查看该申请元数据与审计；不含真实Run业务正文。普通资源读者和仅资料审核专员拒绝。probe仅受益人可在当前批准下获得合成MockRun文本；actual_run_access、actual_assignment_written、deployment_enabled始终false，qualification UNKNOWN，Case目标不因此完成。候选approve不影响产品dispatch/receipt，因为没有写真实assignment。

## 界面与实际浏览器

页面持续“候选流程未启用/仅隔离Mock”，单Run/组织、目标role/READ、UTC期限、审批人和审计清楚可见。换主体或Run立即清空私有记录、表单、缓存和合成快照；迟到成功/错误不回显。刷新只读、probe在服务器验证后再次GET当前状态再显示，expiry定时清空快照/缓存并禁用；用户不能用缓存上下文跳过当前权限。默认双开关不齐则不建存储、所有命令拒绝。独立factory `scripts.run_access_candidate_demo:configured_mock_app` 只在本地测试harness绑定127.0.0.1:8767；X-Mock-Actor不是生产认证。

实际Chromium tag `722bda813db9` 全路径通过：跨企业申请零写入、原资料专员无权限/元数据拒绝、独立审批及只READ、跨Run probe拒绝、撤销旧缓存probe和旧APPROVE key拒绝、拒绝/取消历史、新申请丢已提交响应同key仅一事件、跨企业切换迟到响应清空、实时短期限到期缓存清空/probe拒绝/刷新与reload恢复。revision13/history13/leases2，1200/390/320无横溢出，7截图；模型调用0/预算0、未连接部署PG或迁移，子进程已回收。

## 从原诉求到回执的当前可演示范围

| 环节 | 当前可演示能力 | 尚不能当作完成/真实结果 |
| --- | --- | --- |
| 原诉求 | ENG085保留原诉求、当前显式诉求、用户必需目标及覆盖快照，刷新恢复；修改使旧预览失效 | 仅当前受控合成输入，不是完整冷输入/自动模型编排；缺信息UNKNOWN、不支持目标PARTIAL。 |
| 服务方案 | ENG084有限四步方案预览，前置/责任/材料/资源/核验可見；必要目标未知或未覆盖阻止明确启用 | 尚不是完整F2 DAG、真实目录或所有目标；企业需显式选择，不自动办理。 |
| 准备度 | ENG086绑定材料/规则/来源版本，缺证据UNKNOWN、明确补正FALSE、当前获派专员人工核对仅本地条件TRUE；变化后STALE/重核 | 不证明来源真实性或资格。ENG088有独立规则候选审核发布，但实际规则目录未发布，资格UNKNOWN。 |
| 协作访问接缝 | 本轮独立Mock可申请、审批、限定Run READ期限、撤销、拒缓存并保留历史；真实产品只对既有合法assignment读取 | MockRun不等于现有Case真实Run，未向产品写assignment，P3新Run协作访问仍BLOCKED；既有演示的assignment来自已授权夹具预置，不算用户产品申请流程已启用。 |
| 分派与本人办理 | 在已有合法assignment和当前专员获派材料前提下，已有SYNTHETIC dispatch→executor本人接受→本地receipt可演示，各自重验分派与父版本 | 本轮没有自动赋权/派单/代接受/代回执；Run访问批准不替代这些单独授权，完整冷入口尚不闭合。 |
| 回执与目标 | 已有本地工程回执和资源/步骤历史可核对与刷新；历史事实保留，撤销访问不删除它们 | 不是外部提交、真实履约或企业确认，external NOT_SUBMITTED/offline NO_EVIDENCE；Case NEEDS_INPUT、goal_completed=false、资格UNKNOWN。 |

推荐演示顺序：已有授权的产品Case展示诉求→方案→准备度→当前缺口；打开独立ENG088规则候选和ENG089访问候选，明确它们的Mock范围；回到既有预置合法assignment的合成协作实例展示分派/本地回执。不能把三套夹具拼成一个已完成真实用户冷入口，也不能把Mock批准当作实际开通。后续生产闭合需要一次性决定包列明的权限初始化/赋权和全路径期限校验，随后才接入同Case/Run的真实产品流程。

## 验证与边界

相关59 PASS/0 FAIL/2既有WARN（1.99秒）：30个新Run候选用例及29个ENG088候选/真实隔离目录只读边界。覆盖默认关闭、跨tenant/role、精准受益人、独立审批、未来/到期、角色/READ/审批/requester/Run/config撤权、旧版本/跨Run/旧回执、双engine真实SQLite幂等/CAS、不可变历史与原子回滚、外库字节保留、等待锁跨deadline、普通STATUS不能读私有审计。JS语法通过；217源冻结最终完整Linux **1556 PASS/0 FAIL/9原生Windows SKIP/2既有WARN**（312.6秒），源hash0差异。独立代码/实际截图审查无阻断，最终独立核验已完成，无阻断；217源、完整/相关日志及最终9件浏览器图/JSON哈希相符；计数/hash见[evidence](evidence/eng089-single-run-access-candidate.json)。

不push/CI/merge/deploy，不修改owner、日志限制或任何实际授权数据；F1未签收/F2并行，Windows Server不是Win11，原生Windows/F1完整验收不因Linux/Mock通过而成立；R4关闭，模型调用与预算0。
