# ENG101 事实用途联调检查点（未验收、未推送）

核心外线 `8d9e881f1d64042d6a7dfedf0d96c00e943c7a08` 已获取并在独立工作树以 `263dd05` 集成。合同基线为已公开 `686f3e1f93eed03a31915df5eac6b99da3ad7f0a`。此检查点保存可审阅适配，不宣称产品完成。

本线加入正式 Store schema25 loader/package 与原 API 三个事实用途入口，准备核对/确认和 readiness、resource/P1、分派/回执、local/P5 当前事实门禁；普通未声明 Case 保持原指纹形状。声明历史存在而 ledger NULL 时仍拒绝失效账本，不能退回 legacy。专用 GET 本人来源、通用准备只公开状态/hash，后端不用本人 token 代替其他角色。

网页按实际 GET 的 state/revision/necessary_questions/history 显示三项来源与不可自动选择的证据。显式声明、用途/三项选择、当前版本/sourceSHA、不可改的原参数/键未知结果恢复、刷新/迟响应与身份清理均已静态检查。GET 403 与未知 POST 重试 403 清私密显示且保留原键参数，不推断原 POST 未提交。追加来源仅调用既有 POST /api/facts，固定 SYNTHETIC/SERVICE_PREPARATION，本人明确值、编号、版本、摘录及 UTC 有效期；不替代旧断言、不新增授权/模型调用。浏览器脚本已准备，**NOT_RUN**。

独立 API 首轮20项 **15 PASS / 5 FAIL / 0 ERROR / 0 SKIP / 2 WARN，15.57秒**。NULL末断言先错误禁止原步骤协调允许保存的 invalidated 观察标记，修正后单案 **1 PASS / 19 DESELECTED，2.16秒**；仍严格校验原prepRev/事件/材料与全部下游业务记录不变。剩余四项真实失败涉及 field READ/WRITE 与 capability READ/EXECUTE：撤销后恢复授权，旧用途错误恢复 CURRENT。核心 _sources 只摘要 binding/sources，没有纳入授权 revision。必须由独占核心作者修复源摘要的稳定授权行修订绑定，保留当前来源与原权限复核，不弱化测试。

三文件实际兼容回归 **116 PASS / 2 FAIL / 118 TOTAL / 2 WARN，33.34秒**。外部 migration025 回滚测试假定基础fixture24，正式 Store loader 已迁25，所以测试回滚后仍25；需作者为回滚测试明确建立schema24测试起点，不能简单把预期24改25并假称证明DDL撤销。另一个材料复用测试业务均通过，末尾旧schema24断言由本线更新25，并同步其余现行版本断言；旧版本起点和业务历史断言不改。

外部三个核心文件未被本线改写。已失败日志/JUnit保留在 /tmp/eng101-fact-integration-first.*、/tmp/eng101-fact-null-gate.*、/tmp/eng101-facts-preparation-reuse-regression.*。完整 Linux、事实UI浏览器、最终事实业务推送及其CI均NOT_RUN；不得将外部118或当前116通过称为完整联调验收。隔离 UUID 测试库均按原fixture清理，不涉及原环境/备份、真实身份/Grant/Run assignment安全策略、main merge/deploy、外部履约。F1未签收/F2并行、Server非Win11、正式AT/EX未跑、R4关闭/预算0。


## 现行升级边界的真实阻塞

仅更新现行 schema25 断言后的11项旧升级/权限历史专项实际 **9 PASS / 2 FAIL / 0 ERROR / 0 SKIP / 2 WARN，4.90秒**，日志 `/tmp/eng101-schema25-selected-regression.*`。外部迁移明确只允许 `fixture_<32hexUUID>`。旧升级测试创建的 `upgrade_UUID` 是新隔离测试库，本线可将其初始名称规范为受支持 fixture UUID；但既有生命周期诊断严格限定 loopback `parkweave` 数据库，与外部迁移 guard 不兼容。此项是接线边界的实际阻塞，不能改安全策略或放宽 guard 获得假通过，也不能绕过 migration25 伪称完整回归。当前既有 Store loader 25 适配因此只在支持的 UUID fixture 检查点成立，原 lifecycle 未验收且不发布为完成集成。需先明确候选安装/正式生命周期兼容合同。


旧 legacy001 升级起点规范为 `fixture_UUID` 后，原业务保留断言与重复升级均通过；旧未来版本哨兵仍用25导致重号，按原拒绝未来版本语义改为26。最终单项 **1 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，0.86秒**，日志 `/tmp/eng101-legacy-upgrade-final.*`，log SHA256 `923441902dfa2ec5c6cb0fc9661af1a5b6b6a0d297075da0a559a4b9f94a11c7`，JUnit SHA256 `62e81f9c4ff56fad4aee6fa2b4f22d3567e470bac57e00bb59c15b3416d51e8a`。此前失败均保留；不将单案复跑拼算成11项或118项整套通过。生命周期固定库名边界和外部核心四项Grant恢复失败/rollback起点仍未解决。
