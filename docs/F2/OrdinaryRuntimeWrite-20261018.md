# 普通工厂的既有受信 writer 接线

本片只补普通 `configured_app` 到原 `WriterClient` 的显式绑定；现有申请、批准与激活 API 继续复用原类型、鉴权、期限、原键、签发和事务算法。没有安装器、政策发行器、密钥/身份/Grant/assignment 创建或实际激活。未配置保持原默认拒绝，旧只读入口不变。

`PARKWEAVE_RUNTIME_WRITE_CONFIG` 是最多16KiB的严格JSON，仅含 `schema_version=parkweave-ordinary-runtime-write/1`、`binding_path`、`binding_sha256`。路径须为规范绝对路径；不能与 `PARKWEAVE_RUNTIME_READ_CONFIG` 同时提供（空值也算提供）。无环境布尔值升权、凭据发现、自动修复或fallback。

该路径指向**已有且获准发布、root保护**的公开记录，schema为 `parkweave-ordinary-runtime-write-binding/1`。记录包含：

- `operations` 必须精确为 `["COMMAND","ACTIVATE"]`；未知、重复或缺项均拒绝。
- `binding_path/binding_sha256` 指向原 `parkweave-restricted-api-binding/1` 的受保护host公开pin。
- 精确 `preparation_id/case_id/run_id/service_id/service_version/catalog_sha256/catalog_generation`。

环境、外层记录及内层host JSON均严格拒绝重复键、额外字段及非有限值；不接受DSN、key、模块、URL或测试开关。两层文件使用原host保护读取，不创建、chmod或发布文件。原 `bind_api` 保留root保护、实际API身份、IPC组、数据库角色及ACL检查。仅接受精确 `WriterClient`、`PRODUCTION` policy，policy和endpoint pin须与受保护内层记录一致；拒绝reference、test/activation permit、WriterContext、readonly桥及隔离provider混用。这里的PRODUCTION是既有安装合同枚举，不证明实际安装已完成。

启动只做原VALIDATE/VERIFY及当前scope只读核对，不发送COMMAND/ACTIVATE。失败或中断只移除本次新bridge，不清其他或原有bridge。每次原COMMAND/ACTIVATE转发前重读两层pin并核对scope与原client当前验证；原request key及正文不改、不缓存成功、不自动重发。绑定失效阻止新命令，原有有权历史GET/原键恢复语义保持。

managed assignment的业务访问及原guarded commit沿原 `assignment_allowed` 用**同一连接**重核scope，不嵌套连接或调用自身。新增service/catalog/xmin约束是API调用前及managed业务提交门，不在旧WriterPolicy.Source中；不冒称原writer事务也核验这些新增字段。文件撤回不能原子追回已交付writer的命令，原writer仍最终决定权限、到期、撤销、幂等及event/assignment原子提交。

## 有限离线验证

执行 `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tests/test_ordinary_runtime_write.py`，直接unittest，不调用仓库PG fixture。内存SELECT-only连接替代数据库；仅对protected读取/binder及RPC端点做明确DI，原scope、Client._database/validate/invoke、Native API类型与路由执行。到期/撤销/缺权/重放冲突是DI端点拒绝传播；并发测试只证明独立正文/原键及延迟调用遇变更先拒绝。它们不证明真实writer权限算法、签名、IPC、PG并发或assignment原子性。另有未替换保护读取的临时非受保护文件实际拒绝反例。

设计先经独审。WIP独审发现P2：有限异常捕获会留下半绑定；已改成功标志+finally，并覆盖RuntimeError/AttributeError/KeyboardInterrupt及保留别人的bridge。开发v1因内存查询行形状和缺认证查询出现1失败/11错误实例；v2原请求正文缺字段出现1错误；原日志保留。v2期间追加测试，不作为冻结来源证明。随后v3十九方法、v4二十一方法通过，均属开发窗，不与最终冻结窗相加。最终源码SHA、冻结结果及独审见本片证据/交付回执。

## 仍需实际配置与后续工作

必须另获批准后才可准备合成执行者/会话/READ、两资源及企业四条READ/HOLD、合法pack/journal、应用精确DML、独立受限writer身份/连接/key及受保护host/policy/pin。每个新Run需独立具名政策和正常申请/批准/激活，不能用owner-only `assign_status` 或隔离发行器预置。普通安装/政策发行及用户激活界面仍有后续工作；现有受限host试验边界没有放宽，只有新环境变量和几份JSON不会让当前环境可写。

当前材料专用库、会话与旧源码pin未修改；新src不能冒称已在该库运行。无DB/服务/真实模型/浏览器运行，无权限或网络改动。Windows正式AT、从新安装零准备到同Case完整P1–P5再运行的无夹具正式AT35、完整F2/比赛仍未验/未完成。历史DOM和旧固定ZIP保持其原冻结范围，本轮不重包或重测旧13项。
