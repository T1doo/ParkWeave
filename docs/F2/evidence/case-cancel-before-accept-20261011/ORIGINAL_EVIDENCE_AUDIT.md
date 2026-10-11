# 原始证据与脱敏归档独审

结论：**LIMITED_PASS**，限定于当前已完成的原始窗口、逐测试复验关联和冻结归档；不声明正在运行的完整新窗通过。本轮只读源码、Git、日志、JUnit 和归档，不运行新业务/PG/ASGI 测试，不接触父任务数据库，不改产品、测试或 Git，不启动浏览器。

当前产品与测试源码 SHA 为 `557528da70d905859d7fd09dc0b4ed8f5545af51`，读到的交付 HEAD 为 `f033bd38ade653eea295941dae8e12a12a44c133`。398 路径清单 SHA256 为 `5571352ab2d645d7739f4e727c2ba1188d169c919c3109bc263aec0c3592100b`；工作区与清单零漂移，交付 HEAD 和源码 SHA 在这 398 路径上字节相同。

`final-affected.xml` 保留全部 1271 个唯一 testcase：1227 PASS、4 FAIL、39 ERROR、1 SKIP，JUnit 1029.069 秒。对应 log 末尾计数一致。原窗口不改签；43 个坏测试 ID 与原异常文本/属性哈希及后续同 ID 结果逐项列在 `original-evidence-audit.json`。

| 原始组 | 实际异常与根因证据 | 原始数量 | 后续完整模块窗口 |
| --- | --- | ---: | --- |
| 事实固定名迁移 Oracle | 运行旧 migration-029 时 schema 已 30，原异常为 `schema 28 prerequisite or retained schema 29 required`；改为当前 030 的重复票据迁移，保留 commit/rollback/票据不泄漏约束 | 1 FAIL | final-facts：66 PASS |
| 事实未来版本 Oracle | 原运行 INSERT(30)，实际 UniqueViolation：version 30 已存在；改为 future 31 后继续验证 migration-025 拒未来 | 1 FAIL | final-facts：66 PASS |
| 模板错流 | 先 ADOPT 后新增两条现有 Run assignment，P3/P4 的 access source 已变，原 P3 VERIFY 409；基线与当前原同例都失败，独立错流也已真实复现；使用现有显式 local_revision/CAS，不放宽权限/自动重绑 | 1 FAIL | template-current-corrected：33 PASS；既有独立 template-followup：35 PASS |
| wheel 构建依赖 | 原子进程直接 `ModuleNotFoundError: No module named 'setuptools'`；既有 pyproject 与该测试要求 setuptools 80.9.0，安装日志保存该版本与 wheel 0.45.1 | 1 FAIL | installed-process-rerun：完整 worker/auth/opportunity 82 PASS、1 原 native SKIP |
| 子 API 启动 | 原 RuntimeError：API exited during start，发生在 runtime fixture setup；12 worker + 27 authorization。具体 missing editable-installed parkweave 属于下述受限推断 | 39 ERROR | installed-process-rerun：同 39 ID 均真实 PASS |

事实测试原失败正文存在可解释的 frame/query 矛盾：渲染源代码行显示新 030/31，而运行时 query/异常仍是旧 029/INSERT30。原窗口导入后文件被修订，linecache 渲染当前文件。原文件 SHA `d7acd56a10480aeda9af2a7f3d276e00e02894596310f1b69145a6786178e64c`，当前 SHA `8949b920570714ba12bd02dc9556ea0ab547b985b0951a070ca6a9dbe7a7d5f4`。原 125 个产品源码路径哈希全部与最终相同。不能仅据渲染 source frame 认定执行了新 SQL，也不能把原运行时 baseline Git HEAD e40 当作取消功能源码提交。

39 项 ERROR 的直接原始证据仅支持 API 退出。`tests/test_worker_gateway.py` 的 fixture 将子进程 stdout/stderr 写入临时 api.log；39 个原路径均已不存在，原 log/JUnit 没保存具体 ModuleNotFoundError traceback。minimal_environment 明确剔除 PYTHONPATH，src layout 的子 API 需要已安装项目；现有 editable 安装日志和随后同 ID 的真实 PASS 支持缺 installed project 的根因推断。必须保留“推断”与“原 stderr 未持久化”限制，不能补造 traceback，也不能用新成功窗假称恢复旧 stderr。

冻结归档 `docs/F2/evidence/case-cancel-before-accept-20261011/`，archive-manifest 与 archive-manifest-before-full 字节相同，SHA256 `8e6a34a30f00e0cb4fd342b9ad32c0db7a41029a453c861b25ecc38733a70246`，共 59 件。逐件原 hash、实际导出文件 hash、gzip 解压 payload hash与字节数均匹配。全部 JUnit testcase 所有属性（含 classname/name/time）和原 FAIL/ERROR/SKIP/PASS 均相同，suite 除披露脱敏的 hostname 外所有属性相同。披露 builder 的正文/属性脱敏结果和每类计数可完整复现。final-affected 的完整 XML 保持明文。

对全部日志与 JUnit 异常/输出/skip 正文及属性扫描，导出副本中的完整夹具 auth 值、Bearer 长凭据、PG URI、password 值、quoted 长不透明值和绝对执行路径候选均为零。扫描只报告候选计数，不暴露原值；Regex/context 扫描不能证明任意明文都不含秘密。脱敏应只改披露的副本：保持原私有输入、保存原/导出及解压内容 hash，以明确占位符替换完整/截断 fixture token、URI/password 与绝对执行路径；不得改变 testcase ID、计数、耗时、结果、异常类型、关键 SQL/HTTP 错误、参数化用例标签。公开源码清单中的相对路径与 SHA 哈希不是凭据，应保留。

installed-process-rerun.log 中 pytest 的 82 PASS/1 SKIP 后还保留 `Exception ignored in atexit callback`：PostgresServer._cleanup/shutil.rmtree 的 FileNotFoundError（临时 pg_wal 已不存在）。该异常发生在测试总结之后，不属于 JUnit testcase 结果；父任务记录该进程退出 0。原文与脱敏归档均保留，不能删除为干净成功日志。

跨窗口覆盖矩阵的 1271 个 ID 集合与旧原窗完全相同，得到 1270 PASS/1 SKIP，且与父任务 current-coverage-index 逐项一致。这是原窗加三个完整模块复验后的覆盖矩阵，**不是一次完整窗口全 PASS**。本轮审查时新的 36 模块完整 recheck 未完成，因此不签收该新窗；完成后需追加其原始 log/JUnit、保持旧 59 件不变，再审完整 ID/结果与敏感值。

后续事项：完成新完整窗并归档；保留 39 项 stderr 缺失这一不可恢复证据限制；归档新清单、压缩或新增文件后重新核验。产品切片原 LIMITED_PASS 结论不变，本轮未发现产品/测试源码漂移或归档身份结果篡改。

公开说明复核：failure-map.json 的43唯一ID、原状态、复验窗口/结果和原JUnit hash均与独审一致，C5明确标INFERRED并披露旧stderr缺失，新完整窗明确RUNNING。README的原事实linecache限制、未持久stderr限制、旧59冻结与新窗待完成表述准确。先前工具观察是父任务的未持久化归因，本审查不把它当已保存raw traceback。清理段建议把“退出0后”写为“测试摘要之后，进程最终退出0”，以准确表达atexit时序。

旧事实源码补证：loaded-test-case-fact-clarifications.py.txt 的完整 SHA256 精确匹配原冻结 d7acd；loaded-facts-to-final.diff 完全等于对重建旧 bytes 与实际最终 tests 文件生成的 unified diff。独立 AST 核验只变化六个指定 Oracle 常量（3处029→030脚本、1处当前schema29→30断言、1处future INSERT30→31、1处future schema30→31断言），其余 AST完全相同，另有说明注释修正。原真实创建票据、无票据拒绝、固定当前库名、commit/rollback票据不泄漏、票据重新发出、未来版本拒绝和 business快照保持逻辑均保留。README准确披露这是匹配旧冻结哈希的重建，不冒充旧原文件另存；当前产品/tests字节仍冻结。父任务也已修正README中的atexit时序表述。
