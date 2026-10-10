# F2-T03 / AT29 来源明确的只读合成期限

原产品§6.2/§12.2要求工作日历、业务时区、时限来源及有权留痕的停表。基线 `799419cee674ebe0bab215cce2a977c5450c3677` 只有 HandlingPolicy 结构校验、资源 UTC/半开区间/缓冲和访问租约，不能据此给办理 SLA 或合法停表 PASS。先行合同 `22b1ea4cc638110e29df9007970e9bc6c42de226`，PG绑定澄清 `1e5e22abf62d91fc21765a7734a2a28a18f55d69`；冻结原需求映射不改。合同见 [HandlingDeadlineReadOnlyContract.md](HandlingDeadlineReadOnlyContract.md)。

精确源码 `9e0d7cf5f76ba768f98c77121f7bc0f7923ecb97` 独审 LIMITED_PASS。原资料事项页增只读核对区域，GET沿原owner/获派专员、READ及资料权限/企业/园区范围；默认UNKNOWN。只有已签发同进程、自有临时PG的明确合成来源可启用。未改 HandlingPolicy 正式发布语义，无新Grant/角色/DDL/写入口或生产开关。

来源复制成不可变字节与SHA-256，绑定Case/Run/资料UUID及revision、两个槽ID/version/hash组成的原snapshot、原请求revision/hash、服务版本/目录来源hash+xmin、原CREATE事件ID/时间/payload及资料创建时间。换材料、原请求、来源或开始证据UNKNOWN；目录改回旧值也不能复活原绑定。只能明确重建host测试配置，原业务历史不删除，也没有GET写入业务事件。

计算使用最多366个连续逐日明确记录、显式WORKING/CLOSED及最多两段带偏移本地时窗，不猜真实周末/节假日。交叉核对IANA时区/UTC偏移、[start,end)、有效期与适用服务/企业；缺源、缺日、缺时区/适用依据、错误hash、未覆盖观察或目标截止、DST歧义/不存在等UNKNOWN。秒数是工作时窗内真实UTC经过秒；公开UTC截止与同一瞬间的业务时区截止、本次GET观察和已用秒数。开始仅原合成资料CREATE，不能叫现实机构受理，页面没有自动倒计时或现实逾期/违约判断。源过期和撤权由实际锁等待后的时间/权限复核建立。

本轮没有合法业务停表授权：资料REVIEW、企业CONFIRM/EXECUTE、Run技术pause、等待补件和异议均不提供它。所有非空暂停声明UNKNOWN/PAUSE_AUTHORITY_UNAVAILABLE；该路径POST/PUT/PATCH/DELETE405。独立例子也只测试拒绝，没有假造“合法停表成功”。最小剩余合同是有现有授权的提出/独立批准/结束主体、适用源版本和受控理由、Case/时钟revision、时间与迟到事件、不可变事件及head、CAS/幂等、同事务和未知响应恢复；没有现有授权不能实施写入。

配置不持久化：冷浏览器重新认证后仅GET读取当前原配置；新Store或新的configured API进程无配置默认UNKNOWN。实际独占PG重启改变postmaster_start，旧enabled registry HTTP403失效；新configured API实际新PID默认UNKNOWN，未重签fixture proof，原业务/权限行保持。没有正式持久时钟或跨进程可迁移能力。目录hash/xmin是读取时点的观察，没有新增目录UPDATE授权或承诺串行化任意非合作owner写入。

| 独立窗口 | 实际通过 / FAIL / ERROR / SKIP | JUnit秒 | 受控运行秒 |
| --- | --- | --- | --- |
| 根13个完整相关模块 | 458 / 0 / 0 / 0 | 346.841 | 348.87976813316345 |
| 独审相同13个完整相关模块 | 458 / 0 / 0 / 0 | 355.827 | 357.41499638557434 |
| 独审自己实现的计算/权限/迟到响应探针 | 44 / 0 / 0 / 0 | 17.194 | 18.696245908737183 |
| 独审真实独占PG与新API进程重启 | 1 / 0 / 0 / 0 | 6.222 | 7.471391677856445 |
| 独审真实行/身份锁等待 | 2 / 0 / 0 / 0 | 5.083 | 6.381962060928345 |

五窗分别自然exit0，不加总为同一次测试。根窗口包含新API94项、原页面Chromium8项、原V1结构/资料/资源/Case目标/步骤及新输入串链/异议页面/诊断完整相关模块；模块清单和实际argv随证据提交。独立探针用自己的日历builder、逐秒截止oracle及HTTP/PG/browser逻辑，没有以重复导入开发者测试充当额外probe。原资料页320/1200冷认证、403清空、迟到身份/事项/同事项刷新、非匹配回应拒绝、XSS/textContent、无私有浏览器存储/横溢出均实际检查。

340源码路径首尾零漂移，manifest SHA-256 `9c3f360e2cbd36a62f7bea822db9e742388474ebedfeef445a1ded8a3490600f`；1481诊断AST函数ID精确匹配。独审报告 SHA-256 `8fd6b516bf83e7ee8013e1ebd41c575d679af67754e9b4d3779f12b39f9d1ffa`。见 [机器核验](evidence/handling-deadline-readonly/verification.json)、[独审报告](evidence/handling-deadline-readonly/independent-review/report.json)、[独审原件到公开副本映射](evidence/handling-deadline-readonly/independent-review/artifact-path-map.json)、[产物哈希](evidence/handling-deadline-readonly/artifact-hashes.json)。公开只有通过窗口日志/XML、原件hash、源码及安全状态；原失败日志/XML和私有PNG留忽略目录，不提交凭据或私密材料。

开发历史窗口85PASS、6PASS/2FAIL、8PASS、156PASS单独保留，不覆盖最终冻结源。两条浏览器FAIL是测试在route.fetch回调尚未完成时断言held已有回应；仅补等待同步，原日志保全。旧objection输出在pytest启动前隔离，未再改tracked旧证据；原新链helper六份固定私有产物在回归前逐字节复制/hash保全，历史失败logs未覆盖。两轮正式相关回归开始/结束Gitclean；本轮不重做资料包导出或原异议实现。

原AT29全部仍NOT_RUN：真实政策/正式发布日历、现实机构受理起点/时限、合法停表与独立批准账本、正式持久时钟未有来源/授权或未实现。ENG098资源/执行者权限缺口、未消费Approval新PID写关闭、真实Case完成/履约、完整F2/PR0/fullAT/全仓/F1/Windows仍未签收；旧a823a28 Windows修复未迁移。没有模型、外部通知、部署、main变更、强推或凭据/安全网络修改。
