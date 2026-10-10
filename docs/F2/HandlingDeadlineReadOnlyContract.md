# 来源明确的只读办理期限合同（实施前冻结）

基线 dev `799419cee674ebe0bab215cce2a977c5450c3677`，候选 `candidate/handling-deadline-readonly-20261010`。依据原产品§5.4、§6.2、§12.2、原 F2-T03/AT-29 及冻结的 `PR0-CoverageAt-a1e6022.md`。原资源 UTC/半开区间/缓冲、Hold TTL、Run READ 租约已经有工程验证，不重做、不把它们当服务 SLA。

当前 HandlingPolicy 只校验 calendar_ref/target_seconds/target_source_ref 的结构。没有实际日历、适用时区/时限来源解析、办理期限计算，也没有业务停表授权、独立批准或不可变停表账本。Run pause 是技术控制，资料待补/异议/访问撤销均不是合法停表证据。原资料 REVIEW、企业 CONFIRM、EXECUTE 不能推出办理时钟暂停权。本轮因此只读计算与来源核验，不新增暂停主体、Grant、角色、权限、迁移、写接口、正式法律判断或真实服务承诺。

最高价值最小连通切片：原资料事项页增加“办理期限与来源”只读区域和 GET `/api/preparations/{id}/handling-deadline`。默认关闭仍返回 UNKNOWN；先按原 preparation.scoped 的当前认证、READ、PREPARE/REVIEW_ASSIGNED、原 owner/获派专员/企业/园区范围核验，不能用关闭开关泄露跨企业事项。仅已签发、原 owner 同临时 UUID PG/cluster/OID/端点/启动与同进程证明限定的显式合成配置可启用。无环境自动配置、公开导入、任意文件、政策文本解析或生产迁移。

存储合同：最多16个明确资料事项，host 侧一次构造不可变规范 JSON 字节映射及独立 SHA-256；复制调用方对象，不保存到PG/浏览器，也不改变任何业务事件。来源精确绑定 park/org/owner/reviewer、Case/Run/preparation UUID、资料 revision、两个槽 ID/version/hash 的 snapshot、原 request revision/hash、服务 ID/version 与当前目录来源 hash 及 xmin 行版本（改后恢复原值也须显式重绑），以及原 CREATE 事件 ID/PG 时间/原 payload hash 与资料创建时间（两个 clock_timestamp 不要求相同，事件不得早于资料）。读取在原身份锁、资料行共享锁、目录来源读取后获取当前绑定（现有 app 无目录 UPDATE 权限，不能用需该权限的 FOR SHARE 也不新增授权；目录 hash 核对是本次读取时点的观察，不承诺串行化任意 owner 写入），任何变化 UNKNOWN，历史业务数据保持；显式新 host 配置才能重绑，没有自动延期/自动重绑。冷浏览器重新认证后只GET；新 Store/新 API 进程/PG重启无原配置/证明默认UNKNOWN，不声称持久化正式时钟。

合成来源必须有 SYNTHETIC 标记、稳定 ID/revision、明确文本及文本 SHA-256、有效期、服务版本/接单企业适用依据；policy 指向相同 source/calendar ID+revision+hash，明确业务 IANA 时区、正的 target_seconds（工作区间内真实经过秒数，不是自然日），开始依据仅原资料 CREATE 事件（合成资料准备起点，不是现实机构受理）。不从创建Run/访问批准/材料齐全自动推出现实受理。来源过期、不适用、hash不符、缺字段/多字段/错误类型/非法目标返回有界原因 UNKNOWN；不回显文本/私人材料、请求、token、DSN、owner配置或内部SQL。

日历合同：最多366个连续且逐日明确的日期，覆盖区间首尾都声明，所有日期必须存在；每个日期明确 WORKING/CLOSED，CLOSED 包括显式合成节假日/周末，绝不猜真实工作日或节假日。每工作日至多2个不重叠本地时窗，以带偏移 ISO 秒级端点表示，日期/时区/UTC偏移逐项交叉核对，半开 [start,end)。时区不存在、日历漏日、窗口倒序/交叠、非工作日有窗口、DST 本地不存在或歧义时间（即使附偏移也不猜 fold）返回 UNKNOWN。范围不足以确定 target 截止或截至当前观察的已用秒数均 UNKNOWN；不会跨范围外默认工作日。计算以 UTC aware datetime 计秒，公开 UTC 截止和相同瞬间的显式业务时区表示，窗口边界无重复秒。DB clock_timestamp 在所有锁等待后读取；耗时显示是本次 GET 的观察，不是前端自动倒计时、现实逾期或服务违约判断。

暂停合同：任何暂停输入/所谓停表来源均不能由本轮证明有权；非空声明只返回 PAUSE_AUTHORITY_UNAVAILABLE/UNKNOWN，不从 AWAITING_USER 自动减秒。没有 POST/PUT/DELETE，此路径写入405；技术Run暂停/补件/异议均不改变该只读时钟。仍缺的最小后续合同：明确由现有哪一授权主体提出/独立批准/结束、受控理由及适用来源版本、Case/当前时钟修订绑定、有效时段/迟到事件规则、不可变原始事件与独立head、CAS/幂等、PG同事务与丢响应恢复。未有上述现有授权不实现合法停表写入，也不给整个 AT29 PASS。

页面沿原资料事项：显式点击只读核对，展示 UNKNOWN/仅合成计算、来源引用与hash、开始/观察/UTC和业务截止/已用秒数/尚缺停表合同；动态内容只textContent。换身份、换事项、刷新资料、403或迟到旧响应即清除旧结果。每次响应核对 Case/Run/preparation 与资料revision；原未知写入仍按各原合同处理，本区域不重发、不新增写入或私有浏览器存储。

测试冻结要求：纯确定性日期/工作时窗/显式合成节假日/UTC与时区/边界/目标/漏日/DST/非法来源/非法暂停拒绝；真实HTTP/临时PostgreSQL当前权限与跨租户/撤权/资料及请求换版/来源变化/新Store冷恢复/实际锁等待/并发重复GET无业务写；真实 Chromium 原事项页320/1200、冷认证GET、未知/成功/403、迟到跨身份或事项、隐私/XSS与无横溢出。源码精确SHA冻结，普通候选push后由现有独立审查员另测；LIMITED_PASS后正常dev整合/推送，不改main/强推/部署/安全网络/凭据。失败原始日志私有保全，分别报告实际测试窗口、远端及未推送文件。旧 Windows a823a28 不迁移，F1/Windows/fullAT/正式SLA与合法停表仍未签收。
