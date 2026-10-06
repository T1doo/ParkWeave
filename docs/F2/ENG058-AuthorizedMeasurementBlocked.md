# ENG058 — 已授权一次原生测量，默认连接阻塞

用户已明确允许将独立复核的严格身份修复、单job顺序调度与原导航整合，普通push既有dev分支并运行一次标准25分钟runner。新授权取代ENG056/057当时“容量未确认不push/CI”的范围限制；目的为原生测量，不承诺四片全量完成。不增加runner/job/权限，1500秒总上限、200秒清理预留、每片600秒保持。

本轮本地实际整合提交 `05fcb0e`：身份修复 `26f848b`、调度 `568e3dd`、冻结证据 `744174d`，合入原导航 `1aa81a2` 无冲突，七文件blob全部原样。49测试文件及21实现文件manifest指纹仍全部匹配，原175PASS成绩保持冻结原范围；合并没有改这些源/测试，未无依据重跑整组。1162用例/四片276、264、342、280仍是collect完整性，不是Windows全PASS。原dev工作树、分支、备份及旧候选保留。

2026-10-06 14:49 UTC，本环境默认网络/代理/身份对 `https://api.github.com/` 做唯一无凭据HEAD，curl exit7：`Failed to connect to proxy port 8080 after 0 ms: Could not connect to server`。请求尚未到达GitHub，无HTTP状态，不能称403/权限拒绝。未改代理/策略/身份、提权或改走其他工具路线。按先连通再查远端的边界，未请求origin远端dev/Actions、未push、未开始新CI；当前远端头UNKNOWN，aa3dc55只是最后历史已核对值。

恢复默认连通后继续既有授权：只读核对origin dev/f1-foundation与Actions，比较是否新增远端提交，普通push（不force/reset）；监测唯一精确head标准run到终态，不手动重跑。记录Start PID-valid/ROOT/DIRECT_CHILD/REFUSED安全字段及原生Job结果，四片实际时间/进度/部分counts/JUnit覆盖与cleanup。预算不足为NOT_RUN，清理未确认隔离，不能当完整PASS。取得真实证据后优先检查重复fixture准备或等价调度成本；若需新增总runner时间，集中提出实测需求，不盲跑。

详见[阻塞证据](evidence/eng058-authorized-measurement-blocker.json)及[容量/调度说明](ENG057-SingleJobSequentialSchedule.md)。R4关闭、模型调用/预算0，无main merge/deploy/真实外部履约或自动资格判断。F1未签收、F2并行探索，Server不是Win11，36AT/6EX保持NOT_RUN。
