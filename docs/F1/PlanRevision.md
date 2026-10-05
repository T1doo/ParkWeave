# ENG-009 结构化本地计划修订

这是R1有限交付：一goal/可信case.create的local plan projection，schema `parkweave/local-plan-revision/1`，不是F2复合ServicePlan。正常worker只有显式`--model-fixture good`接此链；响应自建SYNTHETIC MockTransport，真实请求/预算0，不能完成真实AT02。

PLAN wire/可信工具参数校验后，先持久revision1：原goal/op/tool ID、step=PENDING_ACTION、Case NOT_CREATED、下一步EXECUTE_TRUSTED_LOCAL_ACTION。commit必须先于gateway本地效果；已有Case却没有此前artifact会失败PRE_EFFECT_PLAN_MISSING，不能在旧ENG007记录上伪造“动作前”历史。历史已完成Run不补造新artifact。

gateway创建Case/VERIFIED实际本地回执后，反馈由数据库Case状态/op/receipt及前版SHA组成，要求模型返回结构化revision2。必须保留goal、正确previous SHA/op/tool/Case ID/receipt SHA，step=LOCAL_RECORD_CREATED、Case NEEDS_INPUT、next=REQUEST_MISSING_INPUT、外部NOT_SUBMITTED/线下NO_EVIDENCE。Call IDs绑定model_steps和artifact元数据；模型修订与工具回填ID对应可查，前后SHA采用排序/UTF8/紧凑JSON的SHA256。未知字段/额外动作/浮点revision/duplicate JSON/截断/改目标/虚报受理履约/错误回执均拒绝，不执行第二tool。

schema7 `model_plans`按Run/revision唯一，应用只有SELECT/INSERT，无UPDATE/DELETE；保存冲突拒绝，历史不覆盖。accepted revision2与Run SUCCEEDED/LOCAL_CASE_CREATED及terminal outbox在同一事务；中断rollback只留下已知Case与前版本。缓存合法FEEDBACK回复已持久时恢复不增加模型请求，既有Case不重建。当前fence/lease/control/权限在保存时重验。

新GET `/api/runs/{run_id}/plan-revisions`仅通过当前Store身份/scope/READ/enterprise-owner授权；跨企业/园区、撤权或仅获派状态的角色不能获得goal/plan正文。界面不执行模型JSON/HTML/code；这是可核查API artifact，未增加F2业务动作。直接可信本地Run没有模型artifact返回空列表，不伪造智能体成功。

FEEDBACK wire-valid不等于语义修订成功：共享费用账本VALIDATED表示HTTP/模型/usage边界通过，随后修订错误记录model_steps FAILED/INVALID_PLAN_REVISION、Run FAILED，但Case/VERIFIED/LOCAL_CASE_CREATED继续可见。保留历史效果，不能改FAILED_SAFE；费用照计，不把拒绝响应当免费。

`test_plan_revision.py`的独立oracle不调用生产initial/validator/hash函数，直接比对API revision1/2全部字段与真实PG op/Case、独立hash、两个不同provider IDs和相同tool回填ID。另测正常CLI、13种坏修订、动作前持久、immutable权限、终态/outbox原子恢复、当前权限/状态角色隔离、旧效果无artifact不伪造。真实模型/Windows没有执行。

本轮并非修复速率：原产品§10默认30RPM的R2差距在另一个仅配额合成fixture复现31即时发送标记；该“成功复现失败”的pytest项不是AT30 PASS。完整有限残余/原阶段映射见Convergence；不新增金额高阶功能/协调平台。
