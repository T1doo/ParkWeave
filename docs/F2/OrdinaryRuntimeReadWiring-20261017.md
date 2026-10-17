# 普通运行时既有授权读取接线

基线 `fb09abafc2e56a446cc372e6a4ce46afcd64571d`，冻结源码 `6ab25aa0d10dda48fa3d12184a235a6e50fcccea`，开发分支 `dev/f3-ordinary-runtime-read-20261017`。基线已由父线程独审准入，父线程独立解析的是原178项公开JUnit，并非重新执行；本片不继承其测试计数。本实例仍是唯一源码/Git写入者，完整项目尚未完成。

**本片状态：待审候选，完整验证门未通过。** 最终427唯一项为425PASS/2FAIL/2teardown ERROR/0SKIP，新增36项包含在内且全PASS；两项原连接握手超时原因未确立，详见末节及原始失败窗口。

## 已接入的原链路

普通 `configured_app` 可显式读取 `PARKWEAVE_RUNTIME_READ_CONFIG` 的严格JSON配置，调用**原有**受保护 public binding 加载器，再以原 `WriterClient` 核验实际数据库/角色、独立 writer 通道和签名历史。API只持原受限 app 连接与公开 policy/pin，不持 writer DSN 或签名密钥。没有配置时保留原默认关闭；配置出现但无效时启动拒绝，不回退成一个看似可用的 provider。

该 provider 接入原 `Store.assignment_allowed → NativeRunAccess.assignment_allowed → native_run_access_activation.effective` 判断。现有、已独立激活且仍有效的签名 assignment 可以沿原 Run 读取、执行者枚举及分派权限链使用；缺签名、当前授权、有效期或正确来源时仍由原算法拒绝。本片追加同一 preparation/Case/Run、精确服务版本、目录完整来源指纹和实际行 `xmin` 代际的限制，原提交时复核亦经过此判断。仅校验已有 assignment，不创建、更新或重新激活它。

普通加载器固定使用 `read_only=True`。原决定命令、激活入口及 writer 调用入口均拒绝写入；status 的 `enabled=false`、`read_only=true`，当前已有访问是否有效仍来自原签名、期限、来源和权限核验。已经保存的APPROVED记录不是一份新批准。`VALIDATE`/`VERIFY` 使用原只读核验通道；新加载过程不发送COMMAND/ACTIVATE，不延长原期限。

资料页新增四个按钮，使用已读取记录的 Case/Run/服务ID/精确版本作为请求参数，进入原 Run、原分派视图、原 Run READ 访问批准面板，或读取精确目录。它们调用以下绑定读取接口，而非另造办理记录或外围就绪面板：

| GET路径（`/api/preparations/{id}`后） | 实际复用 |
| --- | --- |
| `/runtime/run` | 原Case/Run成功及回执证明、原 `Store.read` 当前权限链与原运行结果视图 |
| `/runtime/dispatch` | 原 preparation 当前范围、原 `service_dispatches.read_preparation` 与原分派面板 |
| `/runtime/access-approval` | 当前只读 provider、原 Run 访问元数据授权、原签名历史与原批准面板 |
| `/runtime/catalog` | 记录所用精确目录版本及当前来源；不选latest替换原版本 |

全部请求携带 `expected_case_id`、`expected_run_id`、`expected_service_id`、`expected_service_version`。错Case/Run/版本返回409；权限拒绝沿原统一403隐藏记录存在性。只读入口复用上片的当前 owner/PREPARE 或原获派专员/REVIEW_ASSIGNED、READ、同园区/企业、当前原专员和目录检查。专员只得到版本元数据，原 PREPARE 才可见的目录来源正文不扩给专员。Run READ、资料权限和批准元数据权限各自保留，不从角色或资料权限推导 Run assignment。

选择/身份改变、编号ABA、迟到200/客户端注入403不会覆盖当前视图；未确认旧操作时拒绝新导航。Run/分派/访问批准仍使用原视图和原权限链。新导航不自动发送POST；原分派的后续显式业务操作保持其已有授权及事务检查。

## 批准边界

本片只读接入**已有 Run READ 访问批准**，不是资源方案批准。普通资源方案 Approval 尚无可用读取契约，因此目录响应明确 `resource_plan_approval_available=false`、`ORDINARY_RESOURCE_PLAN_APPROVAL_CONTRACT_UNAVAILABLE`。原资源方案批准路由的隔离门保持；不读取 IsolatedPlanApproval 对象或 candidate列来冒充普通批准，也没有生产批准开关。

缺普通 provider 时，绑定访问批准读取返回409并指出缺已有受保护 binding；存储或核验通道不可用也拒绝。现有原 owner 的独立 Run READ 或合法 legacy 分派读取继续使用原授权，不能把它们的成功称作新 provider 已安装。签名记录、核验通道与当前有效访问分开判断，拒绝后不自动补权、重发或激活。

## 精确配置与仍缺的真实输入

`PARKWEAVE_DSN` 仍须明确提供原受限 app 连接，无凭据发现。`PARKWEAVE_RUNTIME_READ_CONFIG` 是JSON值，字段如下；多余字段、凭据字段、隔离批准字段、写模式布尔值和相对路径均拒绝。任务没有生成任何真实配置、凭据或受保护文件。

| 字段 | 必须来自的已有输入 |
| --- | --- |
| `schema_version` | 固定 `parkweave-ordinary-runtime-read/1` |
| `binding_path`, `binding_sha256` | 原可信 host 已批准发布的受保护 public binding 文件及精确SHA256 |
| `preparation_id`, `case_id`, `run_id` | 同原 public policy Source 的精确UUID及已存在绑定记录 |
| `service_id`, `service_version` | 该 preparation 已引用的原目录服务和精确版本 |
| `catalog_sha256` | 原目录六字段 `service_id/version/name/source/namespace/qualification` 的原canonical SHA256 |
| `catalog_generation` | 同一实际目录行的 `xmin::text`；不靠恢复相同内容复活旧配置 |

真实运行还缺：

1. 已有有效会话、当前READ及本人PREPARE或原获派REVIEW_ASSIGNED，正确的原Case/Run/资料和原专员。原协议仅接受已有可验证SYNTHETIC本地Case，不把来源真实性或资格标为已核实。
2. 同一实际数据库/集群、OID、app/writer角色及既有安全ACL；原已审Native存储、前缀触发器和读取权限。加载器不安装schema、不执行GRANT、不建立角色或补assignment。
3. 原批准的 host/public policy/pin：实际API UID/GID、IPC组、独立writer UID、受保护路径/依赖、当前socket inode/device、peer PID/启动实例、boot ID、policy SHA及当前VALIDATE/VERIFY通道。已有私有 writer 连接/签名密钥只能保留在原独立writer侧，本API没有其输入字段。
4. 原policy精确指定的既有owner、独立审批者、受益人及其当前权限代际、原UTC有效期；已有签名决定和已激活assignment。当前有效读取通过原核验，撤权/撤销/到期后不复活，不续授。
5. 更进一步资源交付仍缺普通资源方案批准契约、既有批准来源与合法主体接线。Run READ批准和IsolatedPlanApproval均不能代替它。本片未实现正式批准、发布、完整P1–P5办理、部署或生产安装。

`xmin`约束仅用于原物理数据库当前代际，非跨逻辑恢复的永久版本。普通受保护通道当前只支持原Linux实现；Windows不降级到TCP或自报信任，仍未实现/验收。没有上述合法输入就保持拒绝，不能靠测试fixture、环境布尔值、抄旧目录或新建凭据补齐。

## 验证分层与失败

本批最终结果以 `evidence/ordinary-runtime-read-20261017/gate.json` 及同目录JUnit为准。新增测试与旧模块完整回归在同一冻结源码执行，不迁开发成绩。新片独审尚未执行，只有本实例自审；父线程可依据完整冻结SHA独审。

| 层 | 实际证明与界限 |
| --- | --- |
| 已有签名授权核心 | 原自有合成PG、原独立reference writer进程及真实IPC签名核验；普通工厂调用显式注入的host binder，原签名/来源/权限/代际校验不替换。证明现有assignment可沿原Run链读取，命令关闭；**不证明生产root保护或安装** |
| 普通默认启动 | 实际Uvicorn configured_app子进程、Chromium、原已有合成legacy记录，Run/分派/精确目录导航；缺provider准确拒绝访问批准读取；API进程重启、新浏览器仅GET |
| 当前拒绝 | 实际HTTP撤权/跨域/未获派、错Case/Run/服务版本、目录同值更新代际变化、通道停止和重启拒绝；原权限/业务快照保留已撤状态 |
| 客户端时序 | 实际服务器读取后，客户端保留迟到200或注入迟到403，验证ABA和迟到隔离；注入403不充作真实服务端撤权证据 |
| 受保护host | 实际不受保护文件拒绝；真实生产protected binding正向、实际独立UID/安装及Windows均NOT_RUN |

开发首窗26PASS/1FAIL，唯一失败是测试将原Pydantic RunCommand直接交给JSON客户端；修为原DTO的 `model_dump(mode='json')`，不改权限。第二窗31PASS，第三窗36PASS；这些是开发WIP窗口，不称冻结成绩。自审补当前物理库/有效期核验、专员目录投影、导航上下文与稳定收集ID后，以最终冻结全新复验。开发日志/XML保留；临时fixture生命周期沿原测试实现，不声称失败数据库或每个开发源码版本均另存。

首冻结窗 `final-v1` 在125PASS后出现1FAIL及同一用例teardown ERROR：旧浏览器ABA测试的UI断言已过，随后原owner快照读取遇 `connect_timeout=2` 握手超时；原DROP DATABASE因1个残留session拒绝。核验为本轮自己的pytest PID后发送SIGINT，该窗未完成。第二完整窗 `final-v2` 为427唯一项、424PASS/2FAIL/2ERROR，886.28秒；两项FAIL是原链路worker报告 `ModuleNotFoundError: parkweave`，另两项ERROR是旧恢复用例setup握手超时与同一用例teardown ObjectInUse，未计作两个独立用例。第二窗第一窗失败的旧ABA用例已通过。

两次数据库握手超时原因仍未确立；保留PG文件观察副本及原日志，不把环境断开通知认定为致因。观察器只复制本轮自己的PG `data/log`，不导入pgserver、不连接DB、不保持生命周期引用；不保证含最终关闭尾段。未放宽原2秒预算、修改旧断言、终止未知session或强制删库。

已查明两项worker失败是本实例只装requirements、漏掉README要求的项目editable安装；原子进程白名单正确地不继承PYTHONPATH。首次 `--no-build-isolation -e .` 又因Python3.12虚拟环境无setuptools后端而失败，保留完整日志；随后安装项目声明的 `setuptools==80.9.0` 和 `parkweave==0.1.0` editable，原 `minimal_environment` 子进程无PYTHONPATH转发即可导入。源码、权限和进程白名单均未改，重新执行同一冻结13完整模块/427项标准开发环境验证；此前成绩均不迁入。

第三窗的精确命令、PID、开发环境核验和两个证据目录环境变量见 `final-v3-invocation.json`。其中原测试已有的writer证据钩子继续启用，并启用原activation证据钩子保存自有合成数据库快照；这些原钩子会执行其已有只读查询，和上述不连接数据库的PG日志观察器分别记录。没有把观察器描述成真实业务或生产host验收。

## 最终实际结果：完整验证门未通过

同一冻结源码第三窗 **13完整模块、427唯一项，425PASS/2FAIL/2teardown ERROR/0SKIP**，JUnit 860.76秒（pytest墙钟860.77秒）、4原警告。新增31项接口/配置与5项浏览器测试均PASS，36项已包含于427，不叠加开发或前两轮成绩。两项失败各另有teardown记录，因此JUnit有429个testcase元素，仍只有427个唯一节点。收集集合与实际执行集合一致。源码接线已实现，但此分支作为**尚未通过完整验证的待审候选**交付，不把新增测试通过当作整批通过。

| 失败唯一节点 | 实际失败与清理 |
| --- | --- |
| `tests/test_native_run_access_activation.py::test_real_expiry_during_receipt_endpoint_rolls_back_all_business_writes[3]` | 预期回执403断言已通过；随后原 `business(a)` owner快照连接在2秒握手处超时，尚未完成业务不变快照断言。原DROP DATABASE又遇5秒statement timeout。 |
| `tests/test_native_run_access_writer.py::test_verified_recovery_becomes_unverified_when_writer_offline_without_changing_history` | 原 `WriterClient.invoke → Store._guarded_connect` 的app数据库预检连接在2秒握手处超时，调用尚未执行后续VALIDATE/ACTIVATE RPC；未到达本例后续停writer/恢复断言。原DROP DATABASE因1个残留session拒绝。 |

两次握手超时的共同或独立致因均未确立，不宣称产品断言失败已修复，也不以“环境问题”定案。第三窗前两条导入失败节点 `test_whole_ordinary_chain_uses_activation_then_explicit_plan_revision` 与 `test_reference_writer_full_chain_with_explicit_plan_revision` 均实际PASS。源码无新修改，原拒绝、期限和超时预算不变；此后不再盲目重跑整批。剩余验证阻塞是解释并复验这两处超时，以及对本片进行真正独审。

公开入口：[gate.json](evidence/ordinary-runtime-read-20261017/gate.json)、[最终JUnit](evidence/ordinary-runtime-read-20261017/final-v3.xml)、[最终日志](evidence/ordinary-runtime-read-20261017/final-v3.log)、[失败台账](evidence/ordinary-runtime-read-20261017/failure-ledger.json)、[原件与公开副本配对](evidence/ordinary-runtime-read-20261017/public-pairs.json)。原始日志留在本实例忽略的 `.runtime/runtime-read/`，公开文本脱敏源代码常量及一个已核对的历史合成参数组合之外的43字符会话候选；逐件记录原件和公开副本hash，XML/JSON重新解析。715冻结输入与26657继承证据hash零差异；公开截图的会话输入原为password类型，无图像修改。

首版封存完整性校验发现：开发三窗中同一个43字符参数组合 `expected_service_id-SYNTHETIC-other-service` 被误当会话脱敏，正式三窗节点名均未改变。首版封存移到本实例私有 `export-v1-node-id-check-failed/` 保留，原测试日志/XML不改；将该明确由源码字段与SYNTHETIC服务常量组成的参数名加入精确保留名单，重新生成公开副本，复核六窗原件/公开JUnit节点序列与逐件hash。这是封存修正，没有重跑测试或更改成绩；[首版校验记录](evidence/ordinary-runtime-read-20261017/export-v1-validation.json)与两个版本的导出脚本一并公开。

上片CI运行列表已被GitHub API403拒绝，本片遵从停止指令，没有再查询，也未换其它路径获取。仅正常Git分支读取/推送；CI状态未知。Windows/Win11原生、正式AT/AT35、真实身份/来源/批准、真实模型、现实履约、受保护生产安装/部署、完整项目与全仓回归均未验收。无main修改、强推、新费用、凭据、安全网络权限或未知锁/进程清理。
