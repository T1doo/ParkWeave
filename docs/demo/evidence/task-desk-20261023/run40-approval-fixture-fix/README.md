# run40 原 GET 夹具补齐：离线候选，未补跑

基线／run40 源码 `2560ab9e964554814165cbd0057b70d6c3ff23ba`。只改 driver 的精确响应映射与数量：新增原已有 GET `/api/plan-approval/status`，只允许四次。响应与真实 disabled API 相同字段：enabled=false、approval_scope=null、所有可选启用位=false、production_execution_enabled=false、formal_release=false、合成 enterprise_operator 角色；原消费者用既有 fallback 识别 ISOLATED scope，但批准能力仍关闭。没有新增端点、权限或业务功能；产品、actor 等待、字体、workflow、8图、时钟、GET总界、POST拒绝和清理代码不变。逆向还原这两处映射后，driver 与基线逐字一致。

## 原失败与本次范围

[官方 run40](https://github.com/T1doo/ParkWeave/actions/runs/39994718230)／job120555140669 为 FAIL。父级正常读取并校验原件：仅 result、无 PNG；首 RESOURCE_1200 等待表单和 actor 15秒超时，最终 bundleIdentify 的 Promise.all 还请求 approval/status，旧driver返回404，actor保持null。GET5、POST0；cleanup18.946秒、CLOSED／REFUSED、自有全树退出且无cleanup错误。此处引用父级原件复核，不声称本执行器读取了附件，也不认定产品故障。资源几何、八图和导览跨窗场景尚未到达。

核对完整当前调用链：catalog 原按钮读取 synthetic-resources 后调用最终 bundleIdentify；mine 原按钮也调用同一最终覆盖层；每次并行读取 bundles 与 approval/status。两组对应目录2、bundles4、status4，均是原只读请求，仍各侧最多39 GET、POST0。最终 controls／renderer 只核本地状态和注册回调，不额外读取；原 token change 的 run-access/status 已有独立精确夹具。未触发写回调，未扩成新业务测试，也不据静态核查保证全页面所有未来请求。

## 实际离线检查

使用既有测试的机械 DOM／fetch 前缀，执行完整未修改的原网页 script：缺失 status 时复现 actor=null 且表单可见的原等待假值；补齐后原 catalog→mine 两次逻辑序列只出现2/4/4 GET，原三成员 renderer 成立，重新批准／替换／frontier／closure及提出／批准／撤销按钮保持关闭。两序列不等于两个真实视口。实际命令、exit、stdout、stderr保留于 offline-original.json；未运行此前无关测试模式。

另直接调用原 Handler.do_GET，使用内存响应对象，不创建HTTP监听：status前四次200且能力全关，第五次404，未知GET仍404。API DTO字段集合与原实现一致。未注入actor，未开启真实批准，未放宽等待／未知路径／预算；未运行HTTP、PG、pytest、collection、浏览器或CI，不新增测试ID。

当前仍保留旧 run40 精确绑定，本修复提交不能直接执行；必须另经独审重绑实际下一编号及新直接父。没有重跑40或启动新窗口。像素、OS文件选择器、原生popup拦截、Case交付像素及正式业务均未验。
