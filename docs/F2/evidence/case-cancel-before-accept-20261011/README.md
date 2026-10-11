# 首次接单前取消 Case：可审计原始结果

本目录补足原交付 `f033bd38ade653eea295941dae8e12a12a44c133` 只有哈希汇总、父审无法取得原始结果的问题。产品及测试仍冻结于 `557528da70d905859d7fd09dc0b4ed8f5545af51`；这次只补充证据，没有新增业务、修改测试断言、删除测试或放宽权限。

`root/` 与 `independent/` 包含原始 JUnit、完整 stdout 的**脱敏副本**，包括失败窗口和修正后的独立窗口。它们不是未修改的原字节。`archive-manifest.json` 逐件记录原始 SHA256、导出 SHA256、脱敏类别与次数；大于 512KB 的重复内容使用无损 gzip，并另给解压内容 SHA256。原私有输入保持原字节，尚在指定保存环境 `.runtime/case-cancel/`，未覆盖或删失败。

脱敏限于执行绝对路径、临时认证局部变量/值、长不透明 fixture 字符串、Bearer/password/PG URI 与主机名。合成 Case/业务内容、测试标识、PASS/FAIL/ERROR/SKIP、持续时间、套件计数及异常结构保留。`build_archive.py` 仅用标准库，导出时逐一断言这些 JUnit 身份/结果未变化；父审可对 `.gz` 使用 Python `gzip.decompress` 读取。三份源码清单按原字节公开，不含认证数据。

## 原窗的 4 FAIL 与 39 ERROR

原窗 [完整 JUnit](root/final-affected.sanitized.xml) 为 **1271 项：1227 PASS / 4 FAIL / 39 ERROR / 1 SKIP**。原始 SHA256 是 `e630662b5faae1d140de31d5d65b2fdb45d4c2fdfa36b1d2b63888899b2749b4`；[完整 stdout](root/final-affected.sanitized.log) 原始 SHA256 是 `271eca66ff8908bac6b74bebcfec280451241bd044c4610059fd4eed2d2f34ed`。

[逐项映射](failure-map.json) 有全部 43 个测试标识、原状态、直接异常、根因证据等级、源码冻结和完整模块复验窗口。四类 FAIL 分别是：

1. 原测试仍重复 migration-029，但自有 fixture 已到 schema30；实际 SQL 与 `schema 28 prerequisite or retained schema 29 required` 拒绝完整保留。改为当前 migration-030 的原票据测试，迁移守卫仍拒绝无票据。
2. 原未来版本测试 INSERT30，与已有 schema30 重复；`UniqueViolation` 明确记录 version30。改为 INSERT31，继续验证原 migration-025 对未来版本的拒绝。
3. 模板历史 fixture 在采用计划后新增 Run assignments，遗漏已有依赖协议要求的显式局部 ADOPT；P3 正确返回409。原 e40 基线及当前源码均实际 FAIL，原 [基线 JUnit](root/template-baseline.sanitized.xml) 和 [当前原错流 JUnit](root/template-current-first.sanitized.xml) 保留。仅测试增加现有 ADOPT/CAS，依赖、权限、业务源码未改变；完整模板33项与独审额外原错流/保权历史2项通过。
4. 真实 wheel 构建子进程缺少 setuptools，原 JUnit 含直接 `ModuleNotFoundError: No module named 'setuptools'`。按原项目固定版本安装 setuptools80.9.0、wheel0.45.1，构建测试本身未改变。

39 个 ERROR 精确为 worker12项、authorization27项，全部发生在同一 API fixture 的启动阶段，直接异常是 `RuntimeError: API exited during start`，不是业务断言失败。pytest 的 `pythonpath=["src"]` 使进程内导入工作，原最小环境子进程不继承该 pytest 设置；未 editable 安装项目是共同根因判断，安装后两个完整模块的相同39标识均 PASS。

**证据限制：**这39个原子API的 `api.log` 没有被持久归档，旧 pytest-11 临时目录现在不存在。先前工具读取曾看到 `ModuleNotFoundError: parkweave`，但目前可取得的原 JUnit/stdout 只直接证明 API 启动退出。不能把缺失的39份 stderr 伪造成已经归档，也不能说每项各有直接 import traceback；逐项映射明确将这部分根因标作源码、环境和安装后复验支持的推断。实际完整最终窗口用于补齐该环境下的整体验证。

## 原源码与测试版本

原窗开始于 2026-10-11 11:50:51 UTC，首次功能提交4d在11:58:10 UTC。开始时是 e40 锚点上的未提交变更，不能标作已提交557528的一次原窗。原 [398路径冻结清单](final-source-manifest.json) SHA256 `53d8d0948bd082aee69443145d6646266583e92be6590d3ff49242f53218818e`；125个产品文件与最终557528逐字节相同。

两项事实测试在原窗已加载后修正文件，故 traceback 的 linecache 可显示新 migration030/INSERT31，而实际查询仍是029/INSERT30。归档保留这一不一致；原查询和异常优先作为实际运行证据。原 loaded facts 文件 SHA256 `d7acd56a10480aeda9af2a7f3d276e00e02894596310f1b69145a6786178e64c`；最终文件为 `8949b920570714ba12bd02dc9556ea0ab547b985b0951a070ca6a9dbe7a7d5f4`。

通过撤回最终文件的版本数字及注释修正，已重建 [原 loaded facts 文件](loaded-test-case-fact-clarifications.py.txt)，并强制核对其完整 SHA256 与原冻结清单 d7acd 完全一致。[精确修正 diff](loaded-facts-to-final.diff) 可直接复核哪些 Oracle 变化；这是匹配原冻结哈希的重建，不冒充另行保存的旧原文件。当前实际测试文件没有修改。

[修正事实测试后的清单](corrected-test-manifest.json) 与 [最终源码清单](final-delivery-source-manifest.json) 都保存原字节；二者唯一区别是必要的模板 fixture 显式ADOPT。最终398路径清单 SHA256 `5571352ab2d645d7739f4e727c2ba1188d169c919c3109bc263aec0c3592100b`。本补交不再改这些源码或测试。

## 完整原窗范围复验

完整复验已在同一指定环境、最终557528源码与已安装固定依赖下实际完成：**1270 PASS / 0 FAIL / 0 ERROR / 1 SKIP，进程退出0**，JUnit1185.519秒，进程1187.209秒。覆盖相同36个完整模块、1271个测试标识，逐一核对测试集合相同，运行前后398路径零漂移。[完整新 JUnit](root/full-final-recheck.sanitized.xml)、[完整新 stdout](root/full-final-recheck.sanitized.log)、[命令/依赖/时间/退出码](full-final-recheck-run.json) 均可读取。模块按名称排序，原与新 JUnit 都保留实际顺序；不声称 argv 或顺序完全相同。

原先分模块复验用于定位和验证修正，不能替代一次相同最终源码、已具备依赖环境的完整范围回归。本次实际完成这一完整窗，不再以“无需同环境完整窗重跑”作为交付理由。原窗仍是1227PASS/4FAIL/39ERROR/1SKIP，新窗另行记录，不改签旧结果。全部43个旧异常ID在新完整窗均PASS。

此前三个完整模块窗口为事实66PASS、模板33PASS、API/worker/授权/机会82PASS/1SKIP，逐项43旧异常都有相同标识的真实PASS。一个原生Windows测试按原条件SKIP，要求Windows11 x64 reparse/ADS/ACL及干净生命周期。全仓、完整原AT、真实浏览器、生产迁移/部署和真实模型仍NOT RUN；历史浏览器拒绝未重试。

## 清理诊断与安全边界

[安装后进程复验 stdout](root/installed-process-rerun.sanitized.log) 在82PASS/1SKIP测试摘要之后，保留 `pgserver` atexit 删除临时 `pg_wal` 的完整 `FileNotFoundError`；进程最终退出0。随后检查对应数据目录已不存在，无存活测试PG。未删除未知锁或进程，也没有把清理诊断从原输出删掉。新完整窗口的stdout未出现atexit清理诊断，两个原环境警告仍完整保留。

旧59件导出已冻结于 `archive-manifest-before-full.json`，SHA256 `8e6a34a30f00e0cb4fd342b9ad32c0db7a41029a453c861b25ecc38733a70246`。最终清单61件，只追加完整复验JUnit/stdout两件，旧输出与原始hash不变；交付后的远端SHA、保护分支和未提交/未推差异由最终报告核实。[旧59件及43ID独审报告](ORIGINAL_EVIDENCE_AUDIT.md) 保留其审查时新窗尚在运行的边界，新增两件另行最终核验。
