# 自有启动与失败清理修复（未启动浏览器）

基线 `214fc8b07afa2d541b9b49d010a78f7537e7eb78`。本片仅修复启动失败记录及自有进程退出证明；没有新 Chrome、API、PostgreSQL、模型或 CI 执行，没有新增截图。run26 仍 FAIL，其 Chrome 15 秒启动超时原因、旧进程退出均 UNKNOWN；不使用旧 PID 清理。

监督器仅创建一个握手后启动的 worker，私有 SID 保持至退出核查。进程级 subreaper 接收逃逸会话孤儿；绑定前后均核出生身份及直接子进程/保留 SID 的同一归属依据，再通过 pidfd 发信号。无日志 PID 信任、裸 PID 祖先闭包、进程组 kill 或数字 PID fallback。拒绝不重试其他信号通路。原 90 秒预算内最多 85 秒工作，余下清理；15/30 秒操作等待不缩短，余量不足准确失败。原 sandbox、CSP、字体、40 GET/0 POST、10 文件/8 MiB、360 秒发布及 10 分钟 job 门保持，run26 门未更换，不会因本提交启动新 CI。

`checks-ownership-fixed.log`、`stdlib-case-results.json` 是最终监督器的 9 个真实 stdlib 子进程场景：正常、孤儿、double-fork/setsid、忽略 TERM 超时、原错 checkpoint、TERM 时新派生、pidfd 拒绝、枚举失败、signal 拒绝。前六项完成退出/范围核查，后三项保守返回 CLEANUP_UNCONFIRMED。独立于受控树的自有 sentinel 保持存活且无信号，测试结束仅由创建它的外层 checker 清理。

`ownership-check.log` 为 3 正例、7 拒绝例，属于纯身份谓词检查，不是真实 PID 复用实验。`driver-checkpoint-final.log` 是对当前 driver 的一次注入：原 launch TimeoutError、稍后的 SDK RuntimeError 分开保留，最终私有 checkpoint 存在。SDK、字体、server 全部模拟。`driver-parent.log` 为 3 个父层终态注入：正常成功、清理未知拒绝成功、输出超限拒绝成功；没有真实发布。

保留 `driver-checkpoint.log` 的旧 fixture 固定时间线索引断言失败。`driver-checkpoint-corrected.log` 改为查找正确阶段后通过，产品未因该 fixture 红例修改；最终当前源码再次注入记录单列，不累计旧次数。各 fixture 原路径只适用于指定环境，日志未改写；`source-binding.json` 绑定最终源文件与历史 collection。757 是源码指纹数，非测试数；本轮未重新 collection。

尚未验证 Chrome 实际启动/退出、新 CSS 中文像素、布局焦点/禁用/拒绝状态及内容关键页整套视觉；不能宣称前端已精美或验收完成。下一有界视觉窗须在本修复独审后另行绑定，不自动重跑。
