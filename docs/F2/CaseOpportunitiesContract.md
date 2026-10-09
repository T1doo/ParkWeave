# 实施前冻结：合成Case机会导入与手动刷新

基线`9c1b9f91f539ff757e58235535f253e1a9e38434`，本地/远端一致，88403af祖先有效；唯一源码写入者，无挂起Git操作，平台索引刷新锁保留。资料导出、资源、资料异议、原结果检查和生命周期恢复均不重做。

原V1 F3-T02 / AT-24及产品§5.3明确要求显式导入/手动刷新机会、授权作用域、去重、忽略及撤回。当前无机会API/表列/UI。相比之下现有Case事实用途已显示三字段来源/单位/摘录/有效期、明确目的选择及历史；更一般的FactBundle三类来源/多目的与跨字段合同仍缺，但此时只加显示/导出会重复已有能力。本片选新机会业务路径，完整原AT-24仍不由此子集签收。

范围：仅原企业owner、既有SYNTHETIC资料Case与同一service_id的已存在SYNTHETIC目录版本。用户手动导入合成服务版本或本Case资料变化提示，系统以当前真实Case/Run/owner/park/org/service、资料revision、两槽ID/version/hash和所选目录version/source SHA绑定；不做政策资格匹配、利益预测、发布或新企业广播。标题/说明是导入者的未核验声明，不是权威条件。仅本Case持久待审机会，不创建新Case/占位/方案/资料/动作，不通知外部。

导入源族UUID+generation(1..64)及kind、标题/说明、既有目录版本构成有界导入身份。同族同代同内容去重（保留原card与忽略/撤回），不同内容409；较旧代次不覆盖较新代次，必须明确新代次才能再提示。最多8族、16卡、128请求事件。同版本被忽略/撤回后重复导入或刷新不再变待审；新代次保留旧卡及历史。无worker/定时在线/模型。

读/恢复重验active原owner、READ及PREPARE，POST再交集EXECUTE；不增加角色、Grant、assignment或公开来源权限。GET无业务写入。预览给当前聚合source SHA及实际有权目录；IMPORT/REFRESH以来源SHA+独立机会ledger CAS写入，IGNORE/WITHDRAW绑定精确card ID/version与ledger CAS。源变化不把旧卡当当前有效，原导入绑定历史保留；手动刷新仅更新未决最新代卡的当前资料绑定，仍待人工审阅，既有忽略/撤回不自动复活。新事件使用同actor/key锁，actor-wide同键异正文/异Case409；原回放不重复效果，历史回执与当前视图分开。

存储：只增preparations.opportunities JSON列；既有表UPDATE已授权，无roles.sql/能力/字段/访问Grant变更。独立ledger含固定Case范围及最多128个按revision串联hash的追加事件，读取完整验证并重建投影；API无编辑/删除历史入口。它沿用现有JSON业务账本的可信应用/管理员边界，不声称数据库列对获准UPDATE账号不可改写或hash链具有签名抗伪造。机会写入仅更新此列，不增加原preparation revision、人工review、Case状态或既有计划失效。新增fixture限定migration027沿既有实际新建DB receipt协议；native不启用此功能，不改变安装、安全或凭据配置。

GET原actor/key只读恢复；未知/超时/NOT_OBSERVED不能证明未提交，禁止自动POST。页面POST前持久保存最多8条opaque actor/id/key，不存理由、卡正文、来源hash或token；存储失败不发送，损坏/超界/未知锁本Case机会新动作。冷刷新重新认证后只GET，回执须与实际ledger历史精确匹配后才移除句柄。身份/Case/草稿变化的迟到成功/403不得回填或清空新私有视图。明确拒绝仅释放对应新句柄，其他保留。

完成判据：真实PG/API导入→刷新→忽略/撤回→新代次与重启回读；同键及不同键去重、并发CAS、乱序、同代异内容、源/目录变化、范围/角色/撤权、坏证明/边界、原资料/Case/资源/计划不变；真实HTTP/Chromium三宽度、冷刷新/丢响应恢复只GET、opaque隐私、未知禁写和迟到响应负例；必要原兼容、源冻结、普通候选推送、独立只读审查、通过后普通dev FF推送。故障原日志保全。

正式Release/Approval主体、一般企业/政策匹配、真实来源许可、三类通用FactBundle、一般依赖图、真实模型与Win11仍未完成；不虚构前提、不把工程PASS外推42AT/EX/全仓/真实业务验收。不改main/强推/部署/凭据/安全网络。
