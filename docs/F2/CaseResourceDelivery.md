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


第一候选ea29a249独立296 PASS、额外2 PASS/1 FAIL，结论BLOCKED：最终Case行锁升级等待可能跨原预检/hold期限。修正为仅首次新交付在独立实际行核对后再采DB时点，`now >= valid_until`则整事务回滚；历史回放与GET不重验TTL，原CONFIRMED占用保留。已纳入同Case共享行锁后段等待、多目标保留、不同Case争同成员和期限后原键恢复回归。旧候选与失败日志保全，不合开发分支。

当前修正版：最后时点守卫和必要兼容205 PASS / 0 FAIL / 0 ERROR / 0 SKIP（106.745秒）；随后仅增加空白理由的请求层拒绝及负例，最终真实API/PG/HTTP页面55 PASS（71.882秒），308源码hash无漂移。旧566/86与独审296窗口作为第一候选的历史证据保留，不能代替修正版独立复审。正式42AT/EX、Win11和全仓仍未通过。

修正版独立复审：`79500d0c75fd1f8a883188cefdc19d1fa87b41cc`，LIMITED_PASS。150 PASS / 0 FAIL / 0 ERROR / 0 SKIP（108.311秒），另精确诊断映射1 PASS（0.305秒），308源码无漂移；原Case共享行锁后段等锁过期探针Conflict且全部回滚。公开脱敏结论为`evidence/case-resource-delivery/independent-review.json`，SHA256 `52194390521a8c4e095a61cacf3cf4eeae2cbe56bd4fdd21ac0c44a006ed9f70`；原BLOCKED结论/原日志完整保全。随后仅证据文档更新，运行源码与被审SHA一致。
