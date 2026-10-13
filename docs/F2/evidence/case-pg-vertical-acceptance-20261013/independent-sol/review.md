# 新只读归档审查 — 限定 PASS

审查模型 `gpt-6.1-sol`，推理强度 medium。本审查只读取现有源码、Git 对象、归档与运行原件，只在本审查目录写证据；没有网络请求、PG/CI/测试重跑，没有改源码、报告或执行分支。

当前验收清单 **36 文件 / 98,206 bytes**、候选清单 **69 文件 / 787,539 bytes**，所有 hash/bytes 及无遗漏核对通过。验收 root 与 independent-existing 导出逐字节等于各自原件；新增 stdout gzip 解压后也等于原件。候选首/次失败、独审启动失败及四份 gzip 原件无损保留。

实际 tool bundle 中 run 原响应、jobs、job 原日志与独立保存文件一致，摘要原行确实包含在 job 日志，解析结果完全一致。run `38341687876` / job `115113871538` success，number/attempt 均 1；精确 **27 PASS** 与另 **7 阶段 PASS** 分列。实际 checkout 为 b38，摘要 source 为 a52。原七项 PG 测试体从 catalog-only 基线到冻结源码没有变化，旧 NOT_RUN 归档未改签；analyzer 的正确 REFUSED 不被误写为全部预检成功。

source54b → parenta52 → execb38 的单父链成立；54b 到 a52 仅 docs，445 个冻结源码 hash 相同；a52 到 b38 仅 approval.json，剩余 444 个 hash 与当前工作树相同。主测435与旧独审444的 XML 全 PASS、重叠427、各自独有8/17均核对，未相加。首112/1与冻结434/1失败仍保留；过期 pending oracle 仍排除，diagnostic allowlist 失败同 ID 在最终两个窗口 PASS。

静态核验 PG15–PG24 共10项都要求实际 `pg_stat_activity` Lock 等待：取消先五项为取消200/对手409；ACCEPT先为ACCEPT200/取消409；材料/分派先提交为旧源取消409，更新源后取消200；方案/关联先为写入201、取消重核后200。报告准确区分这些语义。probe 控制流还约束逐阶段、setup/call/teardown、一次 session provider、19 次 app42501与 SELECT1 正控制、fixture 清理及 owned postmaster 正常整数exit0后移除 cluster。PG27同库桥接使用原 Case API并保留原Run成功事实。

**无阻断发现。限定PASS仅签现有归档、报告及其所描述的原单次27项子集**。host/IPC、全Case、OS/密码隔离、重启/崩溃恢复、浏览器、外部履约和生产范围仍未签。VM私有JUnit/SQL日志未取得；公开摘要、Actions日志与精确源码不能冒充每个断言的私有transcript。cluster清理不独立证明整个tmp root擦除或VM销毁。真实归档diff检查exit2及原stderr尾空格保留，报告检查exit0；旧模型审查仍为历史证据。

本结论基于当前报告hash及36项manifest快照（见 review.json/checks.json）。后续只需根侧将pending新审查字段改为完成、链接本新审查并重生清单；本审查不授权任何重跑或扩大范围。
