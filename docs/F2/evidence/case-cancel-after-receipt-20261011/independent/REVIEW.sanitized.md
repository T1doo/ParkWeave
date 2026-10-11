# 独立审查：已有人工回执后的取消核对

**结论：LIMITED_PASS。** 已审范围无剩余产品阻断；父任务38模块最终窗口尚在运行，本报告不预签该窗口结果。

最终源码完整 SHA：`796b41ad8939ba1d067f84f137a4d2a1861f06d4`。父任务提供提交身份；独审未执行 Git 操作。独立核对405文件与最终manifest SHA256 `cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5` 一致，当前零漂移。

实际226项独审发生在第六窗口，manifest SHA256 `e103cb121d8396c7e566367705cbc44776e20feb66e325f96ca40dd2af81cb25`。该窗口仍为未提交源码；226 PASS / 0 FAIL / 0 ERROR / 0 SKIP，exit0，进程186.994秒、JUnit184.928秒、pytest汇总184.93秒。两个弃用/环境警告保留，无atexit清理诊断。

第六到最终提交仅十个旧schema测试文件改变；src、scripts、pyproject、新backend/offline完整模块、原VM和独审探针字节相同。这一绑定属于产品同字节及测试变动的静态核验，没有将226项称为最终manifest下新跑的窗口。完整diff保存在 `schema-oracle-final-static.diff`。

两个完整模块共141项owned PG/ASGI和51项离线Node；独立额外34项含24项owned PG/ASGI及10项Node。因此本次实际226项为165项PG/ASGI与61项Node，没有SQLite替代。

## 实际独立窗口

| 窗口 | PASS | FAIL | ERROR | SKIP | exit | 源码manifest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| fourth-extra-probes | 22 | 2 | 0 | 0 | 1 | `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0` |
| fourth-oracle-retest | 2 | 0 | 0 | 0 | 0 | `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0` |
| fourth-cold-hydrate-failure | 0 | 1 | 0 | 0 | 1 | `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0` |
| fourth-prefix-projection | 0 | 3 | 0 | 0 | 1 | `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0` |
| fourth-rehashed-initial | 0 | 2 | 0 | 0 | 1 | `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0` |
| fifth-full-independent-probes | 30 | 0 | 0 | 0 | 0 | `d51af3cccec273588727773f5ab2e8989891b5f9cf11bc20806c8ed87e2f65de` |
| fifth-cross-case-capture | 0 | 4 | 0 | 0 | 1 | `d51af3cccec273588727773f5ab2e8989891b5f9cf11bc20806c8ed87e2f65de` |
| sixth-complete-backend-ui-and-probes | 226 | 0 | 0 | 0 | 0 | `e103cb121d8396c7e566367705cbc44776e20feb66e325f96ca40dd2af81cb25` |

每窗均有独立原stdout、JUnit、run和405源码清单，前后零漂移；各窗不相加宣称一个全PASS窗口。原第四22P2F中的两个FAIL为自有Oracle错误：资源独立释放应为RELEASED；未来句柄原1毫秒偏移被Date.now消耗。原件保留，修正后同ID先2PASS，随后第六也PASS。

## 已复现并修复的产品问题

| 问题 | 原实际反例 | 第六同ID结果 |
| --- | --- | --- |
| AR-UI-001，MEDIUM | 冷unknown REQUEST漏拦七个业务form，1个JUnit FAIL；另原standalone Node exit1 | 1 PASS；原同argv、原探针字节不改的最终standalone Node exit0 |
| AR-PROOF-002，MEDIUM | 当前REVALIDATE投影三种损坏仍允许请求；首REQUEST一致重hash未证明cycle/初始Case状态仍被接受，5个FAIL | 5 PASS |
| AR-UI-003，MEDIUM | plan/delivery/approval错用别的Case导致误禁；receipt CREATE错用已有receipt Case导致漏拦，4个FAIL | 4 PASS |

所有十个实际产品FAIL与两个自有Oracle FAIL的完整ID及原→第六结果在 `review.json.failure_same_id_map`；原窗口始终保持失败，未转签。早期静态五项（terminal64原key恢复、重建整份snapshot、RECONCILING投影、Run.input形状、历史容量）也已由完整新backend对应边界通过覆盖。

独立standalone原探针SHA256 `f229caaf71672a2ad34142c3d856ee51d4bebf69aaa8bf64ea2c891edec741d4` 未变，命令为 `node .runtime/case-cancel-after-receipt/independent-review/unknown_handle_capture.js capture`。新 `final-unknown-handle-capture.log/run.json` 记录exit0，八个forms均prevented/stopped，最终405前后零漂移。此独立Node没有JUnit ID，未计入226。

## 最终十个测试Oracle修订

十个原快照各自SHA与第六405清单一致，完整最终diff SHA256 `ac8959b84e919bfaab7509c697928174f3fe7bbdf923dd5b7eaad80200c280f9`。当前版本31→32、未来版本32→33。历史030/031重放仍在原创建票据授权的独有fixture事务中，仅临时去掉更高schema marker；031保留max31、数据库/票据存在、提交/回滚/不泄漏断言。当前fixture与重复执行的两处SQL改用032。没有删业务、权限、回滚或旧历史断言，没有增加产品权限。

父任务另行执行schema-oracles原窗11PASS/2setupERROR，修正3节点窗3PASS；独审读取原JUnit/stdout/run核验了真实计数和hash。两个setupERROR是当前schema32数据库重复执行旧031被原严格门拒绝。旧原ERROR证据保留，3PASS只复验列出的三个节点；不宣称13项或十个模块最终单窗全PASS。

## 有限功能审查范围

- Original product design sections5.5/7.1/7.4 and frozen finite reconciliation contract.
- Ordinary verified successful SYNTHETIC, pure local manual receipts, whole ACCEPT/CREATE/OFFER and receipt version/decision lineage; effects/isolated sources/closed history rejected.
- Owner READ/PREPARE/EXECUTE, strict typed inputs, actor/fingerprint/source CAS, atomic REQUEST/RECONCILE/CONFIRM and exact whole-history assessment.
- Parent->dispatch->Case/local locking; owned real PostgreSQL lock waiting for request vs receipt SUBMIT/ACK/material/plan/resource writers in both winning orders.
- All business write families and bypass parents frozen under RECONCILING/CANCELLED; both plan read/rejected-observation implicit invalidation paths blocked.
- Old-key GET/history recovery and POST conflict, response loss GET-only, terminal-capacity recovery, rollback on event failure and same/different key concurrency.
- Existing historical cold reads and independent resource release with original rights; original resources still consume capacity until separately released.
- Offline NodeVM late UI responses, same/other Case action scope, opaque8/24h handles, no automatic POST or all-known confirmation.
- Migration032 existing finite CHECKs only; original creation-ticket owner/native/privilege boundary retained.

## 限制与剩余事项

- 本片仅普通已核实成功SYNTHETIC纯本地人工流程；没有外部/隔离效果或本地关闭历史。REQUEST始终先RECONCILING，核对只写专用owner账本，UNRESOLVED保持冻结，全known仍需另一次明确CONFIRM_CANCEL；原SUBMIT/ACK等入口未放宽。
- 所有旧资料、Run、ACCEPT/receipt历史和资源保持。取消不释放容量，独立释放保持自身当前权限。不是完整Case生命周期、没有恢复。
- 父任务最终38完整模块窗口：RUNNING，启动 2026-10-11T15:29:49.846599+00:00，此报告无最终成绩。归档/交付SHA/正常push与远端洁净核验由父任务另行完成。
- 浏览器NOT RUN（0 attempts）；历史ERR_BLOCKED_BY_ADMINISTRATOR未重试。真实模型、部署、生产迁移、凭据配置、新生产Grant均NOT RUN；本审没有产品/tests/docs/Git写入。
- 原历史fixture-b Case0根因仍UNCONFIRMED；本报告未宣称其权限或lease修复。旧阶段原报告和失败hash保持，未覆盖。
- 无全仓PASS或独立native Windows结论。

## 核心原证据

- `sixth-complete-backend-ui-and-probes.log` SHA256 `f460c9d4e1dbe5b4285bcd0f5429dde801791c16a35cef7551396eebc6418ce3`。
- `sixth-complete-backend-ui-and-probes.xml` SHA256 `edf5e695451b00593f9bd1a23c4061e4b56609d152203b46dc00ed1ca0f6a194`。
- `final-unknown-handle-capture.log` SHA256 `a5d588c2430843ad31266e93639b8d578507b46eeee4c92808549d388925a0b0`。
- `review-inputs-manifest.json` SHA256 `8157c3f24d186759b24f2aeb607983c9ca437e01b14b5f710187d9308b114e5e`，所有签署前独审文件原字节hash；旧第四/第五阶段报告hash受保护。
- `review.json` 是本报告机器记录。文件名均相对独审目录；原raw可由父任务按既定规则脱敏导出，不改私有输入。
