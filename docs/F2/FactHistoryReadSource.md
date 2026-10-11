# 声明事实 Case：独立当前 READ 来源合同

原产品 §5.1 和 F2-T01 要求事实按本人、同企业、同用途授权复用，保留来源/版本、显式选择和未知；不自动共享、默认解决冲突或认定真实性。本片从 dev `873e426255cb62c55cf485cb81e1d1c3c706c373` 创建独立候选，排除未集成摘要页的四个提交。root 唯一源码/Git写入者，独审单独串行验证。

`fact_history_read_source.project` 是纯合同/投影；必须由已验权的服务端提供行，不是公开请求输入或授权入口。`source_descriptor` 复用 Store 字段 READ；history_summary 原 READ、本人/park/org、Case/Run、SYNTHETIC、资源/材料和数据库身份校验保持。只支持既有 SERVICE_PREPARATION、三个既有字段、原合成来源；不新增权限、凭据、schema、登记、网络路由或配置。原 EXECUTE/PREPARE/WRITE、执行 gate 和完整正文入口不变。

显式用途账本须与原 preparation_events 的动作、本人、Case/Run、修订及决定 hash 一一对应；拒绝删账本降级、仅声明未选择、未知用途/字段、重复来源或选择冲突。只接受原明确选中的真实所属来源 id、版本、指纹及完整当前行匹配，UTC 有效期和未撤回状态。既有显式选择仅在此 Case 用途解决竞争来源，不改变全局事实；不自动选择最新项。文档来源仍由原 bundle 账本/提交事件、材料版本/正文 hash、范围及撤回检查维护，假设不能充当事实来源。缺失/变化/撤回/到期均拒绝。旧执行权限代际不充当读许可，撤回 EXECUTE/PREPARE/WRITE 不阻止仍具所需当前 READ 的摘要读取。

只把固定用途/字段及不透明来源指纹加入现有历史来源比较；不返回值、片段、源标识、选择理由、账本全文或 proof，不评估真实性/资格、恢复执行或证明。历史仍需原独立可信内存基线及行锚；不能根据历史自述登记许可或重签 proof。普通未声明 Case 来源 hash 保持原算法。

沿原只读事务前后核查并复用事实字段协作锁，非协作变更由快照比较拒绝；不宣称全部来源原子性。完整 issuer 重启/持久登记、真实网络/页面验收仍未完成。浏览器 data: 管理拒绝持续暂停；本片不启动浏览器、不切换 URL、不更改策略。纯合同、已有隔离 PG 的进程内测试与独立审查只为本片提供证据，旧 317 项不重复作为新成果。

末端时效：目录/资源/材料/数据库身份处理之后再次核对独立事实 READ 描述；描述读取末尾再核字段权限和数据库时钟下的来源有效期。目录阶段注入有界延时的真实数据库时钟负测覆盖等待跨期限，不声称证明另进程真实锁竞争。嵌套收据与来源逐项递归检查类型和值，不能用 Python 的 True==1 或 17==17.0 替代来源完整性。

精确源码 `f2298026997376e4651e6b6f65c220d4bbb8e38f`：378源码路径冻结 manifest SHA256 `48ab8244776ed134207d35fd536c6602743469bbc72361f3a9c76c2cff7438a2`，root与独审前后零漂移。root和独审分别实际137 PASS/0FAIL/0ERROR/0SKIP；55新纯合同、35声明事实隔离PG进程内、1普通Case兼容、46原纯投影相关回归。独审collection/JUnit 137 distinct节点完全一致，35自有PID代际及wrapper退出，资源已释放。结论 LIMITED_PASS，不签页面、实际网络或完整产品验收。

脱敏证据：[root报告](evidence/fact-history-read-source/root-report-safe.json)、[独审报告](evidence/fact-history-read-source/independent-report-safe.json)（SHA256 `d063c67f3e344a1a8b83e9e7eaba00f1cfe0813d51abda6b058f68fe0804b2cc`）。独审未重复复现旧开发字节；原fixture缺双资源0PASS1FAIL、嵌套类型缺陷根侧实际复现0PASS1FAIL日志均保留，修后原断言未放宽。原旧实例失败、页面管理员拒绝和已有317范围不改签或转算。原日志/JUnit/进程argv只留私有runtime，不提交公开仓库。

不需要新权限即可完成上述合同；后续持久化必须另明确登记维护者、受信安装/数据库绑定、绝对期限和撤销维护边界。本片不自动接纳旧历史或持久化proof，原 configured_app 保持默认拒绝，原完整GET/POST资格不变。摘要页候选 `35a2edb76159e2d0d43ca4dc7e6e7a812aaa394c` 的四提交不在本片开发祖先中。Windows原生、CI和全AT未验收。
