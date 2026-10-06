# ENG050：已授权首次新建CONFIG owner

父线程根据用户2026-10-06 12:14UTC答复统筹批准：只扩到Windows测试首次新建CONFIG的owner为当前运行用户，保留其他权限，验证成功才写正文。复用ENG047同一独占CREATE_NEW handle、TOKEN_USER、owner-only SetSecurityInfo、DACL字节/control核验与CRT转交；CONFIG入口仅接受该源码仓库绝对固定.runtime/windows-config.json，原session入口仍只允许原相对固定路径。不打开已有文件，不改ROOT、SID allowlist、身份/privilege或用户电脑；非CONFIG普通排他创建路径保留。

独立windows_native_review无阻断。创建、设置/检查失败不得移交正文，DACL变化/别的路径拒绝；提供原生独立临时树验证首次创建和既有字节保护的用例，执行仍SKIP/待Windows。最终定点139PASS/0FAIL/2WindowsSKIP/2既有WARN/14.23秒，见[evidence](evidence/eng050-config-owner-local.json)。Linux合同测试不等价实际Windows权限操作成功，native CONFIG/session各一项仍SKIP。

结合[ENG049](ENG049-RegressionTimingAndFixtureCleanup.md)同顺序耗时调查及独立fixture清理修复收拢后，获准普通推送dev/f1-foundation并只跑一次原标准CI；600/900、runner权限不变，不手动重跑。当前本地结果阶段，推送前实时比较remote，CI结果另行记载。预算0，R4关闭，F1/F2未签收、Win11验收NOT_RUN，原环境/包保留。
