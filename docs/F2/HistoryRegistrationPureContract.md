# 默认关闭的合成登记一致性合同

父候选 `008ecdaf767eec4e5d1dc9e82074b2781c3502d8`；独立分支 `acceptance/history-registration-contract-20261011`，不入dev/main。本片只实现获准的纯模块 `history_registration_contract.py` 和合成测试，不建立持久信任根或访问许可。原只读历史登记/安装/数据库/绝对期限边界见 [P45HistorySummaryContract](P45HistorySummaryContract.md)。

`check_history_registration_contract(declaration, before, after, enabled_for_synthetic_checks=False)` 默认 UNKNOWN。输入仅精确不可变合成模型；没有文件/DB/网络/环境/当前时钟读取，没有registry、原行/快照复制、proof解析、loader/factory接线、OS/凭据/Grant或旧执行链修改。

字段：声明kind/schema/purpose/enrollment_id/revision、既有安装owner/DB owner/app role引用和批准manifest摘要；安装UUID/正整数代际/绝对root/owner；数据库name/规范OID/system_identifier/真实data_directory引用/owner；精确本人park/org/preparation/Case/Run/stage/scope/namespace/原文档版本/合同；1–16个唯一原id/key/row_hash/source_hash锚；UTC绝对valid_from/valid_until及revoked/revoked_at。原P4 v2/P5 v3合同常量按父代码固定，仅作结构兼容，不作执行proof。

独立首末观察另行显式传入当前登记、安装/DB/本人范围/锚/manifest、已知revision最低值、ever_revoked、当前READ/来源布尔及UTC时刻，并声明合成观察完整、当前代际已知、维护写/应用读隔离可确认。缺任一观察/可信代际/隔离、同SID文件/自报/旧proof来源、错类型或不完整观察返回 UNKNOWN；不从声明/hash推断缺失信息。这些标志只是测试输入，纯函数不认证它们，也没有签发它们的能力。

完整观察下，已知非法声明、安装/DB/本人/stage/原锚不匹配、期限外、终态撤销、已知revision/ever_revoked回退、倒退时钟或首末状态变化返回 MISMATCH。只有全部字段一致且期限内、当前READ/来源观察为true才返回 MATCH。结果只有固定classification/reason，不含输入标识、键、正文、proof或许可；bool(result)明确拒绝。MATCH只说明合成声明一致，不表示实际READ、隔离或代际已由真实部署验证。重新构造、新READ与进程启动不改变期限/终态撤销，变更声明不能匹配原独立观察。

UTC限精确datetime和标准库固定零偏移timezone，拒绝naive/非零偏移及自定义tzinfo；版本、布尔、数值须类型精确，bool不当int；OID/system_identifier为有界规范正整数字符串。路径仅纯语法与精确字符串比较，不resolve/stat，不证明文件owner/ACL。没有PID/postmaster_start恒定许可字段，不修改旧迁移回执的启动代际要求。

威胁限界：已知外部当前观察/floor不同可识别不一致；整套旧登记、撤销/代际/时间观察一起回放且不可区分时，纯函数无法识别。测试明确保留该MATCH反例，绝不声称防完整备份回滚；没有可信当前代际时必须UNKNOWN。现有同SID文件、路径或hash不能成为新authority。真实独立安装锚和维护隔离仍是实际启用前提。

本模块无状态，因此不会保存期限、revision下限或撤销记录，也不会自行续期。若调用者伪造或同时替换所有独立观察，纯字段比较不能证明生命周期连续性；终态撤销、绝对期限和revision回退结论仅相对于显式传入且保留这些事实的观察。真实防复活责任仍在以后另批的可信维护与当前代际边界。

本次证据仅签纯一致性及合成默认API门，不签全issuer/API/worker退出恢复、PG重启、持久注册、Windows/整页或浏览器验收；原data: ERR_BLOCKED_BY_ADMINISTRATOR继续暂停。成功分类未接生产API；提供分类作summary_reader也必须403。

本片完成后实际启用的最小待批清单仅为：①现有部署/安装所有者、DB owner及应用角色精确目标与可验证维护隔离；②真实安装根/数据库name/OID/system_identifier/data_directory绑定、未随旧备份回滚的可信当前安装代际来源及恢复边界；③单个本人/tenant/Case/Run/preparation/P4或P5/namespace/独立批准原记录manifest；④明确UTC起止及终态撤销维护者/传播范围；⑤具体持久存储/最小SELECT权限差异、精确历史复制范围和显式只读loader接线。以上均另批，本片不自动实施。若现有部署无法提供②或①，保持关闭，不能自行增加后台、账号、凭据或安全权限。
