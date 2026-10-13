# 第二次 Linux 单轮入口独立审查

结论：**LIMITED_PASS；未发现本次新授权执行的代码 blocker**。只签代码与纯契约，不签物理 VM、UID/ACL、PG 或 17 项实际验收 PASS。parent 转达的新批准为 2026-10-13 01:14:56 UTC；我未另行读取消息来源，审查将该转达作为授权上下文。

冻结源码：`4649970278e29b999a2a4f332ba7380f20795a3f`；基底：`80ac6c86edd447d31e5f046b25eb335c63923102`。

| 审查项 | 结果 | 证据与范围 |
| --- | --- | --- |
| 精确五文件范围 | PASS | diff 与独立静态探针一致 |
| 新 workflow 独立分支/唯一 repo/public/push | PASS | 精确结构比对旧已审 workflow，仅新增分支、入口与独立并发组 |
| first run_number=1 且 attempt=1 | PASS | workflow 与 bootstrap 双层门；反例通过 |
| ubuntu-24.04、单 job、25/23 分钟 | PASS | 静态 workflow；无矩阵、dispatch、artifact/cache、secret 或额外 service |
| 新批准与第二入口不 cross-pair | PASS | 实际 Controller.run 四种交叉组合均在 actions 前拒绝 |
| 实际 main 路由与拒绝 beforeFS | PASS | 8 种拒绝，及正确新路由到精确 checkout 的合成反例 |
| 旧批准函数及 workflow | PASS | 原函数 AST、旧 workflow 字节完全一致 |
| src、worker SQL、既有 docs/evidence | PASS | src/docs 无差异，worker 整文件原字节一致 |
| fresh VM/目录/identities/IPC/PG、保护源与解释器 | PASS（静态） | 新标准 hosted job；原 fresh 创建及 root 保护实现保留；无物理执行 |
| 凭据私密渠道及原 guard | PASS（代码/纯 DI） | env 清空、sealed input/私有管道、root 私有日志、闭集公开投影保留 |
| 冻结完整性 | PASS | 6115 个 git tracked 文件前后 SHA256 零漂移；HEAD 一致 |
| 物理 trial 及 cloud 状态 | NOT_RUN | 未推送/触发/重试/提权/建库/改 ACL/启动浏览器；未读取凭据 |

独立窗口实测 **251 PASS / 0 FAIL / 0 ERROR / 0 SKIP**；其中 **236** 与 root 冻结主测完全重叠，另 **15** 项独立探针，计数不可与主测相加。一个现有 Starlette/httpx 弃用警告，不是跳过或失败。rawstdout.log 与 results.xml 原字节仅本地保留，XML 含超长合成参数；可复制 `testcase-projection.json` 中静态名/结果/ID 哈希，不能把该投影称作原 XML。

历史真实 trial 仍为 **3 PASS / 1 FAIL / 13 NOT_RUN**。旧 `ACTUAL_ROLE_ACL` 宽标签不证明 SQL 权限原因；本次未修 SQL，未反向推断旧失败。新物理执行结果仍未知。动态依赖安装、hosted runner 可用性与实际底层行为只能在已授权的新 VM 内观察，不构成纯审查可保证的成功。

可按 parent 转达的第二次新授权，对上述精确冻结源码，经唯一新分支 `dev/f2-restricted-linux-second-trial-20261013` 正常 push 启动一轮新的标准 VM；不允许旧许可重用、旧失败 rerun 或后续自动重试。相关历史被拒绝 repo GET、旧 runs 集合 UNKNOWN 和浏览器拒绝均未重试。此签署不是云运行完成证明。

证据：`run.json`、`static-boundaries.json`、`source-before.json`、`source-after.json`、`testcase-projection.json`、`test_independent_second_entry.py`、`evidence-manifest.json`；原始文件散列见 run/projection/manifest。只有 `safe-copy-list.json` 明列文件适合后续普通文档证据复制；原始 XML/stdout 与临时文件不在该列表内。
