# 原普通页面人工补证与同事项关闭／重开验证

基线 `e3be7e4de10fce1ff4fc988ffb878ec12694c660`，正常分支 `dev/f2-collaboration-dom-20261018`。最终受测冻结 **`a9c78345d6c25aa46d808fe975a6360f43a1b51c`**；生产src树 `74b5b08951ecbf5ea1f4b36eab91fb57386266a7` 与基线完全相同，tests树 `8224692fb52e2fd65cfa0157663f59b647ef9e12`。核原方案与已有实现后，补完整同对象DOM验收、共同测试函数和自有观测；修复回归中暴露的旧Node替身能力，不改业务算法／通用适配壳。[本片合同](OriginalCollaborationDOM-20261018.md)。

## 精确分窗，不拼全绿

| 窗口／冻结 | 实际结果 | 范围 |
| --- | --- | --- |
| 首窗 a54add455c41e81bd91df481e70cbc377826354c | 301唯一：282PASS／19FAIL／0ES；外层 994.287602 秒 | 14完整模块；新增4与原4个完整DOM节点均PASS；19旧Node页面失败 |
| 错误修补窗 e1d9502d8f1b3d176cc33f0676e7efbc26aad3ca | 27唯一：8PASS／19FAIL／0ES；外层 346.227418 秒 | 独审发现根代理复制constructor被截断；六语法检查均失败；原窗自然结束保留 |
| 最终有限复验 a9c78345d6c25aa46d808fe975a6360f43a1b51c | 27唯一：27PASS／0FES；外层 355.265677 秒 | 19个原失败节点＋8个完整DOM；未重跑整个301 |
| 同最终SHA独测 | 25PASS／0FES | 19原失败＋新增4与assigned2；全部逐ID重叠最终27，不加分 |

每窗759个src／tests／scripts／pyproject／四合同输入，在共享工作区和各自Git archive镜像PRE／POST均零漂移。首窗到最终冻结仅六旧JS替身和本片合同改变；src及所有Python测试模块原字节相同。最终pytest的87个parkweave模块实际从等字节镜像src导入；子API未另插import-origin探针。旧相对路径证据只写入各窗新镜像，不覆盖历史目录。独立最终静审无开放P1/P2。

**没有301项单窗全绿，也没有最终SHA完整301窗。** 301是首窗唯一范围，27／25都是其中重叠节点；不同SHA与开发窗不加总。首窗混合显式隔离API／Node fixture与普通DOM，不能称301个普通业务全链；旧template／approval fixture仅隔离回归，不能进入普通批准。

| 首窗完整模块 | 唯一 | PASS | FAIL |
| --- | ---: | ---: | ---: |
| `test_assigned_demo_chain_browser` | 2 | 2 | 0 |
| `test_case_feedback_cycle_browser` | 2 | 2 | 0 |
| `test_case_goal_results` | 44 | 44 | 0 |
| `test_case_lifecycle` | 41 | 41 | 0 |
| `test_demo_original_page_intake_browser` | 2 | 2 | 0 |
| `test_executor_receipts` | 38 | 38 | 0 |
| `test_manual_goal_collaboration_browser` | 2 | 2 | 0 |
| `test_manual_goal_privacy` | 11 | 11 | 0 |
| `test_manual_goal_recheck` | 45 | 39 | 6 |
| `test_manual_goal_reply` | 36 | 30 | 6 |
| `test_manual_goal_requests` | 25 | 24 | 1 |
| `test_manual_goal_tasks` | 15 | 14 | 1 |
| `test_manual_goal_tasks_late` | 4 | 0 | 4 |
| `test_partial_service_plan` | 34 | 33 | 1 |

[逐ID结算](evidence/original-collaboration-dom-20261018/runtime/accepted-tests.json)、[首窗原JUnit](evidence/original-collaboration-dom-20261018/runtime/final.xml)、[19原异常全文](evidence/original-collaboration-dom-20261018/runtime/first-window-original-failures.json)、[错误修补原JUnit](evidence/original-collaboration-dom-20261018/runtime/repair.xml)、[最终原JUnit](evidence/original-collaboration-dom-20261018/runtime/verified.xml)、[独测原review](evidence/original-collaboration-dom-20261018/runtime/independent-final-review.json)。

## 同一业务对象与持久回读

| 最终页面链 | 宽度 | Case | Run | plan |
| --- | ---: | --- | --- | --- |
| 人工补证 | 1200 | `095cabc4-7820-48e5-b0fc-93f26cc60348` | `31c140e5-8b6b-4420-b044-d3fd9bc9bad0` | `fca3d6cb-b049-4c81-af85-b803518bfc35` |
| 人工补证 | 320 | `5de5f397-586a-47c1-9932-1ac419d17362` | `a641df4a-79d4-4bfc-8fe2-c043abd1a979` | `80eb5256-5249-469f-a7f8-2556d4cf2b53` |
| 反馈／关闭重开 | 1200 | `9fd6c40b-4c0c-4b2e-95ae-434347decdd7` | `99ba3745-8856-4ce3-8d00-5198522c66f7` | `f798ab51-f898-4083-9df6-04422cb34475` |
| 反馈／关闭重开 | 320 | `d34903f0-d3f9-4cba-9fed-328eb86b877f` | `8d1535f4-5618-4940-93f0-06128de737da` | `a71a4525-b676-4f00-b9bc-cf42efc7701b` |

人工链先核零Run／Case／preparation／材料／assignment，只有显式既有SYNTHETIC身份／Grant／目录／资源。独立LOCAL worker及原普通configured_app页面创建事项，经诉求、两份USER_STATEMENT材料、REVIEW／CONFIRM、明确partial采纳／P1。七步REQUEST→TAKE→REQUEST_EVIDENCE→SUPPLY_EVIDENCE→TAKE→REPLY→ACKNOWLEDGE_REPLY经个人任务交接；补证／答复选择当前材料，知悉明确绑定原答复事件／fingerprint。逐阶段同对象、当前source SHA、材料完整性、current reply均核验。最终COORDINATION_ENDED仍PARTIAL／UNSUPPORTED，不证明真实性、阅读、外部批准、线下履约或Case目标完成。停首API／worker／浏览器后，新普通API和两个新角色上下文仅GET冷读，同账本、来源、材料、完整Case历史和权限快照保持。

另一链继续原assigned普通DOM P1–P5／六产物，**准备及精确Run assignment是普通进程启动前的SYNTHETIC fixture**。同Case／同step在原ACK后先REOPEN（直接纠错按钮禁用），原executor交v2、企业REQUEST_CHANGES、原executor交v3、企业ACK。P4核精确v3 ID／SHA／SUBMIT与ACK事件、actor和revision顺序。显式重验P4及cycle1 REVALIDATE／P5，再CLOSE_LOCAL_RECORD，P5需重验；明确REOPEN到cycle2清旧verified SHA且不可关闭，再REVALIDATE／P5。P5绑定原owner／cycle2事件及持久verified_snapshot，并独立canonical JSON重算SHA。旧材料、准备、派工、回执、生命周期历史保留，资源hold／claim／link／offer不自动释放；新普通API／浏览器仅GET冷读最终DTO及完整Case历史一致。

四个Case各自独立，每条链内部始终同一对象，不把多fixture拼成一条链。业务写入经原DOM，page.evaluate只观察；无JS应用导航或运行时授权修补。指定1200／320观察点无横向溢出，各链无pageerror。POST列表只枚举收到response的请求。见[最终实际对象／事件／SHA／child摘要](evidence/original-collaboration-dom-20261018/runtime/new-chain-actual-summary.json)及其原件路径；[首窗同链摘要](evidence/original-collaboration-dom-20261018/runtime/first-window-new-chain-actual-summary.json)独立保留。

## 两类失败原因与观测

首窗19失败涉及六个旧Element替身缺classList。原JUnit分别保留null读取、等待未达、断言和partial直接classList.remove栈；不能说19份栈都直接报同一TypeError。原同字节离线probe调用真实beginCaseWorklistEntry→clearPreparation→clearCaseCancellation，在零API调用／未替换生产函数下复现该TypeError，独审核调用链与请求停点。空stderr文件不能证明没异常：旧Python断言先read stderr，finally再次read可能已空；原JUnit中的首次异常保留。

根代理第一次复制现有stateful实现时错误截断于add方法，造成e1d六个constructor语法不闭合。独审拦下，六项node --check实际均失败；错误窗及原异常保留，未当通过。一次只读/proc所有权核验在cwd读取遇PermissionError，未发送SIGINT、未升级权限或重试，镜像窗自然结束。随后复制完整634字符constructor，六语法检查全通过，再冻结最终版本；业务／负例正文和请求／等待预算均未改变，不移除原私有清理。[离线原复现](evidence/original-collaboration-dom-20261018/runtime/offline-classlist-probe.stdout)、[独审拒绝错误修补](evidence/original-collaboration-dom-20261018/runtime/independent-rejected-repair-review.json)、[完整复制／语法核验](evidence/original-collaboration-dom-20261018/runtime/complete-syntax-check.json)。语法／probe不计pytest业务节点。

逐窗预置自有ordinary child逐次health／CPU／RSS／退出时序及自有PG连接、节点阶段、失败锁／blocking PID／数据库资源日志。首窗19失败均触发有界事后PG采样；采样当时空activity／locks不解释先前阻塞因果。最终16个普通child均ready并结束，观察到的成功测试连接均close。原连接2秒、DROP statement_timeout5000ms、ordinary启动循环15秒和health timeout15秒不变；事后诊断非新业务机会，不说整个清理硬15秒。无自动重跑；修改后的有限复验另窗列明。

**此前连接／DROP清理／ordinary启动底因仍UNKNOWN。** 前片主382仍381PASS＋同一节点setup／teardown共2ERROR，独首53PASS1FAIL／串行54PASS全部重叠。本片classList因果不能解释或抹去那些失败。旧403仍另一fixture身份拒绝的运输注入；旧overlap只旧回复先交付且80ms不是settled屏障，本片未触及其代码或扩大结论。[前片原证据](ReceiptSubmitRefreshFixValidation-20261018.md)。

开发WIP人工320的1PASS／1deselected及双链320的2PASS／2deselected，分别757／758输入零漂移，但随后补断言和helper，与冻结不同；不称测试pristine e3be，不加分。生产src均等最终树，[开发来源差异](evidence/original-collaboration-dom-20261018/runtime/development-provenance.json)保留。

## 证据、运行还缺输入与未验范围

继承32342个证据Git blob实际字节逐件核对零改动，未知锁未删。本片公开580对raw／public映射、47处临时合成会话候选脱敏；SHA／长度、严格JSON／JSONL／XML、PNG CRC／解压和383个JUnit标识实例保持。私有bootstrap／token及PGdata不导出；按原机制删除的PGdata不冒称保留。见[manifest](evidence/original-collaboration-dom-20261018/manifest.json)／[归档核验](evidence/original-collaboration-dom-20261018/archive-validation.json)。交付完整SHA和push／实际远端差异另存.runtime回执，避免自引用预写。

这两个普通DOM缺口在显式SYNTHETIC／LOCAL范围完成；正式AT07/12/15/35与真实业务未验。普通运行仍需已有当前合法会话／READ、PREPARE、REVIEW_ASSIGNED、精确preparation_catalog、原记录及executor的精确Run assignment。缺项原入口准确拒绝。未创建真实身份、Grant、分派、目录发布、批准或凭据。

正式专用backend／主体／原采纳映射仍需外部合同及专用代码：既有来源域／ID／版本／只读结构和获准样本；preparation／Case／Run／adopted-plan关系、版本／hash／current-head；原ADOPT决定／actor／状态／撤销及Run回执语义；已有主体映射和精确权限／用途／期限／撤销；公开trust／签名覆盖／独立验真协议。精确最小字段沿[来源合同](ReceiptSubmitRecovery-20261018.md)，不要发送token／私钥／密码／DSN。正式五证明UNAVAILABLE，NativeRunAccess permit／writer默认拒绝，资源批准只读不可消费，IsolatedPlanApproval不作普通批准。

Windows11原生安装／停启／关机、正式AT／AT35、真实来源／批准／园区业务／模型、生产受保护host、真实履约、效果与申报交付均未验；[原方案其余清单](ReceiptSubmitRefreshFixValidation-20261018.md)保持。无main修改、强推、部署、新费用／安全网络权限、真实模型调用、绕拒绝或未知进程操作。项目仍IN_PROGRESS。
