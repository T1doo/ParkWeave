# ENG061 本地字节完整性与固定拒绝原因

本轮只完成本地修复和复核；没有 push、dispatch 或 rerun。ENG060 的唯一 Windows run 总153秒、两个命令非timeout提前失败，不能写成预算耗尽。Windows严格身份拒绝的实际分支与回归入口实际根因仍未观测。

字节合同区分 Git HEAD blob 与工作树实际文件：manifest 使用 `read_bytes()` 的 SHA256，执行前要求实际HEAD符合显式绑定、所有test文件的HEAD blob SHA256符合manifest且工作树原始字节等于blob。不进行读文本换行转换或忽略CRLF。仅 `tests/*.py text eol=lf` 固定跨平台检出；原 `docs/sources/V1/*.md -text` 保留。manifest 的 producer parent 只表来源，不代替实际执行HEAD。AVAILABLE只表示实际HEAD与这组test原始字节已核验，不声明整个工作树无改动；其他被测源码仍保留原有私有hash。

严格Start/Stop拒绝仅新增固定stage/reason，最后一次身份拒绝及Start清理拒绝分开。原PID、creation time精度、完整命令/cwd、父子关系、60秒窗口、持有句柄与自有树边界保持；没有扩大查询/终止权利、孤儿发现或身份容差。已有主拒绝遇到CloseHandle失败时保留主原因，成功路径关闭失败仍拒绝。

acceptance入口按SOURCE_BINDING、INPUT_CONTRACT、ACCEPTANCE_BINDINGS、JOB_BUDGET、MANIFEST、REGRESSION_EXECUTION、REPORT_SUMMARY、REPORT_WRITE输出固定失败类。原子早期报告给出实际观测0例、coverage/full_regression false、四片NOT_RUN/PRECHECK_FAILED和非0退出；报告无法写入则安全stdout明确UNAVAILABLE，不能宣称已保存。已执行后发生报告失败时保留已有观测或明确UNAVAILABLE，不能编造0例。native与publisher验证固定字段和实际source binding，原8条/2KiB/16KiB/25ID公开边界保持，不输出私有路径、PID、ctime差值或异常正文。

独立终审另复现legacy非shard路径在pytest返回0但JUnit缺失时补空XML、宣称full_regression的问题；缺失或空JUnit必须固定REPORT_SUMMARY失败，保留非0原码、完整回归false且计数不可用。不能从命令返回0推断测试已执行。

本地 `core.autocrlf=true` 临时checkout正例要求工作树LF与HEAD blob一致；手动CRLF、单字节改动、伪造manifest hash、暂存区改动、错误/畸形HEAD、未入HEAD文件反例必须拒绝。它关闭已复现的默认CRLF检出问题，但不能反推ENG060的Windows根因。

沿用workflow固定manifest路径，刷新为51文件/1217实际collect-only用例，四片314/275/342/286；每片独立collection的稳定参数键与全量片内多重集合相同，原1162键全部保留。旧ENG057 baseline/collection明确移入历史字段，不拿旧hash或片数冒充新结果。collect-only不是1217项执行PASS，历史Linux相对权重也不是Windows时长预测。另修正既有真实stall测试的旧exact-dict oracle：phase/id独立比较，并继续核验telemetry采集数与脱敏；生产progress代码未修改。

下一次获授权的CI可验证固定LF检出及实际HEAD/test字节合同，并从固定原因区分manifest/hash、bindings读取/校验、截止检查、源码绑定与报告写入；身份stage/reason可定位严格拒绝的分支。该本地结果不能排除Windows API/psutil句柄兼容性问题，也没有补齐四片实际耗时、完整覆盖、四个原生Job oracle或Win11签收。1500秒总cap、200秒尾部、每片600、权限、R4关闭、真实模型预算0保持。原环境与备份保留。

最终本地验证、独立复核与冻结hash见 [ENG061证据](evidence/eng061-local-integrity.json)。

最终17文件统一424PASS/2nativeSKIP/2loopback明确排除/1既有WARN，19.23秒；独立重要反例39PASS/0.87秒、NO_BLOCKERS。代码本地提交 `5151e8452e4e833025538c5a7f324ccb3e574c20`。对该真实仓库提交作本地 `core.autocrlf=true` checkout：51/51 test原始字节等于HEAD blob与manifest，0个CRLF；手动CRLF拒绝GIT_BLOB_MISMATCH，恢复后通过；两份Library Markdown原始字节保持。该证明是Linux上的实际Git checkout，不冒充原生Windows运行。
