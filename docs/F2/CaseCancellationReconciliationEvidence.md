# 已有人工回执后的取消请求与核对：交付证据

本片按 [实施前有限合同](CaseCancellationReconciliationContract.md) 延续原产品 §5.5/§7.1/§7.4。仅已核实成功建单、普通 SYNTHETIC、真实接单及已提交纯本地人工回执、没有外部效果或关闭历史的 Case。源码冻结 `796b41ad8939ba1d067f84f137a4d2a1861f06d4`，独立开发分支 `dev/f2-case-cancel-after-receipt-20261011`，405 文件清单 SHA256 `cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5`。最终单窗38完整模块实际1560PASS/0FAIL/0ERROR/1既有WindowsSKIP、exit0，1561唯一ID，旧1391全部保留、新增170；首尾405源零漂移。结论仅此有限范围 LIMITED_PASS。

## 实际实现范围

`REQUEST_CANCEL` 独立记录明确请求并令 Case/local RECONCILING，同事务保存原事件；停止新派发和全部新履约业务写。企业另行 `RECONCILE` 全部历史人工 SUBMIT，精确 receipt/step UUID、版本、正文 SHA 和事件证明；结果为 KNOWN_LOCAL_RESULT 或 UNRESOLVED，仍 RECONCILING。最后另行 `CONFIRM_CANCEL`，绑定原请求及最新核对事件，只有完整最新结果全部 KNOWN 才原子收束到 CANCELLED。原 ACK、补正、重开和全部回执正文均保留，不自动替用户核对或终结。

三次动作都按当前 owner、租户及原 READ/PREPARE/EXECUTE、Case/资料/local/source 版本和明确理由/布尔确认执行。相同原键同参回放原事件、异参冲突；后续合法阶段仍可恢复旧请求及核对原键，另投影当前阶段。未知响应只 GET 原入口原键，不自动 POST。事件失败回滚状态及事件；所有历史世代重新证明，不依赖当前回执指针。

请求与 SUBMIT/原企业 ACK/换人/重接单/材料/方案采用/资源关联共 parent 锁，沿原 parent→dispatch→Case 顺序。真实 PG 双向等待覆盖七类合法 writer：请求先赢，晚写409且零业务副作用；writer 先赢，原来源 CAS 请求409。全部事实/材料/规划/交接/接单/receipt_parent/执行者_parent/legacy CREATE/交付/本地关闭重开入口服务端封锁，不能只靠页面。历史 GET 中 FOR UPDATE 不等于业务写；controlled/registered 计划读取与拒绝回调不隐式失效。

原成功 Run、资料、分派/步骤/提交/企业决定、资源关联/预约和容量保留，不伪造 WITHDRAW。Case 取消不释放资源；原独立 hold/group 释放按自身当前授权仍可执行，撤权则拒绝，释放与 Case 请求可以各自合法提交。旧 outbox、通知打开及迟到 UI/POST/GET 都重核阶段。页面三次明确确认，回执结果默认未选；取消说明明确资源需要独立释放。UNKNOWN 句柄冷恢复立即冻结写入口、最多8个/24h且没有正文/理由/核对结果/凭据；精确按动作所属 Case 拦截，不误拦其他 Case 或独立释放。

schema32 仅原 Case/local CHECK 加 RECONCILING、原 local event CHECK 加三动作，复用原表及 snapshot。现有 owned Linux fixture 原创建票据、当前 owner/transaction/table gate 保留；无新表、Grant、registry、角色或生产权限。原两个取消入口的首次接单前/从未 SUBMIT 限制保留。

## 根实际窗口，不能合并为一次结果

| 窗口 | 实际范围 | PASS | FAIL | ERROR | SKIP | 退出 | 进程秒 | 源漂移 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| first | 当时完整新后端模块12ID | 0 | 0 | 12 | 0 | 1 | 1.608 | 0 |
| second | 同完整模块12ID | 12 | 0 | 0 | 0 | 0 | 17.110 | 0 |
| third | 当时完整新后端与离线UI两模块 | 164 | 6 | 0 | 0 | 1 | 133.168 | 0 |
| fourth | 5完整模块 | 404 | 1 | 0 | 0 | 1 | 356.390 | 0 |
| fifth | 新后端/离线UI/旧lifecycle三完整模块 | 230 | 0 | 0 | 0 | 0 | 201.205 | 0 |
| sixth | 离线UI/旧controlled plans两完整模块 | 83 | 1 | 0 | 0 | 1 | 54.429 | 0 |
| schema-oracles | 13原版本相关节点，不是13完整模块 | 11 | 0 | 2 | 0 | 1 | 10.565 | 0 |
| schema-oracles-corrected | 修后3原节点 | 3 | 0 | 0 | 0 | 0 | 3.594 | 0 |

first 直接为缺失既有 preparation_fixture 导入，API尚未执行。third 六失败分别为测试夹具不存在 adapter_execution 列、错误预期能检测完全一致的无签名 owner 重写、非法计划前置条件两处、重复相同 REVALIDATE 已校验拒绝、NodeVM 缺原依赖；逐项修正测试，保留原产品门禁。容量测试现在通过原独立资源 API 构造61个真正不同的 REVALIDATE 来源，再验证62/63/64及全部原键冷恢复。fourth/sixth 旧 current schema31 oracle 与实际32不符；schema-oracles 两 setup ERROR 为已升级32的 fixture直接重放严格031。当前重放用032，专门历史031仍在原创建票据事务删32 marker后保留31断言，历史030同事务删31/32后 rollback；当前32、未来拒绝33，不减少权限、历史或回滚要求。

## 独立审查与真实反例

独审实施前冻结合同及全写入口/锁序静态审查，草案中两个 HIGH 与三个 MED 均在实际测试前修正。独立实际第四额外探针22PASS/2FAIL，原资源状态和1ms未来句柄时间 oracle 错误分别同 ID 2PASS复验，未伪称原窗通过。另有真实产品失败：冷 UNKNOWN 表单 capture1FAIL、既有 local 当前投影与事件不一致3FAIL、初始 cycle/state 完整重哈希未绑定原来源2FAIL；第五真实30探针单窗全部PASS，六旧失败同 ID通过。第五又发现按错误 Case 上下文拦截的4FAIL，第六修复。

第六独立完整新后端141 + 完整离线UI51 + 自有34，一窗 **226PASS/0FAIL/0ERROR/0SKIP，exit0**，进程186.994秒。其405源清单 `e103cb121d8396c7e566367705cbc44776e20feb66e325f96ca40dd2af81cb25` 首尾零漂移，10自有 probe 文件零漂移。原10个产品失败、两自身 oracle 失败均独立同 ID通过。该窗在源码提交前执行，不能改写成最终 cb47 清单窗口；独审逐字节比较确认最终与第六仅10个旧 schema 测试文件差异，产品 src/scripts/pyproject、新后端与离线模块/VM 不变，静态核对没有减少原授权/历史/rollback 断言。

原 standalone UNKNOWN capture Node exit1 单独保留，不虚构 JUnit ID；原 probe 字节、原命令修后独立 exit0，8个 form prevented/stopped均true，最终405清单前后零漂移。浏览器未启动。331 Python AST 文件和生产内联 JavaScript Node语法实际通过；JS SHA256 `ec80033d2700187db45c44f2733cecf09670631fb5df633f14685588b50fb199`。语法检查不代替交互或PG测试。

## 可复核原件与保留边界

所有原窗口 JUnit/stdout、命令/退出/时间/源码冻结、独审初始错误和修前源码/探针原件均保留于本环境 `.runtime/case-cancel-after-receipt/`。公开 [证据索引](evidence/case-cancel-after-receipt-20261011/README.md) 与脱敏 manifest 分别记录原字节和导出字节 SHA/大小、redaction类别、结果/身份/时间等价及无损 gzip；同 ID失败映射不覆盖原 FAIL/ERROR。已签收前两片149个公开归档文件逐字节保留，父审旧结论及旧缺口不改写。

历史 worker合法返回后 Case_count0 根因仍 **UNCONFIRMED**；原 stdout与持久状态缺失不能被本轮测试恢复，没有放宽旧短租约/跨租户/Case1门禁。旧初始39 API错误没有原 stderr，相关根因仍为推断，旧 atexit清理诊断保留。

浏览器 **NOT RUN、0次启动或替代重试**，历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 明确拒绝保持。Windows/native、全仓/全AT/完整生命周期、生产迁移/部署、真实模型/付费调用 **NOT RUN**。不支持取消后恢复、外部效果、已关闭或完整Case状态流；没有配置网络/凭据、强推或修改 protected分支。下一步父审按此有限合同及正常独立分支源码/实际原件限定签收。

## 最终完整窗与正常开发交付

最终38完整模块由原37完整argv加新后端模块组成，从干净工作区源码796b41启动于2026-10-11T15:29:49.846599Z，实际结束15:55:52.204847Z；进程1562.358秒、JUnit suite1560.155秒、pytest1560.20秒。**1560PASS/0FAIL/0ERROR/1WindowsSKIP，exit0**，1561唯一ID；旧1391无缺失，新增170。唯一skip是原 `test_native_windows_file_backend_gate`：Windows11 x64 reparse/ADS/ACL/clean lifecycle不在本环境。两个原Starlette弃用/XDG_RUNTIME_DIR警告保留，无atexit清理诊断。不是全仓/AT或Windows结论。

原完整JUnit SHA256 `77073956059174668caca9528dec3ac072f2d5c0bf37a6f34a89db8dd824f054`，原完整stdout `86925add0de4648e3a7a97acce1d04f334e131a96eacabe9b8f43259e8ec5106`。源码/AST/Node绑定及run记录都在249件冻结输入中。249原件3465991字节、导出3461260字节，本片无gzip；manifest SHA256 `6c24677c7a2b27c330d4da2b714f66561ec68ef44ecb962bccec42b413137096`。精确55静态白名单SHA256 `902d0e18361454d70f7d925b441e5b04d800917f7cd986ed28a66d1326435a96`；每件class及原/导出SHA明确，未知静态文件/hash或credential JSON key拒绝导出。34个实际FAIL/ERROR、34唯一ID全部保留原状态并映射到另窗同IDPASS，failure-map SHA256 `3a7c38d7e1fc68ea24b5d183486d532b1655d67138f93f7da918aabdab371a25`。原standalone Node不虚构JUnit ID。

独立归档审计在249冻结输入之外另附支持记录，原signed REVIEW签时根窗RUNNING保持不改；实际结束后的审计只补签此38范围与证据保存。正常开发交付commit和push后完整SHA、实际原origin各protected/accepted分支、当前独立分支HEAD远端0/0、工作区洁净、405源/249原件导出commit/旧149全集核验见本环境 `.runtime/case-cancel-after-receipt/delivery-after-push-verification.json`；必须以其真实完成结果为准，不将待完成push预写成功。

独立最终归档结论 [LIMITED_PASS](evidence/case-cancel-after-receipt-20261011/ARCHIVE_AUDIT.md)，没有剩余产品或归档阻断。18件后阶段支持在 [独立清单](evidence/case-cancel-after-receipt-20261011/audit-support-manifest.json) 中另存，交付核验也比较其原/导出/commit字节。两个扫描Oracle原exit1和修后exit0没有计作业务测试；报告组装库存断言原exit1另存解释与原工具stderr事后准确转录，原stdin文件NOT_CAPTURED、原命令/结果仅工具会话保留，明确不伪称进程原始捕获。签署后文档/helper新增支持导出与核验，405产品/测试源码及249原件均不变。


归档暂存完整 `git diff --cached --check` 实际退出2，66行保留证据空白（36行原pytest失败正文、30行原独审静态diff空上下文）；原日志/XML字节与hash保留，没有修剪或修改Git whitespace配置。排除原root/independent证据正文后的所有新写文档/helper/metadata检查实际退出0。完整原输出见 [cached-diff-check.json](evidence/case-cancel-after-receipt-20261011/cached-diff-check.json)，不把该失败检查称为PASS。
