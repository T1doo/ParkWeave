# 园合 ParkWeave

独立园区企业服务项目。设计原件及动态入口：[docs/Plan.md](docs/Plan.md)。本次为F1有界工程增量，包含合成身份、V1最小契约结构校验、持久Run/Operation/outbox、可信本地建单与事实一致性核对；未通过完整F1、PR0或赛事验收。

浏览器有“服务/协同/资源”三个入口。创建诉求返回202+run_id；独立worker在PostgreSQL短事务内创建Case、核验本地回执并写outbox。Run可SUCCEEDED（LOCAL_CASE_CREATED），Case仍NEEDS_INPUT，外部受理NOT_SUBMITTED、线下履约NO_EVIDENCE。不能把本地建单称作办成全部诉求。

所有数据为SYNTHETIC；模型没有启用，不存在真实模型调用或开发模型兜底。默认可信动作case.create/1与facts.assess；显式测试模式可使用fault.record。无资格裁决、预约、文件导入、Shell/SQL/生成代码执行或外部动作。普通目标文字仅作为数据保存并通过textContent显示。

## 已测试的Linux工程路径

本云环境Python 3.12.14、PostgreSQL 16.2、依赖精确清单见requirements-linux-evidence.txt。这是Linux证据，目标Windows 11 x64精确版本、安装权限和原生服务测试均BLOCKED。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-linux-evidence.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
# 显式合成测试服务器：本机8765；API与worker为独立进程
.venv/bin/python scripts/linux_fixture_server.py
```

测试依赖pgserver只提供临时Linux PostgreSQL，不能当作Windows安装器。测试创建临时数据库并删除；harness使用独立`.runtime/smoke-pg`保留合成状态，Ctrl+C停止API/worker/测试数据库。不连接用户电脑或Sim2Act。

访问http://127.0.0.1:8765，在页面输入`.runtime/synthetic-sessions.json`里的一个合成会话。该文件由显式setup生成，随机token不打印、不提交；三个身份属于两个园区、三个企业。刷新页面需重新输入会话。新会话不是园区真实登录；默认seed为企业经办合成角色；测试另有服务专员、资源管理员、服务执行者。其他角色需显式同企业/园区单Run授权，且只见最小状态，不见回执/全企业材料。已有region/employees/service_need的READ/WRITE字段Grant（SERVICE_PREPARATION用途）；CaseStep办理授权仍属F2未启用。

浏览器测试需agent-browser 0.38.2及Linux `/usr/bin/chromium`；运行`python scripts/browser_smoke.py`前需harness存活。截图仅留在忽略的.runtime目录，非交付要求。

## 目标原生部署接口（尚未Windows验证）

安装并配置独立PostgreSQL数据库`parkweave`及迁移owner；配置独立应用角色`parkweave_app`，由安装者设置仅本机认证。项目不查找隐藏凭据，不生成持续账号凭据。迁移/seed使用owner，API/worker只用应用角色。

```text
PARKWEAVE_DSN=<显式提供的迁移角色连接配置>
python -m parkweave.cli migrate
在该独立数据库由owner执行 src/parkweave/roles.sql（应用角色须先存在）
python -m parkweave.cli seed-synthetic
PARKWEAVE_DSN=<显式提供的应用角色连接配置>
python -m uvicorn parkweave.api:configured_app --factory --host 127.0.0.1 --port 8765
另一个进程：python -m parkweave.worker
```

应用角色仅SELECT身份表及SELECT/INSERT/UPDATE业务表，无DDL、身份UPDATE或DELETE权限。CLI撤权需owner执行`python -m parkweave.cli revoke --principal fixture-a`。身份、能力、字段、指派的owner变更必须遵守同一principal独占锁；当前API/worker用共享锁复核，禁止绕过锁直接修改身份或Grant。测试中的owner配置用于合成初态，不是开放给客户端的管理API。

API默认本机8765，与Sim2Act端口不得重用。数据/会话/日志位于独立.runtime，禁止生产数据；本增量没有模型账号、调用预算或共享配额协调器，所以真实调用始终禁用。关闭网页不影响存活worker；停止进程/关机后本地执行停止。无公开部署。

限制及测试范围：[docs/F1/TestSpecification.md](docs/F1/TestSpecification.md)。Windows Doctor/Setup/Start/Status/Stop/Test.ps1、完整多角色授权、真实模型预算、真实外部连接和资源事务将在后续独立增量实现；不得把当前子集通过外推为完整AT PASS。

F1 ENG-002增加了测试专用FAULT_INJECTION持久账本及计划重复/规模/引用边界。它不注册API动作，Store.migrate不会安装fault-schema.sql；只有隔离测试库显式安装。模拟远端与操作账本分事务，回执丢失后按操作ID核对，未知不重发；不是外部系统集成或线上效果。新增映射与限制见F1/TestSpecification.md，完整AT仍NOT_RUN。


## ENG-003 正常worker中的故障核对（合成工程）

正常worker现使用ExecutionGateway。迁移002保留历史数据，版本2新增DISPATCHED/OUTCOME_UNKNOWN/RECONCILING及控制意图；未知操作只能核对，不能重派发。取消/暂停在途动作后仍核对，回执保留已知模拟效果，不宣称撤销；单步已核对操作不能再次resume。三次自动未知观测后停止自动查询，当前有权用户可用“核对结果”按钮或POST /api/runs/{id}/reconcile再次查询，仍不重发。派发响应未知也计入三次观测。

显式开启合成故障测试：`python scripts/linux_fixture_server.py --fault-fixtures`，它仅在独立合成数据库授予fixture_effects权限，并对API和worker设置PARKWEAVE_MODE=FAULT_INJECTION。默认LOCAL模式拒绝API fault.record并跳过故障任务，即使数据库已有测试权限。正常roles.sql不授予该表写入；勿在真实业务数据库启用roles-fault-fixture.sql。

`python scripts/gateway_smoke.py`通过实际HTTP与连续独立worker验证响应丢失后持久核对，产出ENG-003证据。worker的--fault-stage after-dispatch/after-effect仅在FAULT_INJECTION模式允许，用来在确定的事务窗口退出75，模拟失联；无网络或真实外部效果。目标Windows仍未实测。

旧fault_ledger.py是ENG-002独立对照原型，不是当前执行路径；当前路径为API→runs/operations→worker→ExecutionGateway。本地建单和故障核对共用当前身份、租约、fencing与账本网关。fault.record成功范围仅FAULT_INJECTION_EFFECT_KNOWN，不创建Case或代表服务履约。


## ENG-004 心跳、事实与当前字段授权

worker对每个claim运行独立LeaseKeeper线程，使用独立短事务连接，每租约1/3（最长5秒）续租。数据库当前时钟、fence和当前身份/字段Grant仍是写入权威；过期或撤销后不复活租约。`--mock-model-wait-seconds 3.3 --lease-seconds 1`仅用于模拟无真实模型调用的长等待。取消/撤权可中断该等待；心跳失败关闭派发权，不打印异常凭据。真实模型长请求尚未验证。

`POST /api/facts`持久保存带来源、片段、单位、有效期、Evidence ID/指纹的自述合成事实；三个受控字段region/employees/service_need，每字段最多16条，不覆盖冲突来源。请求体不能指定园区/企业/身份，实际范围由会话决定。`GET /api/facts?fields=region`及`GET /api/facts/{id}`重验当前READ Grant；WRITE与READ独立。owner CLI撤回：`python -m parkweave.cli revoke-field --principal fixture-a --field region --capability READ`，seed不会恢复被撤销权限。正常应用角色不能改Grant。

`POST /api/runs`提交`{"action":"facts.assess","goal":"合成核对","fact_fields":["region","employees"]}`。实际独立worker按当前READ Grant核对全部请求字段，撤权后安全失败。结果为事实一致性KNOWN/UNKNOWN及证据来源，不是资格TRUE/FALSE；缺证据、冲突、过期保留UNKNOWN，qualification_decision=NOT_EVALUATED。技术Run成功范围仅FACT_EVIDENCE_ASSESSED，不创建Case/不代表服务履约。旧回执读取也重验当前字段授权；已发送到用户的历史资料无法本地收回。

`POST /api/contracts/service`与`POST /api/contracts/plan`使用parkweave-domain/1.0-draft完整V1最小必备结构（有效期、材料/资源、处理策略与来源、输入输出/检查/限额、依赖锁等）。当前可信服务动作仍限case.create；只做STRUCTURE_ONLY校验，不核验声明审核人身份，不发布服务、不开放预约/计划执行。旧0.1投影作为历史测试类型保留，不冒充完整V1。

用户确认Windows11系统家族，精确版本/架构与原生实测仍BLOCKED。F1完整AT未通过，未进入F2。真实企业资料、真实模型配置与预算仍待确认。

## 模型token变量名称兼容（LIVE禁用）

读取助手resolve_intern_token显式接收环境Mapping：非空PARKWEAVE_INTERN_API_TOKEN优先，INTERN_API_TOKEN作fallback，返回SecretStr或None。仓库此前没有项目专用token读取器，本次首定义该项目名；通用名按父任务协调。测试只用虚构值，不打印真实值、不读取任何.env。当前API/worker没有调用此助手或真实模型；配置名称兼容不等于安全注入完成，不能越过预算/总配额门。


## ENG-005 授权、outbox和逻辑文件边界

Schema4/5非破坏迁移增加绑定park/org的当前能力/动作Grant、单Run状态指派、LOCAL_INBOX交付记录、逻辑文件资源与最小脱敏拒绝/消息审计。有效权限交集：当前身份+服务端角色上限+当前能力Grant+园区/企业及owner/获派Run范围；执行再交集可信动作/当前动作Grant/运行身份（fence与租约）及所需字段Grant。没有CaseStep或正式服务发布执行，不把Run状态指派当成F2完整协同。

正常worker消费outbox时复核当前READ/字段授权，无权事件SUPPRESSED，不生成可读交付；已READY交付撤权后API立即403，worker后续清空payload并RETRACTED。同事件去重、投影单调版本、ack前回滚。`GET /api/messages/{event_id}`仅本地站内状态记录，不连接邮件/短信/Slack；历史已传给客户端的副本无法收回，不能据撤回宣称外部发送已撤销。

文件默认禁用。显式PARKWEAVE_FILE_ROOT需绝对私有根，owner仅可用register_synthetic_file登记≤16KiB的UTF8纯文本合成fixture；无用户上传/任意路径/原始宿主导入入口。`GET /api/files/{UUID}`重验当前FILE_READ、READ、own scope及相关字段Grant，下载attachment+text/plain+nosniff+sandbox，不渲染动态HTML；内容/大小/hash核对，Linux目录descriptor逐组件O_NOFOLLOW，拒绝symlink/hardlink/非普通文件。未验证的平台文件backend关闭；Windows重解析点/ADS/ACL原生测试NOT_RUN，不以Linux拒绝字符串代替。文件/数据库写入是合成setup，不是已验收的通用文件产物提交协议。

跨平台目标：响应式网页用于Windows/Mac/Android/iOS浏览器；后端仍以Windows11 x64原生为主验收。Mac本地Python/PG兼容需独立验证，手机连接已运行且获授权的后端，不承诺手机运行数据库或原生App。本轮仅Linux Chromium桌面和320/390像素视口模拟，无手机/Mac/Windows实机证据；按钮≥44px、无水平溢出。保持127.0.0.1，不启动公网或更改防火墙。

模型LIVE仍关闭，预算0；其他项目的模型成功不证明Park成功。将来模型身份仅兼容已知同型号intern-s2/Intern-S2大小写，其他型号仍须拒绝，不能删除身份校验。详见F1/ENG005-Mapping.md及TestSpecification.md。


## ENG-006 生命周期、固定验收汇总与离线模型边界

首次体验见[docs/首次体验.md](docs/首次体验.md)，逐条F1交接见[Checklist](docs/F1/Checklist.md)。六Windows脚本位于scripts/windows：Doctor/Setup/Start/Status/Stop/Test。只支持原生Windows、localhost、独立.venv-windows；已有配置不覆盖、已撤权会话不恢复、外部进程不终止、不停止PG服务、不关安全策略。脚本是尚未原生实测的候选，requirements-windows-candidate仅候选直接依赖，不是Windows精确锁。

`python scripts/run_acceptance.py --report .runtime/engineering-acceptance.json`运行完整工程回归，并按docs/F1/ATBindings.json绑定42固定AT/EX定义，分别输出工程子集与完整NOT_RUN。`--ids AT-04,AT-19`只跑所绑定子集，不把缺用例/跳过记PASS。完整错误/JUnit留私有.runtime，公开汇总只有分类/计数/源码hash；原Windows/LIVE门不自动签收。

intern_adapter.py只用明确MockTransport测试官方非流式HTTP形状，真实传输/live_complete拒绝；本地离线预算不是共享实账，API/worker未接入真实规划链。已知Intern-S2/intern-s2 ASCII大小写同名接受，其他型号/Unicode近形/截断/未知工具拒绝；不会执行生成工具或丢响应盲重试。模型真实调用0，详见ModelBoundary。

审查修复：文件根/既有files目录和文件须当前POSIX属主且group/other无权限，0777/0755拒绝，不自动chmod/chown；新files0700、fixture0600。Windows既有ACL只读检查，不借POSIX位推定安全，原生backend仍关闭。所有受控测试/启动子进程用OS项白名单+显式项目配置，不复制全os.environ或转发无关密钥。安全说明见SecurityConfiguration。

F2资料准备并行切片：参见[首次使用](docs/F2/FirstUse.md)与[开发边界](docs/F2/Plan.md)。企业带来源补件→获派专员人工核对→企业确认/重开，全部SYNTHETIC本地业务；F1未签收、Windows未验证、资格未判定、生产R4关闭。当前GitHub Actions访问阻塞不妨碍本地使用。
