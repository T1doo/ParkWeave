# run41 精确来源绑定候选：未运行

直接父 `4e3d7a877b8b0afbcc04a33ff6c047f151cb5d14`。实时读取最新为 run40／39994718230／attempt1／completed failure；预期下一编号41。执行ref仍 `2560ab9e964554814165cbd0057b70d6c3ff23ba`，本轮只推不匹配任何既有 workflow 的 `dev/ui-resource-guide-run41-review-20261023`，不推进执行ref、不启动浏览器或CI、不重跑40。真正执行前必须重新核实际下一编号、ref和精确候选SHA。

本提交只同步主／worker、workflow、font 的run41门、直接父和七路径；反向还原绑定后，三文件与父版逐字一致，两个产品页原字节不变。八图、四状态请求限制、原 actor 等待、字体资产、sandbox／CSP、未知GET拒绝、POST0、90秒工作清理／85秒worker／360秒发布、job10分钟／依赖3分钟／每侧GET≤39／最多10文件8MiB与全部清理门不变。

沿用已审资源fieldset／组合与导览局部八图及动作边界，不追加新场景。源run40没有PNG，资源几何、八图和导览跨窗仍未到达；父级原件检查与修复证据见 ../run40-approval-fixture-fix/README.md。既有离线红例是原actor等待条件为false的预期观察，命令本身exit0，不称“测试命令失败”；绿例是完整原脚本的机械DOM／fetch执行，不是浏览器或真实视口通过。

本片实际检查仅五个纯来源listing合同正反例，以及精确绑定逆向还原、页面hash、文件白名单和审查分支触发范围；不重跑此前红绿、几何或业务套件。提交前preflight明确NOT_EXECUTED；提交后真实source_contract另存原stdout并全文回报，不用旧PASS或脏树快照代替。当前无新HTTP／PG／pytest／collection／浏览器／CI；产品与真实来源／OWNER／Windows／模型门未改。
