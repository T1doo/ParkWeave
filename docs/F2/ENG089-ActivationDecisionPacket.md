# ENG089：一次性审核的启用决定包（尚未执行）

本文件把 ENG088 规则发布与 ENG089 单 Run 协作访问的后续工作分成代码、部署初始化、真正访问扩大。用户目前仅授权第一类及隔离 Mock 测试；后两类没有执行。不把“需权威合同”当作无限等待：以下给出可批准、可调整、可拒绝的具体推荐方案，供统筹审核。

## 推荐决定

| 可决定项 | 推荐方案 | 确认后发生的实际变化 |
| --- | --- | --- |
| 规则提交 | 本服务所属机构指定的已有目录经办人，建议用独立服务专员账户，按原设计导入权威来源；企业仅可提出修订建议。精确park/org/service及来源版本，不改其他服务 | 该已有目录经办账号获得精确服务RULE_SUBMIT能力。不新建账号或角色，不借用EXECUTE。 |
| 规则审核 | 园区指定的已有规则审核账户，建议由专员岗位承担；与该稿作者不同，必须有该服务RULE_REVIEW能力 | 该账号明确获得规则审批范围，现有资料REVIEW_ASSIGNED本身不扩大。 |
| 规则发布/撤回 | 园区指定的已有目录负责人账户，建议由资源管理员岗位承担；与当前审核者不同；RULE_PUBLISH/RULE_WITHDRAW精确到服务 | 该账号能发布/撤回经过审核的服务版本；模型草稿与人工材料TRUE不能直接发布。 |
| 单Run申请 | 当前Run所属企业经办人；具名同park/org现有service_executor，READ固定，不更改角色 | 创建访问申请业务记录，无申请即赋权，无跨企业/其他Run默认范围。 |
| 单Run审批/撤销 | 为每个试点Run指定一个已有访问审批账户，建议园区指定访问管理员承担；Mock用独立mock-run-access-approver，不把资料专员权限视作授权。申请人、受益人与审批人分离。经办人可撤销自己的批准，审批主体可撤销其获授权Run的批准 | 审批账户获得列明Run的RUN_READ_APPROVE/RUN_READ_REVOKE能力；批准后才给具名受益人一个期限内Run访问。具体已有账号ID由审核时填入，不猜测真实人员。 |
| Run期限/范围 | 每次最长8小时，默认4小时；审批只能缩短申请范围，起止UTC，自动到期；不允许通配园区/企业/Run；只READ | 给目标账户真实单Run读取权；不是CONTROL/EXECUTE/FILE_READ或外部OS权限。期限/身份/READ/Run版本或撤销变化后缓存不得沿用，旧批准不得自动恢复。 |
| 首批启用范围 | 一份列明的园区/企业/服务/Run清单；所有账号已存在且有同tenant READ；先启用试点后重新评审扩围，不自动授予新Run | 只清单对象发生真实变化；其他对象仍默认拒绝。无法提供清单/合法现有账号时，不执行初始化或授予。 |

ENG088 Mock作者enterprise_operator只用于演示提交/独立审核/发布时序，不决定正式规则作者岗位；生产接入按本推荐的目录经办人明确RULE_SUBMIT，接入适配代码需再验证角色能力合同。推荐岗位是RACI建议，不是现有角色天然权限。候选代码复用四角色字段，但APPROVE/PUBLISH仍必须交叉满足当前具名主体、精确对象、显式能力和期限。审核可以替换推荐岗位/已有账户，不允许省略独立审批或改为应用自授。

## 三类工作及最小权限

| 类别 | 具体交付/动作 | 是否产生真实访问扩大 |
| --- | --- | --- |
| 代码开发（本轮已授权） | 独立默认关闭的候选合同/API/UI、专用SQLite、Mock角色/READ事实、版本/期限/CAS/审计、浏览器和回归；候选迁移/接口需求只文档 | 无。生产API未挂载，部署数据库未变；没有身份、凭据、Grant、assignment写入。 |
| 部署初始化（待审核） | 用现有获授权迁移机制创建空的rule_versions、rule_reviews、rule_releases、rule_events及run_access_requests、run_access_decisions、run_access_events；另建空的rule_publication_authorities与run_access_authorities，存具名主体/精确scope/动作/期限/active/revision；补期限/版本/撤回引用所需结构。新增受限事务函数但不给PUBLIC/app可调用权，路由仍关闭；不建数据库角色，不更换owner，不写主体/授权/assignment | 空结构本身不授予用户访问。DDL及新对象的默认不可调用约束仍属于需要审核的初始化动作，不能由本次候选测试代办。 |
| 技术最小写权限（待审核） | app直接DML只限新规则草稿/访问申请的SELECT/INSERT及列明草稿状态UPDATE；app只读新的authorities表，无写权；审核/发布/批准/撤销决定、不可变events及assignment写入全部function-only，不给app直接写决定/events/assignment权限。通过列明窄事务函数执行，不授任意assignment表写权。现有preparation_catalog保留SELECT，新增发布只读解析器读取规则release | 这是实际应用技术权限改变，必须单列批准，不能称为单纯代码或无害初始化。不得给app principals/capability_grants写权、DDL、DELETE或owner身份。 |
| 真实主体授权（待审核） | 有权方通过现有授权配置管理流程将列明RULE_*、RUN_READ_APPROVE/REVOKE记录写入新的authorities表，绑定具名已有账号、精确对象、期限及递增revision；这不往旧capability_grants塞入任意新cap、不改通用角色能力，应用只读该配置 | 真实审批/发布权扩大。不得把Mock persona、角色名称、文本reviewer_id或原资料审核Grant作为凭证。 |
| 单Run真正赋权（待审核后按申请执行） | 经当前合法审批后，受限函数事务写入精确(principal_id,run_id,park_id,org_id) active assignment，关联批准ID、版本与到期时间；撤销只将该关联失效并记录不可变事件。拒绝/取消不写assignment | 目标现有service_executor获得指定Run的实际读取权。不是申请即写入，不执行setup assign_status，不批量赋所有Run。 |
| 所有使用路径的有效期（启用前必须完成） | scoped_run、controlled_plans、service_dispatches、executor_receipts以及其他直接查询assignment的路径统一使用当前身份/READ/tenant/Run/批准版本/expiry与撤销guard。旧assignment不自动转成有期限的新批准；保留兼容或重新审批策略须明确 | 不新增通用能力，但决定已有路径能看/做什么，必须作为整体验收范围。不能只给新页面校验TTL而让旧查询继续使用过期assignment。 |

4h是待审核的生产默认建议，Mock UI使用4h初值但API仅强制8h上限；不是既有正式策略。每个Run本候选最多一份当前请求/批准，不引入批量多对象授权。

生产兼容建议：既有active legacy assignment保持原边界，不能由新候选默认补期限、替换或撤销；对已具现有访问的(principal,Run)返回“已有合法访问，无需新申请”。新申请只处理缺少有效assignment的精确绑定，写入新增批准来源与expires_at。撤销必须匹配当前批准ID/版本，不能撤销他人后续批准或旧legacy记录。所有读路径应区分未迁移的legacy与受期限约束的新managed binding；不把NULL期限认作新批准或自动到期，相关兼容与历史数据验收须在初始化前冻结。

推荐assignment写函数仅接受“当前已批准的request_id及预期版本”，在函数内锁定相关身份/Run/批准，验证当前角色/READ、申请人与受益人/审批人分离、精确tenant/Run、期限、未撤回与未消费版本，事务写单一assignment和审计。不得允许函数接受任意目标/Run列表而绕过批准。应用不持有owner凭据；新增函数默认PUBLIC不可执行，获批后仅给现有app身份精确EXECUTE。新函数由现有合法迁移身份建立，推荐受限SECURITY DEFINER、固定search_path、静态SQL和精确对象检查，不给app owner权限或通用setter；调用者来自现有后端认证事务，客户端不能指定actor，API和函数共同检查当前身份/能力，不能信任请求体approved标记。app可直接写草稿/申请，所有批准/发布/撤回/撤销及事件只能由该受限事务函数写入。函数定义与app的精确EXECUTE属于需审查的权限边界，本轮没有生成或执行这些真实SQL。

## assignment真实影响必须如实说明

当前Store.scoped_run给非企业角色除READ外一律拒绝；assignment不会直接赋CONTROL/EXECUTE/FILE_READ。不过它也是既有服务协作路径的先决条件：执行者目录枚举、方案核验、本人offer查看/接受、已单独分派给本人的合成receipt操作。因此实际赋权的说明应为“精确Run READ及当前既有、仍需独立分派的合成协作路径可达”，不能只说多看一个页面。审批单应列出这些附带可达范围；如果审核仅允许纯Run状态读取，需先完成新的窄访问绑定，并确认现有流程不读取该绑定，再另行审核赋权。**推荐先以现有assignment完整影响范围做显式试点审查，不隐瞒关联操作。**

不会新增动作EXECUTE/CONTROL/FILE_READ，不绕过dispatch/receipt各自的当前分派与材料父版本校验；不会创建外部账号、发送外部材料或承诺真实履约。

## 可供一次性确认的清单

审核时只需决定：采用/调整上述岗位与分离规则；列明现有账户ID及park/org/service/Run清单；接受4h默认/8h上限及撤销责任；接受assignment对既有被分派合成协作路径的完整影响，或要求先做纯读绑定；分别批准空结构初始化、app最小技术写权和具名主体能力配置。源码测试完成不自动批准任何一项。未决定的具体账号/对象不会被代码猜填，未获批部分保持关闭。

## ENG090：优先仅隔离合成的具体最小决定

生产方案不能混同本次演示初始化。本次仅park-a/org-a/candidate-intake与mock-run-a，在专用runtime目录建立两份SQLite：rules五表candidate_meta/rules/releases/events/assessments，access四表access_meta/tickets/leases/events（实际完整表名前缀见[ENG090](ENG090-LocalReviewPath.md)）；仅OS文件写，无PG连接/DDL/GRANT/真实主体或凭据。受益人仅Mock mock-run-executor、READ、默认4h最多8h；Mock独立作者/审核/发布、访问申请/批准/撤销标签显式列明。候选撤销/到期拒绝缓存、审计保留、只停自己子进程，旧assignment零影响。推荐只采用这个范围；上述未来生产表、技术权限、具名主体与真实赋权均另行审核，不以一次演示决定泛化授权。
