# P5 本地 Case 记录隔离预演：实施前合同

基线 aac5489710b4364a78e83383c0ec9284a2b213fb，正常 fetch 与实际远端一致，88403af18b95b361114b303c3fae636f286d91b4 为祖先。只在独立候选分支开发；无挂起 Git 操作，平台索引刷新锁 inode 1310816 保留。源码唯一写入者为本环境主实例；独立审查仅自己的私有证据。main 不改，资料包不重做。

复用原 P1–P4 和 case_lifecycle.read/command。必填 lifecycle_sequence 只允许 REVALIDATE、REVALIDATE_CLOSE、REVALIDATE_CLOSE_REOPEN 三种固定序列；模拟企业 owner 身份与执行者分离，每一步由原 read 获取 revision/cycle/current_snapshot，REOPEN 不携带验证 hash。关闭由明确选择触发，ACK 不自动关闭。REQUEST_CHANGES 保留原纠正要求，原 REVALIDATE 拒绝；不补 ACK 或成功 bool。记录原命令正文、key/指纹、逐步返回、最终 read、完整 ledger/不可变 events，单纯恢复 GET 不重放。

P2 原处理器在其影子 rollback 前，通过默认 no-op 的保护钩子，仅为 P5 捕获完整资源、资源授权、组合及成员原行。P5 在同一 P4 影子准确重建原 UUID、规则、hold/member/claim/receipt 映射；不按 UUID 排序猜测来源，不扩大已校验的 READ/HOLD 范围。此重建是原 P2 合成影子的保存与复用，不是正式 Grant 或来源权限修复。原资料、资源、本人接受及回执条件均由原处理器真实核验，数据库时钟在最终锁后读取。拒绝/到期/撤权/hash 或版本变化不得伪造满足。

P5 静态影子表与封闭 SQL 见 P5LocalCasePreviewSQLContract.json。30 个 pg_temp 表，新增 ledger/events 保留原唯一索引；每个处理器 SQL 必须精确命中闭包，不回落 public。保留原 P4 SQL/TABLES/CONTRACT 和默认输出，保护钩子默认不产生额外数据。全部影子事务最终 rollback/close，不消费 4 个 PENDING outbox，不通知，不创建新正式权限、政策批准、模型调用或 Case 完成。

关闭检查点 Case=WAITING_CONFIRMATION，绝不是 FULFILLED；REOPEN 最终 Case=REOPENED、cycle=2、验证快照为空、最终 read verification_current=false、四项 required_rechecks。不自动重验、不释放 holds，不把 REOPEN 当当前校验有效。保存检查点与最终状态，所有成果带 SYNTHETIC/SIMULATED_ROLES_ONLY/PREVIEW_EXECUTION、qualification=NOT_EVALUATED、external_acceptance=NOT_SUBMITTED、offline_fulfillment=NO_EVIDENCE、case_goal_completed=false。

独立 scope/SQLite namespace、不可变 triggers、0600 文件/0700目录、BEGIN EXCLUSIVE、128 总记录/16 每事项、每份文档和 proof 64KiB。proof 绑定完整原 artifact、显式序列、actor/key、Case/Run、资料 revision/两槽 id/version/hash、原请求版本、资源规则、当前参与者与来源 SHA，幂等指纹含序列。原来源资格检查先于历史/幂等读取，三来源 CAS 和执行后复核；未知结果仅 GET 原 key。未观察保留未知，不自动重发；403 清页面私有视图，导航/身份/草稿变化的迟到回复不得回填。

工程验收要求真实 PostgreSQL/HTTP/Chromium，精确冻结源码后主测和独立运行覆盖原调用、关闭/重开、纠正、过期/撤权、跨企业/角色、规则/材料/回执 hash/换版、旧 revision、并发同键/重复、晚响应、丢响应/冷 GET、SQL/文档篡改和隐私负例；原 P1–P4 与生命周期相关回归。保存所有失败窗口；普通推候选后独审，未签收不合开发分支。

只承认原发行进程仍存活的已有证明范围；无 P5 跨进程证明迁移或新增代理层。完整 issuer 退出恢复、full AT14、Windows 原生验收仍为后续门槛。保留 P4 旧 2c 错键/597PASS 与 issuer 退出 500 故障窗口；issuer 退出 503 不是全重启成功。仅合成工程范围，未证明真实材料交付或真人批准。
