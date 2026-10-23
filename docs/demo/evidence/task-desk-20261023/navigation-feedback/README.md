# 未决材料期间的工作区切换

基线 `6d0dff525830af8c158501305ecbe2a5e3845fb6`。按原产品设计§3三个工作区及§7结果不明语义，修复真实原逻辑可达的问题：材料请求失败或提交响应后的读回失败，原跟踪 finally 将通用请求交给专用 UNKNOWN；主导航因此可以通过通用只读守卫，却在清屏中途才因原 pending 拒绝。旧状态不是“没有任何提示”，原材料提示仍在，但通用和部分子视图已清，导航 wrapper 产生未处理拒绝。

`red-original.log` 记录原源码在拒绝前调用8个子清屏函数；`red-unhandled.log` 保留第一次直接观察到的未处理拒绝。修复只把原异议→材料两项阻止条件抽成纯预检，置于导航任何清屏及 clearPreparation 自身的最前端。不增加其它 pending 限制，不改变原恢复、鉴权、请求或许可。导航拒绝仅更新已有全局 polite 反馈，保留原 result、事项视图、请求编号和正文；正常清屏顺序及 aria-current/hidden 切换不变。原身份/403 使用的 discard=true 路径继续清屏。HTML/CSS、业务提交及跟踪逻辑逐字不变，见 static-checks.json。

最终实测 **14 PASS / 1 warning / 0.79s**：5个导航模式＋9个受清屏改动影响的目录模式，非历史累加。导航测试执行原 sendPrepCommand→prepCall→entryFetch、trackedEntryFunction finally、原读 wrapper 与导航，使用合成 fetch/DOM和子清屏替身；UNKNOWN由失败路径产生，非直接置标记。覆盖POST传输失败、POST有响应后GET失败、三工作区正常切换、discard=true及原异议拒绝。未执行 capture DOM事件、完整子清屏、真实API或浏览器/读屏。它不承诺所有未知清屏异常均事务化。首次测试接线错误日志保留：新helper未纳入旧提取器、测试wrapper共享闭包变量；修正测试接线后产品源码未再变化。

独立只读 `/root/summary_review` 限定ACK，无新增确定P1/P2。Node语法及精确改动范围检查通过。清单实际收集9535项/407文件，**不是测试通过数**；四片数量由本次全局收集推导，未重复分片执行，原历史记录保留。

渲染条件：本地 sandbox helper 故障与旧run34 ZIP/log Forbidden 均未重新尝试或绕路。独立只读核验已有 [run30原件](../../collaboration-indexes-20261023/run30/README.md) 证明过去存在受支持 hosted Chrome 路径：Ubuntu24.04 image20261012.334.1、Chrome155.0.8059.39、正常 namespace/seccomp sandbox，35同批GET/0POST，工作及清理21.569s；它不代签当前候选。

下一次新候选的正常静态渲染需另行审核精确源码/比较合同和实读新run编号，同步原workflow/driver/font门；旧driver仍绑定run34/f3f67直接父及旧script逐字相同，不能直接套用当前树。保留原10min job/3min依赖/90s UI清理/360s发布、双侧各GET<40/0POST、原固定字体许可、10文件8MiB、正常sandbox与自有进程清理。新目标的附件/log是否可读取仍未知，遇拒绝停止；不能以新CI取回旧Forbidden原件。本轮未启动该窗口、未改workflow，截图0、CI0、实际业务API0；无新权限、凭据、费用或用户电脑操作。
