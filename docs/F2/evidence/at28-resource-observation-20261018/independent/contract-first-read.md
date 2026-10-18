# AT28 当前资源预检来源披露：有限合同

基线 `4c1aa1005d3e81dce5a240b3a9056627ff527f1b`。先读 RemainingDeliveryGates、固定 AT22–29/33、AT22/23/24–27、FactHistoryComparison 和第二范围回执排重。已交付的算法、历史对照、三值、局部 ADOPT、第二园区冷输入及 P1–P5不重跑。AT29合法停表仍缺现有授权主体、来源版本、原始事件及当前head合同；缺项仅阻塞该写入，不自造暂停权。本片选择未交付的 AT28 当前预检来源披露。

原 AT28：检查可用性并申请确认；“显示来源/时间及需确认；本地非权威快照不能保证外部资源可用”。既有 catalog 显示资源登记来源，preview 显示数据库观察时间和当前容量/版本，但没有返回/显示该次 preview 使用的实际来源。目录读取后来源换版，用户仍看到旧目录来源，不能核对新 preview 的版本与来源。这个具体显示/响应缺口可独立修补，不需要真实来源、模板适配或新权威。

只在原 `resource_holds.preview` 增加原已验权、资源锁后 `_scope` 同一行的 source、authority、timezone、resource_name，以及明确 external_availability=UNKNOWN、confirmation_required=true。复用原 resource_id/resource_revision/server_time/capacity/occupied_peak/available_quantity/available；server_time只表示本次数据库观察时刻，不编来源更新时间、上游刷新时间或TTL保证。不新增路由、表/权限、发布源、签名、pin/receipt、持久化或评估算法。外部可用性永远UNKNOWN；LOCAL_AUTHORITY只对本地合成账本有效。

原 web.html 资源工作区区分“目录读取”与“本次预检”两个观察：显示本次预检的资源名/资源版本、来源kind/id/revision/statement、authority本地范围、UTC观察时刻、当前本地容量结论及仍需显式占位/确认。旧目录不自动换版；新预检按实际当前来源显示。新表单缺失/无效来源或观察元数据时清楚说明待核对，不把未核对响应保存成可占位预检。新增信息按 textContent 输出，仍由原 token/generation/resource/window 守卫处理迟到响应，新增代码不复制恢复协议。

实际变更后仍复用原 HOLD 的 expected_revision、当前权限、锁后DB时间、开放/缓冲/峰值，以及原单/组合确认；不修改或重测这些已完整覆盖算法。测试只取新增来源切片所必要的原动作：原 catalog-v1→自有夹具来源/登记v2→原preview-v2→本人明确原占位/确认并核边界；另核新页面对未核对元数据不启用占位。源变更只在新自有、原有合成资源fixture，不产生真实身份、Grant、分派、发布或批准。有限使用原 API/PG、原完整 HTML 的 NodeVM/实际HTTP，实际浏览器/Windows/正式 AT28/真实资源及完整项目均未验。

先冻结原文/有限oracle与本合同再读实现；独审仅静态审查本次明确Git SHA和原保护边界，不重试此前模板风险标记动态窗口。历史独立动态0、旧5PASS/1FAIL、平台标记原记录与历史HTTP UNKNOWN保持原范围。只root写tracked/Git，普通新devpush已授权；main/强推/部署/费用/真实模型/凭据/安全网络权限/未知锁进程不动。
