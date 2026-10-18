# 本 Case 受限步骤分派、本人接单与人工回执

基线 `a31cb8b551a8f335387e83174e94c789dbb2c165`；合同提交 `2e671e5b0ad9d8bd4ba6b7aa988a1c19bcfa84b3`；实现与测试冻结 `f6b76c5e030ffd7a055c7b4a3278bf911c05b4f1`；开发分支 `dev/f2-case-step-assignment-20261018`。根是唯一受控文件/Git写入者，独审只写其私有运行时证据。原图传播片保持冻结，本片接续原V1 §3/§5.5/§6.4 `case.assign`、F2-T04有限用户路径。

## 已实现的用户路径

显式隔离应用可从零业务临时PG初态，经原API/worker创建新诉求和Case、原资料准备双槽REVIEW/CONFIRM，再由当前负责专员使用原分派表单OFFER、指定本人ACCEPT、原回执表单SUBMIT、企业owner核真实正文SHA并ACKNOWLEDGE。正向链不在运行中补Run assignment、不新建身份、Grant、目录或批准；七类权限表快照不变。原资料准备、当前身份、来源/修订预检、原事件与事务接口复用。

新的 [CaseStep合同](CaseStepAssignmentContract-20261018.md) 将这一个固定“合成人工办理回执”任务与整Run读取分开。执行者只见自己的步骤必要字段、本人分派及回执，不见原诉求、材料或事实；Run GET保持403。负责专员须是该Case既有reviewer并有READ/REVIEW_ASSIGNED，owner须有READ/PREPARE/EXECUTE，目标是显式配置中已有同park/org、当前READ的执行者。REVIEW_ASSIGNED不推导整Run授权。

每Case仅一次OFFER。全部新动作共用首次最多300秒截止，依赖本身最多3600秒；接单、同键重放、换键均不续期。当前principal/授权代际、资料revision/hash、目录版本/代际、Case/Run/服务绑定每次重核。撤权后恢复、变版或到期不复活原步骤；实际锁等待跨截止与写入后最后检查失败均整事务回滚。没有COMMIT触发器，不声称物理COMMIT瞬间的原子期限保证。

本人DECLINE后只返回当次精确终态回执，后续读取拒绝；页面核对原坐标后明确成功并清空视图，不再自动GET一个已终止权限的对象。负责专员仍凭当前本Case权限可WITHDRAW已接单责任，即使目标撤权、资料失效或offer到期；当前指针按原表约束清除，原ACCEPT→CREATE历史证明保留owner回执列表入口。原REQUEST_CHANGES/REOPEN与人工纠错语义保留。不存在重分派、execute-local、legacy CREATE、资源释放或自动核验的新许可。

未知结果沿原ACCEPT/SUBMIT只读恢复接口，核实际原key、精确选择、原事件/CREATE、正文SHA/版本/指纹；错误坐标即使原键不存在仍拒绝。NOT_OBSERVED不证明请求失败；COMMITTED不授予当前写入权，不自动重发/ACK/VERIFY。原_event保留本地outbox意图，本片不授予通知读取或对外送达权。

## 授权边界与原实现

仅 `create_app(store, case_step_assignments=原精确依赖)` 显式绑定；`configured_app`无环境启用、loader或生产安装路径。原证明必须为原发行fresh owned临时PG，零业务初态构造，精确数据库/集群启动实例绑定。普通新Store/API不能从数据库marker继承此依赖。

`Store`、`roles.sql`、permissions、全部Native模块、正式资料来源入口、普通runtime、资源批准/隔离批准、原图算法及固定AT规格/绑定保持基线字节。普通 `configured_app` 函数源码保持基线。27项保护检查全部相等；34,390份继承F2证据与基线Git blob逐件SHA256相同。原分派/回执guard均保留，另增加marker隔离拒绝及列表过滤，防止后续旧Run assignment把本合同记录重新解释为legacy权限。已有active/inactive assignment、Native历史、混合provider、未知/损坏marker/原件均拒绝，绝不捕获旧拒绝后fallback。生产持久权限/角色SQL、迁移、原fixture初始化均未改；无需新增持久权限来完成本隔离片。

本片仍调用原P1/P2前置检查，不声称其独立任务满足旧Run依赖的P3–P5证明链、全Case目标、完整PR0或正式AT35。`IsolatedPlanApproval`没有转作普通批准。

## 实际验证与失败保全

冻结主窗实际124/124通过（新CaseStep 33、原dispatch完整模块53、原receipt完整模块38），0失败/错误/跳过，4项既有依赖警告，pytest 277.94秒。collection、setup/call/teardown与JUnit逐nodeid一致；789个Git选入输入在共享树/执行镜像前后全部相等；104个项目/测试导入来源均在镜像且SHA匹配选入输入。证据：[计数核对](evidence/case-step-assignment-20261018/runtime/counting-verification.json)、[导入来源核对](evidence/case-step-assignment-20261018/runtime/module-source-validation.json)。完整原HTML在NodeVM中通过原控件发实际loopback HTTP/ASGI至自有PG，三分支明确人工动作产生实际业务记录，不是模拟fetch或浏览器结果。

独立第二窗8/8通过（独立5复合探针＋原HTML三支3重叠），pytest45.77秒；与根按实际nodeid精确并集为129唯一通过，不累计开发窗。独立103个导入来源为102个冻结输入＋1个独立probe，全部SHA匹配；789基础输入、独立probe和控制器/oracle各窗前后无漂移。首窗8setup ERROR/0call/8teardown PASS源于独立控制器basetemp在workspace，原owned证明准确拒绝；只改控制器为系统/tmp后有限重跑一次，原窗及两版控制器保留。有限SYNTHETIC范围无开放P1/P2。[独审报告](evidence/case-step-assignment-20261018/independent/independent-final-review.json) SHA256 `c1003aeef1fb1565de94a92adab3f1c64266fb04e64204205fd7433e3b4c3e68`；[精确去重](evidence/case-step-assignment-20261018/runtime/cross-window-verification.json)。

开发七窗原始stdout/stderr/JUnit及输出均保全：第1窗0通过/1失败（同角色GET与owner ACK响应误比的测试错误）；第2窗18通过/4失败（3项WITHDRAW原表指针约束产品缺陷、1项恢复URL测试错误）；第3窗5通过；第4窗1通过；第5窗4通过；第6窗5通过/1失败（DECLINE页面引用不存在的context.offerId）；第7窗30通过。其间源码未冻结、导入来源未插桩，中间源码前像未完整留存；不声称这些窗零漂移，也不把其次数转计最终冻结结果。静审另外发现DECLINE事务终态guard、撤权后catalog阻断WITHDRAW、owner历史列表丢失、OFFER原件字段未完整匹配及未知key恢复坐标问题，均修补并列入冻结验证。只读rg缺失文件的exit2及不存在本地main分支的git读取exit128也列入ledger；实际远端和origin/main已另核，不计产品测试失败。

[失败账本](evidence/case-step-assignment-20261018/runtime/failure-ledger.json) 保留各窗和修补分类。公开证据对临时会话值/pytest截断前缀脱敏，私有原件及SHA配对保留；不发布DSN、会话配置、PG数据或镜像目录。独审oracle原版与后续接受选择补充均保留。归档140组原始/公开SHA配对：134组字节相同，6组开发失败日志脱敏，共12次临时会话替换；80个实际独审fixture token及16字符前缀扫描无残留。独审56项canonical公开原件按其原SHA逐件原样复制。JSON/JSONL/XML均解析，配对目标唯一、SHA差异均有映射，另有3项派生归档元数据。[归档校验](evidence/case-step-assignment-20261018/archive-validation.json)、[配对清单](evidence/case-step-assignment-20261018/manifest.json)。

## 普通/真实运行仍需的既有输入

| 路径 | 尚缺的合法既有输入与实施边界 |
| --- | --- |
| 普通资料准备 | 实际受限DB与原迁移、已有有效会话/身份、当前READ/PREPARE或精确REVIEW_ASSIGNED、合法preparation_catalog及原Case/Run/资料。缺PREPARE/REVIEW_ASSIGNED/目录沿原接口准确拒绝，普通启动不补权。 |
| 本片生产CaseStep安装 | 当前只发行自有合成证明依赖，生产入口关闭。真实已有身份/域/Case的合法分派范围、服务必要字段/动作/版本/期限及存储/当前性合同仍需实际安装证据与经授权实现；任何持久技术权限扩展必须先报告待批准。本片没有安装或制造这些输入。 |
| 整Run Native路径 | 已选owner申请/激活、独立具名专员审批合同保持独立；仍需现有受限writer身份、受保护host/policy/私有通道、独立密钥来源及精确安装权限证明。此前root/seal/安装拒绝不重试，不用本步骤路径代替。 |
| 正式资料只读来源 | 指定实际source_id/合同版本/读取结构；preparation/Case/Run/已采纳plan四对象稳定ID、关联/归属/修订/服务版本/指纹；原ADOPT决定与Run/回执业务语义；源主体到既有本地主体及原许可范围/期限/撤销映射；已有issuer/公开信任、签名覆盖、独立验真及current-head/撤销协议。项目内专用解析/映射代码仍待这些确定输入后实现，不能称只缺凭据。 |
| 正式资源批准与执行 | 另需既有批准对精确plan/revision、动作/对象/来源摘要、批准主体及原授权、有效期/撤销定义；后续消费/幂等/撤销及交付事务语义。合成批准不可导入普通路径。 |
| C0正式提交 | 正式可读模板/hash、规则/截止、合法身份与相关作品/视频/提交回执等输入本地仍缺；本片不新增、发布或提交。 |

正式来源输入详细说明见 [原回执合同](ReceiptSubmitRecovery-20261018.md)。无需索取密码、token、私钥或新增身份/Grant来明确上述合同。

Windows/Win11原生、真实浏览器/视觉、生产不同UID安装、正式AT/AT35、真实主体/来源资料/业务/模型/现实履约均未验。未改main、未强推、未部署、未新增费用/安全网络权限；未知锁与进程保留。项目整体尚未完成。
