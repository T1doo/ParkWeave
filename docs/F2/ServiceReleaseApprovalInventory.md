# ServiceRelease / Approval关键路径只读盘点

原只读盘点核对1a8d95e8cf532affc8e5b8c8503866c63b29d4c7，与产品§7.4–7.5、§8对应。后续11b756db4e164fafb7756ec63bffb286178e0a73已独审LIMITED_PASS，实现下表所列原首次资源交付的有界合成Approval；仅隔离fixture setup两个列/固定前缀触发器，仍无正式发布、业务Grant或生产迁移。后续20c0a568312e53c1c926927eda6d11c607c8e44e已精确独审LIMITED_PASS：有界合成目录不可变修订/head与source-key→owner安装关系锁→schema重读串行setup；原Approval shared消费到COMMIT、owner exclusive发布协作窗口已闭合。实际不同API PID/自有PG重启后已消费证明只GET可恢复，新批准写保持关闭；其它盘点保留原范围。后续 `076625a357fe9631cccb923132dad3cd224db48e` 精确独审LIMITED_PASS，只补本人原合成实例的新旧修订检查与明确选择审计，未实现迁移执行或正式ServiceRelease/ParkInstance。

| 原要求 | 已有源码证据 | 真实剩余 |
| --- | --- | --- |
| 发布主体、审核与来源维护 | template_candidate.py 默认关闭；TemplateConfig显式合成principal/permit，AUTHOR/REVIEWER/PUBLISHER分离，发布不得作者/审核同人；当前contract/来源head/期限动态检查 | 非正式生产主体或Grant；真实来源维护和精确实例/用途授权未建立 |
| 精确服务/动作修订 | candidate发布保存definition、registry、source、contract精确hash与不可变版本；consumer的release_id+expected_release_sha256、snapshot一致检查 | 正式ServiceRelease/ParkInstance发布与实例适用协议未实现；V1ServiceSpec只结构校验，不验证reviewer身份或正式发布 |
| 参数化消费 | template_consumer.py默认关闭，精确fixture_UUID数据库与park/org白名单，每阶段重验发布及当前产品权限，用原键/正文；未创建Grant或assignment | 只有隔离合成桥，不是正式实例挂载或完整服务履约；新Run仍独立访问合同 |
| Approval版本/用途/期限 | service_plan_approval默认关闭；独立持久UUID与不可变事件/head，绑定原Case/Run/plan UUID修订/指纹、服务/来源/双槽/成员、原请求/owner HTTP执行身份/授权版本/期限；原首次资源交付同事务消费，P2/goal验证真实消费证明，来源/撤权恢复不复活旧批 | 仅原owner本来有权执行的CASE_RESOURCE_DELIVERY，非独立业务审批主体；正式Approval/任意资源动作/Release消费协议待补，已消费证明在实际newPID API/自有PG重启GET验收；未消费Approval新进程写/重启重新启用不签收；固定协作窗口关闭，可信owner非协作窗口仍排除 |
| 在途变更与历史 | candidate来源升级/withdraw动态不可消费；consumer每阶段核对原发布snapshot；service_case_steps绑定变化阻塞、明确ADOPT保留旧计划8代；076有界逐原实例分类为兼容/需重验/人工锁冲突/破坏性拒绝，最多64不可变明确选择，旧Case/预约/回执/历史不变 | 只有合成检查与选择记录；正式逐Case迁移/回退执行与业务责任未建立；破坏性升级不能自动迁移，代码回退不撤销真实预约或线下动作；20c仅闭合固定合成目录publisher与原Approval消费协作窗口；默认其它资源路由和可信owner绕全部锚不在保证内 |

常规功能实现与合成测试已授权，可继续实现原设计有界产品能力。本次人工锁仅保护原注册步骤核验内容与冲突处理，不建立Approval、不自动发布、执行或完成Case。对真实主体正式发布、真实履约、真实Case FULFILLED和对外分享是独立业务动作，没有本轮授权；这些业务限制不会停止其他已授权开发。Windows、全仓、完整原AT/EX均另行实际验收，旧a823a28不迁移。

后续批准范围和精确证据见[ServicePlanApproval](ServicePlanApproval.md)。人工锁继续是内容保护，Run READ租约继续是访问期限；三者没有互相冒称授权。

目录协作与真实已消费证明重启范围见[CatalogApprovalCoordination](CatalogApprovalCoordination.md)，根/独审18模块均按实际两窗分列，不改旧11b验收时点。

逐原实例检查与明确选择的范围、失败史及真实API/PG/页面证据见[TemplateUpgradeCheck](TemplateUpgradeCheck.md)，不替代正式发布或迁移审批。

本轮6d79精确独审仅串通原fixture-a/b已有授权的冷LOCAL链与第三输入，root20/独审20各650PASS、另16反例，337源不变；没有建立正式ServiceRelease/ParkInstance或新的Approval主体。literal ENG098两新企业仅材料P1，原资源/执行者权限缺口实际为空/403，未补Grant；未消费ApprovalnewPID写仍关闭。根旧观察器证据改写已保全并恢复，既有正式缺口全保留。见[NewEnterpriseLocalChain](NewEnterpriseLocalChain.md)。
