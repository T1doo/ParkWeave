# ENG013有限清理与凭据边界冻结

基线本地b9bc4dba0bac17b266004683ea72600e7f3f1e4c。仅PG启动失败/owned state篡改/浏览器超时清理oracle及CI子进程owner/admin凭据隔离审计。不得重试Actions/换身份路线/读取凭据/推送workflow/启动runner/改权限；仅本地commit。Forbidden使用ENG012原记录，数值HTTP状态仍缺失。

原lifecycle.start使用app_environment生成API/worker白名单，未发现直接继承owner的路径；但CI native_suite此前把owner/test/app DSN统一传所有PowerShell包装器，Start/Doctor/Stop/Server文件probe不需要这些admin配置，属于本轮需修的最小暴露面。按阶段区分可信Setup/DDL、测试协调器与应用/文件/浏览器，实际API/worker只获低权限app DSN；未知/misbound app配置拒绝。全部Fake Mapping/合成DSN验证，绝不读真实凭据。

集群控制纯helper可在Linux用明确命令test double验证真实PS控制逻辑，不绕Server入口守卫，不执行PG；状态拒绝须在任何native命令前、启动失败保留主失败并安全停止自身cluster、未知状态不猜测清理。browser timeout须关闭自己session/driver后清新profile，失败不掩盖主错误；其他独立suite阶段仍执行。原Win11 guard/生产R4不改，原来源/历史不改，whole AT/EX NOT_RUN、真实模型/API预算0。
