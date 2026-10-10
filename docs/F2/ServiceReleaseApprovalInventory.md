# ServiceRelease / Approval关键路径只读盘点

核对最终1a8d95e8cf532affc8e5b8c8503866c63b29d4c7源码（发布/审批盘点相关源字节与首轮0c2e5fa一致），与产品§7.4–7.5、§8对应。只读盘点没有产生发布、审批、安装、迁移或权限变更。

| 原要求 | 已有源码证据 | 真实剩余 |
| --- | --- | --- |
| 发布主体、审核与来源维护 | template_candidate.py 默认关闭；TemplateConfig显式合成principal/permit，AUTHOR/REVIEWER/PUBLISHER分离，发布不得作者/审核同人；当前contract/来源head/期限动态检查 | 非正式生产主体或Grant；真实来源维护和精确实例/用途授权未建立 |
| 精确服务/动作修订 | candidate发布保存definition、registry、source、contract精确hash与不可变版本；consumer的release_id+expected_release_sha256、snapshot一致检查 | 正式ServiceRelease/ParkInstance发布与实例适用协议未实现；V1ServiceSpec只结构校验，不验证reviewer身份或正式发布 |
| 参数化消费 | template_consumer.py默认关闭，精确fixture_UUID数据库与park/org白名单，每阶段重验发布及当前产品权限，用原键/正文；未创建Grant或assignment | 只有隔离合成桥，不是正式实例挂载或完整服务履约；新Run仍独立访问合同 |
| Approval版本/用途/期限 | domain.V1ServicePlan.approval_requirements仅CURRENT_AUTHORITY结构要求；资源有当前来源/容量/期限与既有门 | 没有独立持久方案Approval对象，不能拿Run READ租约或人工步骤锁充当批准；仍需方案指纹、精确服务/资源修订、执行身份、用途、有效期、授权版本、前置提交时重验 |
| 在途变更与历史 | candidate来源升级/withdraw动态不可消费；consumer每阶段核对原发布snapshot；service_case_steps绑定变化阻塞、明确ADOPT保留旧计划8代 | 没有正式逐Case兼容/迁移/回退协议；破坏性升级不能自动迁移，代码回退不撤销真实预约或线下动作；未闭合来源发布者到COMMIT协作窗口 |

常规功能实现与合成测试已授权，可继续实现原设计有界产品能力。本次人工锁仅保护原注册步骤核验内容与冲突处理，不建立Approval、不自动发布、执行或完成Case。对真实主体正式发布、真实履约、真实Case FULFILLED和对外分享是独立业务动作，没有本轮授权；这些业务限制不会停止其他已授权开发。Windows、全仓、完整原AT/EX均另行实际验收，旧a823a28不迁移。
