# 实施前冻结：原首次资源交付的合成方案 Approval

已普通fetch与实际ls-remote核对dev `3406fd9c62bf1f28fd1e7ef62932d8acd1b3a386`、main `31e7acb7e53bb1ab6465b9daae59de28757f7583`。无挂起Git操作/普通index.lock，平台空未持有锁保留；既有独审结束，无活动测试/API写入者，root唯一源码写入者。本片不继承跨环境状态，不重复资料导出、异议、人工锁、Run READ访问批准或一般依赖框架。

原§7.4/F2-T03/T05：现有case_resource_delivery已将首次两个或有限多个合成占位的确认、Case claim、版本比较、不可变关联与原回执合在同一PG事务，但只有120秒预览同意，没有独立持久方案Approval。仅补这一既有事务的批准前置，不批准其它资源路由、一般计划执行或外部动作。人工锁与Run READ租约均不是本批准。

默认关闭。必须显式启用、原LOCAL模式、由现有同进程FixtureDatabaseEvidence证明全新自有临时PG、精确当前endpoint/database OID/postmaster匹配，并限定既有enterprise_operator owner的park/org/Case范围。真实configured_app、部署脚本、环境配置、roles.sql与业务Grant不变。允许仅合成setup在既有preparations上加候选专用jsonb列及不可变前缀触发器，不接入生产迁移，不授予新数据库或业务权限。现有应用角色的preparations UPDATE权限承载有界独立Approval对象/事件；SQL触发器拒绝改写/截断/清空历史，与人工锁JSON分离。

闭环为原owner明确PROPOSE精确首次交付→明确APPROVE→可显式REVOKE→由同一原owner以本Approval UUID和原交付命令提交。原owner已有READ/PREPARE/EXECUTE及全部成员READ/HOLD，本片仅许可其原本可执行的资源决定，不把资料专员REVIEW或文本声明当审批权，不新增独立业务审批主体。执行身份固定ORIGINAL_OWNER_HTTP及原actor/role/Run UUID、revision/state/fence；不是worker租约或新技术Run。用途固定CASE_RESOURCE_DELIVERY。历史保存不表示当前批准仍有效。

Approval绑定独立UUID、原preparation/Case/Run/park/org/owner、原采用plan UUID/revision及定义指纹、service ID/version/catalog/source完整hash、材料revision与双槽实际版本/hash、P1当前VERIFY及事实用途来源、精确成员hold UUID/resource修订/规则/时段/数量/来源/有效期、原请求版本和全部显式目标。绑定完整原Deliver命令（包括理由、预览指纹和valid_until）及规范hash，不允许同批准改正文、换成员或换Case。当前授权绑定真实principal非敏感字段、READ/EXECUTE修订、PREPARE与资源READ/HOLD实际行版本和原范围；无显式revision的表使用PG xmin作为此次≤120秒合成窗口的不透明行版本，撤销恢复亦不能复活旧批准，不声称正式全局authority epoch。

批准期限不能超过原预览120秒或任一占位到期；不延长占位/权限期限，不自动重建预约。来源/计划/Run/资料/规则/占位/授权变化、撤权、期限或前置失效时当前批准不可用，必须明确新PROPOSE/APPROVE；旧对象与事件保持。REVOKE在当前原owner授权下允许来源已经变化，不执行资源取消或撤销已知实际效果。

每Case独立CAS revision最多64事件、最多8个Approval UUID；活动对象保留显式REVOKE额度，不能用新增提案或批准耗尽。事件稳定UUID、actor/key/完整指纹、Case范围、严格结构与串联hash、对象状态由原事件折叠，SQL历史前缀保护；同actor/key同参数只核对原事件，同key不同参数/跨Case拒绝。PROPOSE、APPROVE、REVOKE及原提交都可GET按本人原key恢复丢响应，不自动重发；COMMITTED只是历史保存，NOT_OBSERVED不是失败。未知结果UI保留原key，重新认证/刷新只GET，当前撤权403清私有内容。

启用候选的原resource-delivery写必须携带当前Approval；没有批准不能绕过原入口。旧已保存交付同键只返回原历史；不会因期限或撤销而重执行。Approval消费与原组合/claim/关联/回执同一PG事务，任何后续失败全部回滚，原同键只一个消费/一个交付。原parent锁/CAS、principal权限锁、资源互斥和source行锁保留；提交前及最后可能等待后再核对当前期限/授权/来源，原批准对象、actor、用途、精确请求与真实产物证明必须一致。目录发布者现仍无协作写协议，最后source读取到COMMIT的非协作目录更新窗口明确OPEN；不能宣称正式ServiceRelease或全来源线性化。

真实隔离PG/HTTP/Chromium验证正向持久批准/提交/冷重读、默认关闭和fixture证明拒绝、CAS/并发/重复写、同key改参、跨企业/Case/原角色越权、撤权及恢复授权版本、材料/原诉求/计划/目录/规则/Run变化、占位与批准期限跨末次锁等待、损坏/截断账本、丢响应GET恢复、迟到回复隔离、原业务回滚、隐私与窄屏。先精确冻结运行源码、独立审查，BLOCKED不合dev；只有LIMITED_PASS后正常候选push/dev快进/push和actual远端核验。根与独审窗口分别记录，不拼称全仓/原AT/Windows通过，失败原日志/XML私有保全。

仅代码、原合成流程、隔离测试与独审授权。真实能力默认关闭；正式发布/真实履约/真实对外调用/Case完成/分享/模型/通知不实施。main、强推、部署、凭据、安全网络与既有权限配置不改；旧a823a28不迁移。正式独立审批主体/Release/在途兼容等差距在本片之外继续明确，不以其业务授权缺口停止已授权候选开发。

开发损坏负例补充、实现前冻结：除了不可变前缀触发器，专用独立header列记录原最后事件revision/hash，由同一触发器随合法追加生成，禁止单独客户端修改。账本与header必须逐次对应；空账本降级、完整有效前缀截断也不能复活历史决定。只增这两个有界业务列及该固定用途触发器，不新增权限/生产迁移/通用审计框架；可信合成数据库owner故障注入可绕过触发器，但应用读取须识别未同步的原锚点。整个数据库及原锚点被可信owner一起改写不由本片提供密码学保证。
