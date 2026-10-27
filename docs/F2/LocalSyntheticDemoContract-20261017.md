# 普通启动本地合成演示接入合同 / 1

本切片把已有 preparation、当前身份/权限与原 V4 有限选择算法接入普通 `parkweave.api:configured_app --factory`。默认关闭。它只处理明示 SYNTHETIC 本地样本，不代表真实园区接入、正式批准、履约或 Windows 正式 AT。没有零准备一键全链。

## 入口和输入

保持既有 `PARKWEAVE_DSN`（应用身份，不是迁移 owner）、`PARKWEAVE_MODE=LOCAL`。同时显式提供：

- `PARKWEAVE_SERVICE_PROFILE=LOCAL_SYNTHETIC_DEMO`。
- `PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG`：严格 `parkweave-local-synthetic-demo-config/1` JSON，字段对应 `DemoConfig`，含既存绝对 pack/journal 路径及各自原始文件 SHA256、实际数据库 name/OID/address/port/user、原 `preparation_catalog` 内容哈希及 xmin generation。
- pack 是 `parkweave-local-synthetic-demo-pack/1`、`kind=SYNTHETIC`、版本/有效期、园区/组织、三个原身份、两个原资源、两个原字段映射、最多三个已注册合成服务种类；严格字段、禁止真实来源及额外字段。
- journal 是 `parkweave-local-synthetic-demo-journal/1`、`kind=SYNTHETIC`，精确重复 pack 文件哈希、数据库、园区/组织、原目录哈希和 generation；journal 文件必须为私有权限（Linux 下无 group/other 权限）。它只是预先存在的输入绑定锚，不是批准、发布或授权账本。加载器不写入它。

未配置维持原拒绝。未知 profile、单独配置、错库/园区/组织、文件变化、原目录变化、真实源、过期包均拒绝。必须已有普通 schema 32；仅允许 LOCAL 执行模式，启动不迁移，不引入 schema 33 fixture 许可。包内目录只派生原有限注册合同，不建立 TemplateEngine 发布、source_review 或 Isolated 类型来源。

## 权限和行为

`LocalSyntheticDemo`、`LocalDemoCatalog`、`LocalDemoSelector` 是独立精确类型，不继承隔离测试类型；旧 Isolated 类型门、旧 OFFLINE_HTTP_FIXTURE 模型证明保持原义。普通 demo 禁止混入隔离 catalog/planner/consumer/Approval、正式来源或批准 provider。

每次目录/选择/采用及原业务绑定核对都须原 owner、当前 reviewer、park/org 一致，并重新读取已有 READ/PREPARE/REVIEW_ASSIGNED/EXECUTE、原 SYNTHETIC 资源 READ/HOLD。没有 Grant、身份、分派、批准、目录发布、token 或凭据创建。NativeRunAccess 的 permit/writer 默认拒绝不变。运行分派及资源批准仍由原业务入口负责。

复用 V4 解析、穷举最小解和注册图重建。demo 独立来源是 `LOCAL_SYNTHETIC_DEMO_NO_MODEL_V1`，候选校验版本 `LOCAL_SYNTHETIC_DEMO_V1`；producer 明示 `NO_MODEL`、`model=null`、`provider_enabled=false`、`real_model_calls=0`，没有虚构 HTTP、usage 或预算。只允许唯一合法解；多解、未知或不支持保持拒绝。候选在原 PostgreSQL planning_previews 内单事务保存；原 key 读取不重算外部调用，采用仍须用户显式确认，后续仍为原 P1–P5 命令。

## 初态和边界

测试可显式建立隔离合成数据库、原身份/Grant/资源/目录及精确 Run 分派；这些全部在启动加载器外，并单列初态写入数量。普通程序必须由调用方提供相同意义的合法既存输入，不会把测试初态操作移入启动。

最小切片从已有 preparation 或原普通 Run/preparation API 开始；未新增 cold-input 向导、真实模型、真实资料、正式批准或正式业务权限。真实运行仍缺已授权数据库/模式、已有身份及当前 Grant、合法原 preparation_catalog/preparation、精确 Run 分派与业务需要的原资源/批准输入。Windows、本机正式 AT 和真实业务场景须另验。
