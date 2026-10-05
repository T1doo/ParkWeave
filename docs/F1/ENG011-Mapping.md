# ENG011 R3冻结

基线d395fc1856b350fa1d4256563f0731a6b27b3687。仅现有region/employees/service_need的结构化合成候选projection及集中必要问题，正常facts.assess请求/worker路径；不做任意文档解析、资格引擎、F2或Windows候选启用。

来源为显式SYNTHETIC摘录与版本，区分USER_STATEMENT、DOCUMENT_EVIDENCE、OFFLINE_MOCK_MODEL候选；均UNVERIFIED。模型候选不写已核实事实、不覆盖现有fact_assertions。冲突/缺失/过期/未核实全部UNKNOWN，qualification NOT_EVALUATED。既有非候选assessment历史语义保留。

immutable review快照/hash与Run终态/outbox同事务；当前owner/scope/字段READ-WRITE交集、fence/control重验。统一必要问题按三个字段一次列出。带父review hash的澄清回填创建新Run及不可变followup链接，旧review/来源版本保留；cancel只取消本次回填，不修改旧事实/Run。重复键幂等、冲突键拒绝、旧worker拒绝，事务中断恢复。HTTP/API/PG/真实CLI独立oracle、合成Mock、不连接provider，真实预算/API0。全量回归/Convergence/Log/commitpush后停，R4保持未启用。
