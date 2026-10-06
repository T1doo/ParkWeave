# ENG048：已授权 owner 修复与 JobObject 单次 CI 终态

正式 require_escalated 审批下，同一无凭据 GitHub 根 HEAD 返回200；代理、身份、目标与配置未变，先前默认沙箱 exit7 保留为历史。只读远端实时为8da8e4a、无其他提交，普通快进推送已审查头 **ab445a9144ecc9d5c1fa1856d8bf3a007ac12450**（包含ENG045/046/047）。末次只读确认远端仍是该头，只有一个标准push run：[37457916936](https://github.com/T1doo/ParkWeave/actions/runs/37457916936)，attempt1，精确head匹配，completed/**failure**。未重跑/dispatch/追加CI、force/reset/merge main或部署。

## 生命周期与权限边界

- Setup：FAIL，exit1，BoundaryError/private_acl/**ACL_OWNER_MISMATCH，对象CONFIG**。
- SESSIONS：本次Setup最终只读检查先经过该文件的owner及DACL allowlist，之后才在CONFIG owner比较处拒绝；因此批准的首次新建SESSIONS owner修复路径已在原生Windows运行，该次SESSIONS检查通过。不能把它扩写为Setup整体PASS或全部ACL通过。
- CONFIG：实际owner SID没有观测，不能指定管理员/SYSTEM/某账户；其owner失败后DACL和后续对象没有检查。本轮没有修改CONFIG，新的权限动作超出SESSIONS授权，已停止该动作。创建路径仍为既有 `lifecycle.setup → write_exclusive(CONFIG, config_template)`，本轮未改。后续若需对首次新建CONFIG设置owner，应单独提供同样窄的对象/权限方案并获得授权；此文档不是执行授权。
- Doctor/Start：Setup失败分支未执行，无各自独立case row；生命周期API/browser明确NOT_RUN/SETUP_FAILED。不能称它们失败或修复成功。

## 回归、最后快照和原生 Job 清理

完整工程回归FAIL，regression_run/TimeoutExpired，内部仍600秒，counts MISSING。最后原子记录为 **pytest_call / test_preparation::test_unassigned_or_wrong_role_grant_is_not_authority**。这说明最后记录前进到另一测试；只代表最后成功写入，不确认具体挂点、参数、锁或600秒因果。没有回填旧run，原定点测试成绩仍只用于ENG045范围。

内层回归真实Windows路径报告 **OWNED_TREE_STOPPED**：异常TimeoutExpired保持，Job回收后确认ActiveProcesses=0才发此固定状态。外层native_suite真实路径 **exit1、timed_out=False、658.296秒、OWNED_TREE_STOPPED**，未触发900秒外层超时，结束时同样清理其自有Job。两层实际清理证据支持本次接入路径已执行，原失败未被掩盖。不能据此宣称所有超时场景永久解决。

四个专用Windows Job原生用例的逐项结果未由现有有界摘要提供；没有下载Junit/artifact或日志，因此各自仍 **INDIVIDUAL_RESULTS_UNAVAILABLE，不能记PASS**。尤其无关对照进程存活、绑定拒绝零正文、协调器突然退出这几个独立性质不能由本次两层清理结果替代。OWNED_REGRESSION_DESCENDANTS已有这次实际回收证据，完整专用原生验证仍待完成。

Publish及owned PG Stop步骤成功；pg_status exit0/0.016秒，pg_stop exit0/0.125秒/无超时。PG停止单独报告，不作为测试树回收证明。2PASS/2FAIL/1NOT_RUN为harness case统计，与pytest counts缺失不同。

## 安全证据和审查

普通API读取check/annotations，4条notice、单条最大404字节、总988字节含LF、1个去参数白名单ID、零省略，均符合原8条/2KiB/16KiB/25ID限额。两位独立只读审查一致确认CONFIG边界、last-snapshot语义、真实Job回收与四专用测试证据区别；无额外权限/代码操作。

完整安全证据见 [eng048-owner-job-ci.json](evidence/eng048-owner-job-ci.json)，本地 `.runtime/eng048-*` 保存正式网络/推送/唯一run/终态/末次确认。ENG047此前“同步阻塞”是默认沙箱检查时的历史状态，此轮正式批准路径同步已完成。结果文档仅本地提交，未再push；远端实际代码头仍ab445a9。

runner、权限合同/SID allowlist、600/900、模型/预算0、R4关闭保持；没有范围外CONFIG/root权限修复，没有访问被拒日志路线或下载artifacts。F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN；新回归等待根因仍UNKNOWN。
