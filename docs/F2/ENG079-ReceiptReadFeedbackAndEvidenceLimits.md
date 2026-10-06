# ENG079 回执读取反馈与原生证据边界

## Forbidden 的已知范围

仅使用ENG078已取得的响应，不再请求网络。正式权限审查通过，run/jobs元数据读取成功；失败发生于 `gh api` 的 job-log GET 读取流程。工具退出码1，脱敏错误类别为 GET / Forbidden。没有保留HTTP状态码，**不能写成已观察到HTTP403**。错误中的URL已脱敏且原值未保存，无法判定是GitHub API原始端点还是其重定向存储地址返回；具体拒绝位置UNKNOWN。它不是本次权限审查拒绝。没有更换凭据、工具、地址或代理绕过。

独立run37545785486/attempt1/source381a20a的success和测量step4秒已直接读取；后代membership/signal时序、无关进程LIVE/cleanup及转移句柄关闭JSON仍UNAVAILABLE。成功状态不能替代直接JSON，也不代表完整工程CI或历史S4通过。完整CI未恢复，owner保持暂停，描述符对象未选择，未新增push/run。

## 实际用户流程缺陷与修复

只复用保留Case `0b76ab4c-e429-4313-ace2-25d3522ed09b` 和已有assignment。使用真实Chromium、当前源码API、worker和保留PG，不seed/migrate/assign或更改grant。此轮只读回执，没有提交、核对、重开等业务写入；回执revision13、5个版本及history前后相同，全部run_assignments/capability_grants前后相同。

实际发现：回执刷新会先隐藏详情，无效合成会话的真实API **403**、或刷新断连后，错误只写进隐藏详情里的receipt-error，用户看到空白，没有可见反馈。这里的本地403是独立实测，与上方GitHub日志状态码未知无关。

最小修复receiptError同步写入现有可见page-feedback；连接/解析失败使用固定中文提示，成功读取列表或详情清除旧提示。原身份/事项/generation guard、权限、重试key、版本和关闭条件均未改变。不自动重试、不代替用户办理。

## 实际验证

修复前后均跑真实浏览器：输入无效合成会话→刷新回执列表（真实HTTP403）；合法身份打开原回执→一次受控浏览器断连→刷新列表恢复；将真实成功GET响应延迟到身份切换后返回；将旧请求的受控拒绝延迟到新身份已加载后返回。断连和旧拒绝是明确的浏览器故障注入，不能称为真实权限撤销。迟到成功不恢复旧历史/内容；迟到错误不覆盖新企业身份提示。执行者和企业读取相同已有回执历史，revision和版本数不变。

主线程实际查看修复前无反馈图、修复后403可见提示与连接失败可见提示图。仅桌面viewport像素查看；未新增移动端或真实设备签收。最终通过保存的 [只读复验脚本](../../scripts/receipt_read_browser_smoke.py) 实际再跑一次，结果见 [证据](evidence/eng079-receipt-read-feedback.json)。相关既有回执/Case回归 **77PASS，2个既有警告，31.40秒**。默认沙箱的PG socket setup先失败；已授权本地socket权限路径成功执行，不能将最初77个setup error称为业务失败或跳过。

各轮API/worker均由拥有的Popen句柄SIGTERM后wait（-15/-15），PG STOPPED，无广泛kill。原本地数据库、已有Case/assignment、前后截图和环境均保留。模型0、预算0、R4关闭，F1未签收/F2并行、Windows/Win11/完整AT_EX未运行。

## 最短当前体验与恢复

在当前保留合成环境输入已合法准备的本机企业会话，进入“协同”→“刷新我的回执事项”→选择同一事项；执行者切换到已有合法本人会话后从同一列表选择该事项。切换身份会清除旧内容，迟到响应不能恢复它。权限提示出现时核对当前会话和已有授权，不新增grant；连接提示出现时先检查本机服务，再刷新列表并选择原事项。成功读取后旧提示消失。

本会话复验入口为 `.runtime/eng079-existing-case-read.py`，它启动保留PG/API/worker并调用发布源码中的只读浏览器脚本，然后停止自有服务。该本机harness依赖保留fixture目录、私有会话和缓存浏览器，未承诺环境重置后可直接运行；不得改用ENG073新建Case脚本来替代本轮复用范围。私有会话/DSN与原始服务日志不写入交付文档。

收尾同步分片清单中workflow指纹至已推送的ENG078独立配置，保留替换前ENG077历史指纹；53测试/33实现指纹均匹配当前文件。用例集合与collect-only证据不变，未执行或恢复完整回归。
