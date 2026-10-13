# Git stderr封闭与仅准备入口候选交付

冻结源码与精确范围清单 **b821729a79db4bb36c1bfd38fd79caf46eab2a25**，正常独立分支 `dev/f2-prepare-only-candidate-20261013`，基于上轮交付8de739c9c0505fee43d8766047e2653a4ad2361f。后续仅追加本报告和公开离线证据；最终候选完整HEAD以正常push远端核对及交付响应为准，下一次批准必须绑定该完整候选HEAD。

修复原bootstrap源码复制 `git show` 的stderr继承：现显式stderr=PIPE，全部Git核验/复制stderr均捕获。没有过去泄密证据，本轮不声称查明旧失败根因。新测试在真实prepare控制流的Git失败点注入含合成敏感串的CalledProcessError/argv/stderr；若stderr未捕获则模拟污染公开stderr，实际输出无污染且只包含封闭B_SOURCE_COPY诊断，未投影异常消息/路径/argv/stderr。

新入口prepare_once.py只复用prepare并运行固定纯导入，不启动完整controller或业务流程。独立pending approval、独立新branch/ref/claim、精确Git父子链及单文件激活差异，不能复用已耗用的旧一次授权。新工作流只接受新执行branch的approval路径push和run_number/attempt=1；候选branch不触发。当前原/new两个approval均false/null/null，没有创建激活commit、执行branch或实际运行入口/CI。

[精确资源与下次批准范围](PrepareOnlyTrialApproval-20261013.md)逐项说明本次新T和一次claim、root ownership/chmod、官方运行时副本、锁定19wheel下载/离线安装、无敏感数据固定纯导入、成功删T但保留claim、失败保留尚存私有T、后删除timer失败保留实际清理事实、480s主窗口+60s清理/日志窗口、10min step/12min job。此实现**仍包含新副本的root所有权/权限保护动作**，当前仅离线验证，须先完成精确范围复核并取得对此完整候选SHA的一次明确批准；不将其误归为无安全权限变化的普通导入测试。

根最终相关纯测 **255 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（新prepare48+旧207）；独审最终 **58 PASS / 0 FAIL / 0 ERROR / 0 SKIP**（48与根重叠，另10独立负测），不合并计数。测试是DI/虚拟目录、子进程与FD，物理OS/SQL/网络/随机凭据操作由guard拒绝，未运行真实准备入口或CI。源码行为测试通过后只修了源码注释和清单表述，未改行为。

原始失败窗口保留：root-first命令使用不存在的测试文件名，pytest收集前ERROR，零测试；root-second **246 PASS / 1 FAIL**，新测试函数尚未同步诊断allowlist的精确一致性检查失败；同步allowlist后root-reviewed255PASS。这两次失败均保留原日志/JUnit，不用最终PASS覆盖。独审指出的清理措辞问题只修文档，准确区分清理前失败和确认删除后的timer失败。旧actual run38373923111仍 **1 PASS / 1 FAIL / 19 NOT_RUN、cleanup=false、根因UNKNOWN_NOT_PUBLIC**，不回填诊断或重跑。

公开证据仅纯测试/合成敏感串/源码hash/只读范围审查，无真实VM私有日志或凭据；原件按独审safe-copy-list逐bytes/SHA256归档到 `docs/F2/evidence/prepare-only-candidate-20261013/`，包括失败窗口。冻结证明已归档；最后归档收尾审查不递归归档，仅保留在runtime。独审首次freeze脚本误假定存在本地main ref而只有origin/main，原失败也保留，改为正确只读ref后通过。

本次候选交付无生产部署/迁移、模型/付费调用、真实PG、用户/组创建、凭据配置、安全权限动作、浏览器尝试、强推或旧CI重跑。main/F1/F2与旧候选/执行/报告/上轮bootstrap交付branch均保持原SHA。源码diff --check通过；证据暂存diff --check实际FAIL（rc2），只因root-second原失败日志/JUnit中pytest生成的四处trailing whitespace；为逐字节保留失败原件不裁剪，原检查输出留runtime。工作区和新远端SHA最终一致性由收尾核对给出。

剩余：先复核本精确范围，决定该一次保护准备探针的合法批准路径；目前真实准备和导入 **NOT RUN**，也不能证明原11秒失败准确原因。若准备成功，host→业务Case取消21项真实组合验收仍是另一个独立范围，尚未完成本次验收。
