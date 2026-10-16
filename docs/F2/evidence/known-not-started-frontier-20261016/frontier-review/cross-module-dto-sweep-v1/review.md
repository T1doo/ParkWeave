# 全src跨模块七writer DTO序列化复核

STATIC_ONLY。117个src/parkweave Python模块经AST解析并结合rg交叉核对，11处跨模块DTO构造调用；未运行业务/PG测试，未改src或旧证据。inventory.json含逐调用位置及同函数model_dump。

|模块/构造点|序列化用途|结论|
|---|---|---|
|case_cancellation_before_receipt:54 sd.Command|55重建ACCEPT fingerprint|已报：None破坏旧指纹；fence需精确payload重建|
|case_cancellation_reconciliation:78/87 er.Command|93重建receipt event fingerprint|已报：None破坏旧指纹；不能忽略原字段|
|case_cancellation_reconciliation:147 lc.Command|151重建REVALIDATE prefix fingerprint|已报：None破坏旧指纹|
|lifecycle_execution_preview:79 lc.Command|80 attempt.body与fingerprint；111/117校验实际event|确认backend新发现：两次model_dump都加入None，真实lc.command已去None，后续e.fingerprint!=attempt.fingerprint；必须body和fingerprint统一原frontier_request，不能放宽117校验|
|dispatch_execution_preview:153 sd.Offer、154 sd.Command|直接传入原writer；无writer DTO model_dump重建|排除同类缺陷；execute:165的data是独立Preview DTO|
|receipt_execution_preview:190 sd.Offer、191 sd.Command、199 local.ExecuteLocal、202 er.Command|直接传原writer；无writer DTO model_dump重建|排除同类缺陷；execute:219的data是独立Preview DTO|

七writer DTO定义分别为sd.Offer/Command/Reassign、er.Create/Command、lc.Command、local.ExecuteLocal。无其他src模块直接from-import它们进行构造/序列化；API的ExecuteLocal是endpoint类型注解，executor_receipts内部import用于类型判断；未发现隐藏别名构造。isolated_local_execution本身无model_dump调用。

同模块补核：service_dispatches三写入口均frontier_request，executor_receipts create/command均frontier_request，case_lifecycle command/recover均frontier_request且recover捕获payload fence。其余model_dump来自自己的DTO（如取消DTO、预览请求DTO），不能无差别替换以免更改原语义；source-v2新增取消字段后仍需再做增量复核。

本轮新增确定位置仅lifecycle_execution_preview:80（backend已先报）；前三个取消位置是既有独审发现。普通源调用/事件读取的静态排除不等于原完整模块通过。根已计划补lifecycle_execution_preview和_browser2完整模块，冻结后重新执行32pure及完整受影响测试，成绩不迁移。
