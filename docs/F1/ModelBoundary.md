# 书生适配运行边界：离线实现，LIVE禁用

核对来源（2026-10-05）：[官方Chat Completions](https://internlm.intern-ai.org.cn/docEn/docs/Chat/)及[官方型号页](https://internlm.intern-ai.org.cn/docEn/docs/Models/)。非流式POST使用chat/completions、Bearer鉴权、messages/tools，工具反馈带匹配tool_call_id；finish_reason区分stop/tool_calls/length。模型固定intern-s2，不采用随时间变动的latest别名。官方工具参数示例存在单引号样式，本实现只接纳严格JSON，不eval或修补后执行。文档查询不是模型接口探测。

`intern_adapter.py`为正式HTTP载荷/响应校验边界，但本轮构造器只接受确切httpx.MockTransport；真实传输及live_complete直接BLOCKED。API/worker不启用此适配器。测试token仅虚构SecretStr，不读取真实环境值、.env或其他项目配置；真实请求授权/实际调用均0。

自建SYNTHETIC响应只复用官方字段形状，不声称收到Park真实模型回包。已知Intern-S2/intern-s2的ASCII大小写同名可接受；空白、Unicode近形、latest/preview及其他型号均拒绝。返回模型缺失/错误、完成标记缺失、length截断、未知工具、额外script、重复JSON键、非JSON参数、空白目标、多工具或缺反馈均不产生可执行proposal。

可信工具仅case_create→现有case.create的有界参数（goal≤2000字符）。proposal始终executed=false，不能替代用户授权或Run/Grant/租约/fence网关，不新增办理/预约工具。两次离线请求验证工具选择→明确合成反馈→文本修订，不伪造Case/外部受理/线下回执。

本地离线预算账本用锁最多3次尝试，单次保留8192 token额度、默认总24576；输入8消息/16KiB、输出上限1024、响应验证≤64KiB、HTTP timeout参数≤120秒、非流式、不跟随重定向/代理、不自动重试。429/401/403/5xx/超时/传输失联/无效JSON保留尝试记录；超时/断链不推定上游未计费。usage缺失保持UNKNOWN并保留保守预留；有效整数usage核对prompt+completion=total，超预留时拒绝输出且记实际数，后续预算检查阻止扩大。日志仅attempt/分类/usage元数据，不含key/messages/response内容。

这些是离线控制与解析证据，不证明真实HTTP超时取消、模型限流、上游实际计费或全成本。预算计数是进程内fixture，不是持久跨产品总配额协调器；无真实tokenizer/价目，因此不能把保守预留称作精确财务成本。仍需独立工程：经授权启用的真实传输/持久调用usage账本/共享配额协调及worker规划链绑定；后续获安全配置/预算才可做真实AT-02/30，本轮不为此建新调度框架。

模型token命名仍PARKWEAVE_INTERN_API_TOKEN优先、INTERN_API_TOKEN回退。只有未来批准的注入路径才可取值，当前不用；密钥不进入配置、源包、记录或聊天。其他项目已验证模型不能继承为Park通过。
