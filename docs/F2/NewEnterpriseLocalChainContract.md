# F2-T06/T07 新输入到本地产物的最小接续合同

基线dev `1ba81f94aae43471aa6079121980dc54cc9bf41a`，原源码076有限验收保留。本片先对照原V1 §5.1–5.5、§7.1–7.5、§8、F2-T06/T07及冻结PR0覆盖表，再接原模板/资料/访问/Approval/资源/本人接单/本地执行与目标核查接口。只修真实阻断，不新外围检查页；不把选择记录、历史ACK、技术SUCCEEDED或本地报告算完整诉求完成。

已核UI阻断：模板后端已有全部六个LOCAL_*目标与精确注册闭包，当前作者页面只能编辑名称和来源，固定例子只有P1，不能明确选择多步骤目标。最小产品变化是在原模板作者入口选择已有注册目标，按服务端现有目标→步骤映射与注册依赖构建草稿；原后端仍独立验证精确闭包、参数、来源、CAS与独立审核/发布。无任意步骤/代码/SQL或新服务注册，不改变角色、审批与发布门。身份/模板切换清选择；已有未知请求冻结原选择/正文；回读按实际保存草稿显示。

真实测试先用原现成固定合成fixture的已有企业经办/获派专员/执行者/资源范围，在全新自有UUID数据库、零Case/Run/材料/交付的冷会话起步。所有新Run/Case/资料从原HTTP接口产生；模板作者→独立审核→候选发布经原入口，企业明确新诉求和双槽新材料、专员REVIEW、企业CONFIRM、原P1 VERIFY。原隔离Run READ申请由企业明确REQUEST、原专员明确APPROVE，仅执行者本人原READ与该Run租约；不得直接插assignment、调用assign_status或模板自动代办。未批准前分派和执行拒绝。专员采用原资料获派权限，不扩大为Run全量读。

原Approval在原已签发自有fixture进程内，对实际新资料事项ID由测试host显式调用原setup（最多16原ID）；不是HTTP动态注册、不是跨进程凭证再签或复制。原本地执行适配器仅在同已签发Run访问bridge的显式setup启用。企业PROPOSE/APPROVE后首次同Case资源交付原短事务实际消费；专员明确OFFER、执行者本人ACCEPT，原P2/P3 VERIFY后执行者生成真实LOCAL_SYNTHETIC_HANDOFF_REPORT与持久回执、企业明确ACK、原P4 VERIFY。必要时原本地记录REVALIDATE/P5 VERIFY；最后原goal-results只读独立核对当前实际产物/各原验证事件，保持原Case NEEDS_INPUT/WAITING_CONFIRMATION、external NOT_SUBMITTED、offline NO_EVIDENCE，不写FULFILLED。

再用同审核模板与第二份明确新输入创建不同Run/Case/资料/计划/资源关联/接单/报告，不复用旧材料、审核、访问票、Approval或回执；保存第一件全行和历史，旧lease不能授权新Run。错误新输入原422/未创建，跨企业/未获派/撤权/换版/未知丢响应按原合同拒绝或只读核对；不复制旧私密正文。冷会话指新的浏览器上下文/重新认证，不声称无桥的新API进程可以写原未消费Approval。新API只保留既有已消费证明GET范围。

原固定fixture-a/b两个企业都有现成合成资源READ/HOLD、各自获派专员和各自执行者READ，可在各自全新Run上通过明确REQUEST/APPROVE验证两个独立冷会话，再以企业a第三份新输入验证重复使用。原ENG098另两个新企业的现成seed只有Case/资料权限，没有资源HOLD或执行者；不得为了串链新增Grant或身份。对这些真实现有新企业可验证模板→新Case→新材料→独立REVIEW/CONFIRM与原材料目标核查，并实际记录后续资源/执行者缺口；不能将固定fixture-a/b的完整本地合成链转签为两个ENG098企业的资源链。若发现其它边界外能力，交付已验证部分与精确接口/状态/缺权限，不暗中手改DB完成。

写入、存储、CAS/幂等/恢复继续沿各原接口合同，产品不增加任何权限/迁移或新的账本。仅合成测试setup使用原确证自有UUID PG和既有seed；默认生产入口不挂模板，不启用Run/Approval/执行fixture。测试/API/PG子进程minimal_environment。源码冻结后按精确SHA交独立审查，失败原始日志/XML私有保全；通过后只正常候选push、开发分支整合/push，main不动，不强推、部署或改凭据/安全网络。正式ServiceRelease/ParkInstance、真实主体/政策/预约履约/模型/通知/Case完成、完整AT35/PR0、F1/Windows仍未签收，旧a823a28不迁移。

首次真实串链观察：原资源交付要求3–8个占位，不能以两资源组合的2槽测试正文称交付拒绝缺陷；原REVALIDATE真实将Case置WAITING_CONFIRMATION而非FULFILLED。两窗各2FAIL/4PASS分别为上述测试预期错误，原日志/XML保全；只修测试/此合同说明，不改原交付容量下限或Case状态语义。
