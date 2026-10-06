# ENG059 — 正式审批路径恢复，唯一原生测量

本轮继续用户既有授权，不新建环境、不改变代理/身份/host。上轮默认沙箱HEAD exit7只是默认路径失败，不能据此断言已知正式审批路径不可用。按明确指示对同一api.github.com根入口申请require_escalated，工具审批后无显式凭据HEAD成功exit0/HTTP200；没有绕过明确拒绝。

同正式路径只读核对origin dev/f1-foundation，精确远端仍aa3dc550765d3a23d598b0e282dde6bfe84784eb，是当前整合候选祖先。原Actions最近五run都completed；最新37470355894失败，没有正在跑的新任务。严格身份26f848b、单job调度568e3dd与原导航1aa81a2已无冲突整合，当前1162用例/四片276、264、342、280，所有49测试+21实现manifest指纹匹配。175PASS为本地冻结定点，不是Windows全量成绩。

现在候选提交完成后对具体普通push申请工具审批，成功才描述远端已更新。只允许既有dev分支、无force/main/deploy；push触发原单个windows-2025标准25分钟job，不另dispatch/rerun。共享1500秒总限额、200秒清理、每片600不变；可能正确缺片NOT_RUN，不能视作全通过。原native900默认入口合同保留，新workflow只改同job顺序阶段。原环境/备份保留；无LIVE/新权限/新runner数，R4关闭、模型预算0、F1/F2/Win11门不变。

监测以唯一精确push head run ID为准；只读读取run/jobs/check安全字段与有限注释，不访问被拒日志、切身份或盲重跑。目标是Start PID-valid/ROOT/DIRECT_CHILD/REFUSED、原生Job清理及四片实际耗时/進度/部分结果。拿到事实后优先削减重复fixture准备或等价调度成本，需要增加总runner时间时集中报告实测需求。此文push前状态见[有界证据](evidence/eng059-formal-path-single-measurement.json)，终态结果另写记录。

后续同类默认网络失败应先核实本会话已成功的正式工具审批路径；审批拒绝或该路径仍失败立即停止相关外部操作，不改变代理/身份/host，不重复迁移环境。
