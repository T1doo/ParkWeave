# ENG060 — 唯一原生测量终态与可证边界

已完成正式工具审批HEAD HTTP200、普通push和唯一标准Windows Server run。[37483067638](https://github.com/T1doo/ParkWeave/actions/runs/37483067638) attempt1精确head `08cd6591ff7a7aa9fb00d0b911153f7d617caf56`，completed/failure。远端push后及终态后精确头均核对为08cd659。没有另dispatch/rerun、新runner/权限、LIVE调用，1500秒总cap、200秒尾部、每片600保持。上轮默认exit7只是默认沙箱路径失败，已知正式审批路径成功；不能再把默认失败当成必须重建环境或正式路径不可用。

## 实际时间

| 项目 | job step墙钟 | bounded native命令 |
|---|---:|---:|
| Prepare | 29秒，success | initdb3.907秒、PG start0.266秒（仅两个可见子项） |
| Lifecycle/API/browser | 86秒，failure | 85.562秒，exit1，timeoutFalse，OWNED_TREE_STOPPED |
| guard/candidate/regression | 19秒，failure | 17.282秒，exit1，timeoutFalse，OWNED_TREE_STOPPED；获分配1141秒上限 |
| 安全发布 | 1秒，success | 0.063秒，exit0 |
| 最终owned Stop | 1秒，success | app0.109、PG status0.015、PG stop0.235秒，均exit0 |

job从14:55:51至14:58:24，总153秒。提前失败，没有容量耗尽证据；19秒不是四片完整运行时间，也不能拿这次短运行证明1500秒足够。

## Start、Stop与Job实际证据

安全发布SUMMARY_AVAILABLE/COMPLETED，6PASS、5FAIL、1NOT_RUN，6条非PASS全部可见、0 omitted。check title/summary/text仍null；只读安全注释及固定phase字段，没有访问私有日志。

Start：两根记录；attempts50、responses49、mismatches49、transport timeout1，无refused/http/other计数。最近响应mode/model匹配、health PID类型为正整数，但process_matchesFalse/server_relationREFUSED。这只定位到严格身份合同拒绝，不证明PID必定不同、也不证明49次全部仅PID不匹配。bind可在child检查前拒绝root；具体句柄、ctime、命令/cwd、父关系分支仍UNKNOWN，不能猜redirector或调低10微秒容差。

Start内部stop_record调用2、stopped0、foreign2；两根清理后仍RUNNING，内部final_Stop_owned_services也FAIL。foreign是合同拒绝，不能称实际外来进程，调用数也不是terminate次数。随后Lifecycle外层owned Job、Validation外层owned Job和regression内Job均实际报告OWNED_TREE_STOPPED。最终app Stop exit0可包含树回收后的ABSENT清记录，不能反推原严格身份检查通过；PG停止成功明确独立记录。

四个原生Job测试逐项结果UNAVAILABLE；不能用这三个实际树回收取代四个完整pytest oracle或F1/Win11签收。

## 回归与容量观测缺口

full_engineering_regression FAIL/exit1，counts MISSING、REPORT_MISSING、最后phase acceptance_bindings、无失败ID。没有完整collection、四片覆盖、逐片实际耗时或fixture瓶颈证据；S1-S4均UNAVAILABLE（不是编造为producer已声明NOT_RUN）。API_browser_restart明确NOT_RUN/START_FAILED。回归入口前置失败没有走到可见报告；同1141秒outer deadline而17.282秒结束的事实不支持预算不足解释。

即使正常执行，冻结源目前只保private全局elapsed；native_suite未提升pieceRows，publisher未投影每片时间/覆盖；共享progress文件被后一片覆盖，最后snapshot仅该片局部计数/计时。采样预算20/片，不能据最后快照算全job采样数。该接口缺口也必须先本地补齐，才谈完整四片真实测量。

## 独立本地复现与下一最小建议

独立临时clone冻结08cd659，在本地设置core.autocrlf=true再checkout（只该临时副本，未改工作区/GitHub/网络策略）：49/49 test rawhash改变且含CRLF。validate_manifest拒绝test file fingerprint changed；实际CLI exit1、最后phase acceptance_bindings、report不存在，无collection/shardJUnit。LF对照接受，CRLF版JSON规格语义不变、42固定绑定通过。此严格复现与当前安全接口吻合，但没有本次Windows checkout byte或typed failure reason，不能将CRLF宣称为本次已确认根因。绑定读取/校验、报告目录访问、第二次截止检查等早失败也未逐项排除。

下一本地候选应同时准备：固定bind/Stop refusal阶段与原因（不输出PID/时间差/路径/异常正文），manifest-covered tests固定LF检出且保rawhash核验、入口失败原子固定原因报告与四片NOT_RUN，固定S1-S4每片elapsed/状态/计数/coverage/cleanup与冻结片内progress，四个native Job oracle逐项typed结果。既有公开8条/2KiB/16KiB/25ID边界不扩大，不减弱身份或清理合同。实际根因明确后再决定唯一后续验证，不能盲跑。

本次没有新增源码修复或额外CI；只提交并普通推送终态文档，唯一workflow的push paths不覆盖这些docs，不产生第二run。没有fixture瓶颈测量，故不贸然共享可变fixture或放大scope；若后续实测表明重复迁移/seed成本显著，先本地等价调度/隔离实验，再集中说明确需的runner时间。R4关闭、预算/真实模型0、F1未签收、F2并行探索、Server不等于Win11、36AT/6EX NOT_RUN；原环境/备份/导航保持。

完整有界数据见[实际证据](evidence/eng060-single-native-measurement.json)。
