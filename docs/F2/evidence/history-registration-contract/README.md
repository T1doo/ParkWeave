# 纯登记合同候选证据

冻结源码：`55d1366373e949ffe3f621be98c8a5d13435750f`。父候选：`008ecdaf767eec4e5d1dc9e82074b2781c3502d8`。仅候选分支 `acceptance/history-registration-contract-20261011`，未接入生产 registry、loader 或 API。

本片验证默认关闭的显式合成声明/独立观察一致性；返回 MATCH/MISMATCH/UNKNOWN 数据分类，没有访问许可、持久信任根或完整退出恢复验收。输入标志和哈希不认证当前代际或维护隔离；无法区分的整体旧观察回放仍可能 MATCH，已保留此反例。

根验证：最终范围 196 项通过，包含新增纯合同合成测试 150 项和既有纯摘要测试 46 项。`root/scoped.log`、`root/scoped.xml` 为原始结果，`root/verification.json` 记录范围、源码文件摘要与各次运行，`root/manifest.json` 为证据文件摘要。初步 127 项通过日志仅反映补齐覆盖前的测试文件，不用来签最终源码。

扩大关联范围的两次运行各 251 项，均 250 通过/1 失败，原始结果完整保留在 `root/final.*`、`root/verified.*`。失败是未改动的 `tests/test_fact_history_read_source.py::test_exact_projection_no_values_or_proof_and_no_input_mutation`：它检查整数值文本 `17` 不出现在整个序列化输出中，随机十六进制 source_sha256 恰好包含 `17`，精确输出字段断言此前通过。本片没有修改旧测试/实现或反复重试取绿，不宣称扩大范围全绿。

原始失败日志/JUnit及独审副本保留 pytest 自带的尾随空白，因此全证据的 `git diff --check` 会报告这些空白；未为格式检查修改原始证据字节或其摘要。源码、测试、Markdown和JSON的格式检查通过。

运行没有启动 PostgreSQL、浏览器、网络 listener、业务模型或旧受限执行链。唯一 API 门检查使用进程内合成 TestClient 与拒绝 DB 访问的替身，默认工厂及传分类对象作 reader 都返回 403。既有 Starlette/httpx 弃用警告保留，未改依赖。

独立审查限定通过，无本片阻断缺陷；80项新建纯合成探针全部通过。报告、探针、原始日志/JUnit、关联限制及哈希清单已存入 `independent/`，复制前后逐项核验摘要。独审 manifest SHA256：`45083efe4f527c0829287677f8e5d60288613f4aec021a80fccb0d3b2aee4a02`。审查范围及旧测试限制见 `independent/REVIEW.md`。

仅审查通过后进行一次正常候选推送，不合并 dev/main。浏览器原 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 暂停不变；Windows/整页、持久登记及全 issuer/PG 完整重启不在本片验收范围。
