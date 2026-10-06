# ENG066 精确 argv0 与安全失败映射本地修复

本地代码 `649803f8253dc4b9f7a34d1c7f4a2e40fbd8ae5b`，基于 `aa8fd4d`；独立终审 **NO_BLOCKERS**。本轮不 push、不启动新 CI、不 merge main/deploy，不改身份、代理、权限策略、runner、Job预算或清理合同；真实模型调用/预算0，原环境及恢复备份保留。

最后实际 Windows 结果仍为[ENG065 唯一 run](https://github.com/T1doo/ParkWeave/actions/runs/37498631767)：1160 PASS／42 FAIL／51 SKIP。它确认 CHILD_POLICY/ARGV0_MISMATCH，但没有输出原始 executable/path 或命令尾；以下为受控本地修复，不能改写实际42 FAIL，也不能还原此前省略的16个函数ID。

## 指定 venv 的单一合法转发路径

[CPython3.12 redirector](https://github.com/python/cpython/blob/v3.12.0/PC/launcher.c) 从 pyvenv.cfg 的 home 组装 base python.exe 并保留命令尾；[getpath](https://github.com/python/cpython/blob/v3.12.0/Modules/getpath.py)支持与运行时 base executable 交叉核对。受控前例在旧完整argv相等合同下拒绝 ARGV0_MISMATCH；同一受控输入经本轮绑定接受 DIRECT_CHILD。

新增单一 authority 仅来自当前运行的 managed venv：sys.executable/prefix 必须对应本项目，base_prefix/_base_executable 必须绝对、存在、非managed且定位其base目录，并与有界8KiB pyvenv.cfg home/可选executable一致。候选 argv0、PATH、health PID都不能提供authority，不启动额外探测解释器，也不接受其他目录同名python.exe。root trusted command保持；child完整尾、cwd、直接父子、60秒窗口、kernel10µs、held pins/borrowed ownership及重复快照保持，实际进程exe镜像也必须与单一target匹配。私有child record保存实际完整base命令与launcher命令，Stop重新导出authority/整记录并验两个pin后才能signal；漂移负例无signal。

负例覆盖其他路径同名exe、相对/缺失/非文件target、prefix/cfg冲突或重复home、image/argv0不符、tail改/增/缺、cwd/父链/时间窗口、动态NaN/inf/非法type和authority漂移。真实Windows目标路径仍未知；若其不满足指定合法形态继续拒绝，不忽略argv0。

## 四个公开 failure ID 的定点处理

| 公开去参数 ID | 本地处理／结果 | 原生结论 |
| --- | --- | --- |
| test_lifecycle_diagnostics::test_real_loopback_refusal_and_occupied_port_are_distinct | Windows probe在bind前设SO_EXCLUSIVEADDRUSE；调用序列注入及同身份真实Linux loopback PASS。[Microsoft文档](https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse)说明默认绑定与exclusive区别。 | OPEN；Linux不能证明实际Windows断言原因。 |
| test_owned_job::test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary | Windows-only两个参数在本环境SKIP；已有Job注入合同PASS，生产Job与2s/5s oracle预算不改。 | OPEN；外层OWNED_TREE_STOPPED不能代替专项的descendant/unrelated/primary oracle。 |
| test_regression_shards::test_actual_expired_coordinator_persists_all_not_run_without_launch | fixture用as_posix生成canonical tests/test_*.py。Windows反斜线在严格manifest前置拒绝的受控前例见ENG065证据；当前定点PASS。 | OPEN；不把S1的35FAIL全部归因于这一fixture。 |
| test_regression_shards::test_each_shard_exports_actual_counts_invocation_cost_and_cleanup | 同共享fixture修复，定点PASS；production manifest path合同不放宽。 | OPEN；不改历史四片实测。 |

## 安全 mapping 和完整发布链

原mapping在去参数前检查name长度，合法长参数落unknown；现先去参数，再精确白名单匹配函数，所有已知失败按函数count聚合，未知保留unknown。仍最多25 producer IDs；超过时记录mapped_cases_omitted，不伪称全部函数可见。publisher严格验证known/unknown/omitted守恒。

原fullreg单notice为了容纳计时信息先删IDs，实际20个投影ID仅4个可见。现先保留4片及case rows、省略重型timing observation并标记，再用已有空闲槽位续页整ID及同序整数counts；主notice记录mapped总数、producer及annotation省略。固定case_ids kind贯通native publication_capture，依然重新生成整批逐字节比对，坏kind/截尾拒绝。预留最终false比true多1字节，连续300字节边界扫描通过。8条／每条完整UTF8+LF 2048字节／总16KiB／全局25 ID出现次数不变，极端长ID容量不够仍明确省略。

ENG065形状的6 case rows、4片、20个合成已知函数ID、42个失败case重放，8 notices保留全部20 ID/counts且0省略，并经实际capture完整接受。这是完整链合同复现，合成IDs不冒充以前未公开的16个ID；实际3 unknown也未擅自归零。

## 验证和边界

最终11文件347 PASS／6原生SKIP／2隔离deselected／1既有warning，15.33秒。同身份临时本地数据库及loopback流程109 PASS／40.51秒；关闭重开及双角色确认另62 PASS／24.15秒，两组不重叠。独立审查245 PASS／5.33秒，最后边界/capture 2 PASS／.25秒，NO_BLOCKERS；与主测试重叠，不累加成绩。compileall和diffcheck通过。

collection1283，51文件，四片342/307/347/287，604白名单函数；四片stable multiset与global相同，旧1253 exact case keys全部保留。collection不是1283 PASS。提交后51 test blobs和26 implementation blobs SHA256分别等于manifest与工作树raw bytes，原文件mode不变。

实际Windows身份/端口断言、四个专项native Job oracle、未公开原失败断言及新全量结果仍OPEN。本轮没有新的Windows测量；F1未签收、F2仅并行探索、Server不是Win11、R4关闭，不自动资格判断或外部履约。固定证据见[ENG066 JSON](evidence/eng066-targeted-local-repairs.json)。
