# 原事项入口的独立部分办理

接续已接收交付 `f9731fc2be4a6f0d00491d6823f38d5541a1c41b`，对照原 [V1 产品设计 §5.2](../sources/V1/平台产品设计%20(2).md) 和 [持久步骤合同](ENG096-PersistentServiceCaseSteps.md)。本片补齐“无法满足全部必需目标时，独立部分继续、依赖部分等待”，保留原合同的明确用户目标与受信 P1–P5 适配器边界；不是模型推理或完整生命周期。

原 owned PostgreSQL/API 三项红验均 FAIL：PARTIAL 预览没有可采纳子图、原 ADOPT 拒绝部分确认字段、原目标结果/总览未接入。随后增加 `partial_offer`，在完整预览中保留全部必需目标、步骤合同和依赖，另列当前可选择的独立闭包、等待步骤与不支持的人工目标。只有目录来源已知、至少一个独立节点、至少一个不支持必需目标且没有未知全局条件时才允许部分采纳。排除责任角色造成的冲突沿原依赖传递；这些步骤没有实际 CaseStep，原 API 也不能执行。

企业在原方案页面核对同一 Case/Run、资料和诉求版本及来源 SHA 后，单独确认“只采纳独立部分，整体 PARTIAL”，填写明确原因，才以原请求键发送 `partial_adoption:true`。未确认、删目标、旧来源、来源未知、撤权、跨企业或非owner均拒绝。计划保存完整目标、完整预览、精确原请求与采纳事件，仅给独立闭包建立稳定步骤；省略新字段保持旧请求指纹。原 parent/key 锁、同参原事件重放、异参冲突和只读原键恢复均保留，没有自动业务执行或新授权。

不支持的全局附加条件不能假定不影响独立部分。其原 UPDATE_REQUEST 历史声明进入来源指纹；即使后来清空约束表单，已保留的必需全局条件仍阻止部分采纳。已有旧 fixed controlled_plan 的转换不在本片范围，明确拒绝，不放宽其守卫。部分计划依赖集合变化须明确替换并保留旧计划/键历史，不执行保号 local_revision；人工锁须先通过原 UNLOCK 明确解除。

P1 仅在已验证部分采纳证明且当前 request/service/catalog/registry 绑定有效时解除整体覆盖缺口，其他真实材料/事实/人工核对要求继续检查。部分计划的原资源关联、分派、接单、legacy receipt CREATE/提交及本地生命周期 gate 必须包含动作目标和全部前置节点，不能用空前置集合绕过未选步骤。资源 delivery-plan 的独立旁路也核当前部分计划证明；原权限、预约、资源容量和外部执行协议均未扩大。

原总览给已保存的部分计划添加入口与 PARTIAL/待人工提示；它仍是单条 SQL 的只读记录投影，不声称当前核验有效。打开入口重读当前身份、Case、Run、计划与原来源。原逐目标结果保留所有目标：实际独立材料或合成回执输出可 LOCAL_OUTPUT_VERIFIED，不支持目标为 UNSUPPORTED/转人工，被约束阻塞目标为 WAITING_DEPENDENCY。整体始终 PARTIAL，Case 全部目标完成仍为 false；不写 Case 为 FULFILLED，也不宣称机构审批或现实履约。

原完整 HTML 的离线 NodeVM/owned PG/ASGI 链实际 30 断言、22 HTTP、2 POST、1 ADOPT、1 次提交后丢响应：冷页 GET 原 key 取得 COMMITTED，再明确结束核对；恢复没有重发 ADOPT，原业务表不变。另实际观测 PostgreSQL parent 行锁等待，原获派专员 REQUEST_CHANGES 先提交200，等待的旧部分采纳预览409且没有计划。资源前置、原本人 ACCEPT、回执 SUBMIT/ACKNOWLEDGE 和核验也实际贯通，独立合成本地目标通过后整体仍 PARTIAL，权限快照不变。

最终修复源码3模块根回归：**103唯一PASS、0FAIL/ERROR/SKIP、2WARN、76.02秒**；初版27模块1039 PASS/1 FAIL单列，不算作最终源码验收或加总。初版源码独审另窗34个唯一用例PASS：首窗33 PASS/1 FAIL/0ERROR/0SKIP/2WARN、22.13秒；失败是独立 lifecycle helper 漏 row 参数，修正该调用后1 PASS/2WARN、1.21秒。该初版冻结源码未变，未把重测次数加总；最终源码独审另窗 **40唯一PASS、0FAIL/ERROR/SKIP、2WARN、23.08秒**，仅当前34部分+1原页目标扩展+4附加边界+1拒绝副作用。独审补测依赖替换双键历史恢复、人工锁保护、同键异参真实并发、未选回执与本地生命周期旁路。

已有计划新增必需目标的原HTML链另实际复现展示漏项1 FAIL：页面覆盖列表优先旧名单，虽然原ADOPT正文仍保留完整当前目标，用户确认却可能漏看新增目标。现改为优先展示全部当前目标，旧采纳目标单列为历史；17断言、16HTTP、2POST实测当前3目标、旧历史2目标、一份明确部分替换，整体仍PARTIAL。数值/字符串/false不能替代显式boolean true确认。

原失败窗口、命令、XML和exit保留：第二窗168 PASS/1 FAIL是旧目标结果helper试图删除已保存目标，改为同请求409并在新Case保存空目标，保留原UNKNOWN断言；第三窗24 PASS/1 FAIL是PG等待测试没有先重开已确认资料，原状态合同拒绝且未到持锁点，修正后实际PG等待通过。初版27模块还有1项旧人工锁helper同样错误删除已保存目标，修正为保留原目标并新增目标，原锁定/解锁/替换及历史断言保留。UI修复窗37 PASS/1 FAIL仅Python错误要求16个断言而Node实际15个全部通过，保留失败及真实链；新增历史名单与整体未完成两项实质断言后17项通过。初版宽回归首次命令因不存在的 cold_recovery 模块 exit4/NOT RUN，核现存模块后重新运行。公开归档只脱敏生成fixture会话repr，私有原件及哈希保留，XML结构/统计与原失败尾部空白不修剪。见 [results.json](evidence/partial-plan-20261013/results.json)。

额外独审实际红验发现：拒绝未选P3的原OFFER返回409，却通过ServicePlanBlocked观察失效处理把已核验P2标为invalidated。该缺陷不在此前39项覆盖中；原1 FAIL及计划前后状态完整保留。最终把无来源变化的越界操作拒绝改为普通Conflict，原P1/P2核验和整份plan不变；根和独审均实际重过。中间666源码17模块445 PASS和独审39 PASS被该新红验明确否定为可交付闭合，只列历史窗口；最终一行partial guard修复后重跑直接受影响功能和全部原registered steps共3模块，不把未变全域445/初版1039算成最新SHA测试。独审最终40也不与根103加总。

两 approval 仍 false/null/null。浏览器、Windows、安全prepare、真实/付费模型、生产部署/迁移、正式AT08/35及现实履约 NOT RUN；历史 Chromium data: `ERR_BLOCKED_BY_ADMINISTRATOR` 没有启动或换URL/工具重试。没有新Grant、registry、凭据或网络/安全权限配置。源码冻结 **5eb703caa0cd7d1e52b27a9e2a650a5cd86e5062**，15文件字节前后一致；独立分支正常推送与交付完整SHA由最终核对记录提供。

下一步由父级复核这份有限部分办理闭合：明确目标合同内的独立本地子图可以继续，未知全局条件、无目录能力和依赖阻塞仍需人工/新服务合同。不得据本片扩展真实外部服务或宣称原诉求完整完成。

源码空白检查PASS/exit0；公共证据首次暂存diff检查 **FAIL/exit2、8处原失败日志尾部空白**，原件未修剪，完整检查输出单独保留，不递归归档。证据清单130文件（不含manifest），56独审公开原件及总索引；根12份、独审4份仅脱敏生成fixture会话repr，完整私有原件保留。
