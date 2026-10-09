# 同Case首次资源交付

对应原产品§5.4和F2-T03/T05/T07的有限本地切片：企业选择本人3–8条现有合成占位，在当前Case资料事项中预检当前服务版本、资料和已采用的注册计划，再明确确认全部容量及首次Case关联。此前两次独立写入存在确认成功而关联失败的缺口；现在两者以及不可变CONFIRM、Case claim/link同事务提交，任何关联写故障全部回滚。

运行沿用项目README的原API/PostgreSQL启动方式，网页资源区新增“交付到此Case”。先完成已有资料审核/企业确认、注册计划采用及P1独立核验，填写同Case资料事项编号，在本人占位记录选3–8条，点击只读预检，再明确交付。结果核对实际成员及Case关联，不自动核验P2；返回原计划独立VERIFY。该结果仅是本地合成容量与Case记录，正式ServiceRelease和方案Approval尚无可启用主体合同。

新增路由均在原认证、16KiB及no-store边界内：

- `POST /api/preparations/{id}/resource-delivery/preview`：只读有限成员预检，无业务写入。
- `POST /api/preparations/{id}/resource-delivery`：严格原预检指纹/资料及计划版本/期限、明确理由和Idempotency-Key。
- `GET /api/preparations/{id}/resource-delivery/recovery/{key}`：原actor/key只读恢复，读权限独立于已撤EXECUTE/HOLD。

所有原入口保留。只有新可信事务组合入口允许严格关联比较核对已经采用的注册计划目标；旧固定模板目标规则不变。新版入口先检查当前注册计划覆盖全部原required_goals、稳定定义和P1来源，再核对原目录/资料/原专员当前权限、逐资源READ/HOLD、容量、期限及Case归属。没有新增schema、表、Grant或身份；未调用模型、通知、真实预约、机构受理或Case完成。

不可变两边delivery_binding绑定Case/Run、原资料revision/hash、服务ID/version/目录sha、计划ID/定义sha/当时revision、P1源sha、预检sha/期限及原请求key/指纹。初始CONFIRM的manifest逐成员绑定UUID、资源修订、时段/数量/缓冲/来源。恢复重新读取实际初始CONFIRM、成员、claim/link与当前来源；取消、换版或后续绑定保留历史COMMITTED，当前NEEDS_RECHECK，不自动重新执行。NOT_OBSERVED无法证明未提交；未知或损坏页面句柄锁住相关写入。页面最多保留8条opaque actor/key/资料事项编号，不存token、正文、方案或成员列表。

应用锁协议与现有数据库管理员信任边界不变：未制造目录发布权或数据库管理员COMMIT窗口的绝对原子承诺。正式42AT/EX、全仓库、Win11原生、正式权限主体、实际业务履约和真实模型验收仍未通过/未完成。已有旧Windows问题与未迁移成果不由本轮宣称解决。

冻结合同见[CaseResourceDeliveryContract.md](CaseResourceDeliveryContract.md)；测试、源码冻结、失败历史及独立审查证据将记录在`docs/F2/evidence/case-resource-delivery/`。

实际验证：后端与必要兼容冻结回归566 PASS / 0 FAIL / 0 ERROR / 0 SKIP（304.919秒）。其后仅页面状态/句柄类型与相应页面负例变更，最终页面及诊断86 PASS（78.169秒）；后端源码一致，最终308源码文件无漂移。独立审查尚待候选推送后执行，不代表正式42AT/EX或Windows验收。
