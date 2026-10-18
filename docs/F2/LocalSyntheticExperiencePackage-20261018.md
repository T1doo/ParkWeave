# 固定版本 LOCAL_SYNTHETIC_DEMO 用户体验交付

本切片把已有原页面、普通启动工厂和 worker 整理成可下载的**源码体验包**，包含当前 profile 的启动说明、两次不同输入的短卡、空白比较表及下载核对方式。没有新建数据库或补造批准。当前环境缺四项运行配置，交付到离线包与准确拒绝边界；两次业务路线是操作说明，未宣称已在本环境完成。

## 交付物和固定版本

- [下载 ZIP](../../deliverables/local-synthetic-demo/ParkWeave-LOCAL-SYNTHETIC-33bf2efa125e.zip)，940,079 bytes。
- 外部 SHA256：`a6bdbe2846415d585653d92668faca2784328667f06f652c275b8c3b20736b9b`，同目录 `.zip.sha256` 可核对。
- 包对应完整源码提交：`33bf2efa125e5d3b7b59e30b3ea153b9d58a113a`。
- 起点：`7699c112e7a200a26734a274b3a7fc1852f4eca9`，继承 `db1084100a2477bbff3da8b49287c755dbc83c1b`。
- [离线操作卡](../demo/LocalSyntheticWalk.html)、[当前启动与停止说明](../demo/LocalSyntheticExperience.md)、[原输入合同](LocalSyntheticDemoContract-20261017.md)。包根 `START_HERE.txt`、`Comparison.txt`、`BUNDLE.json`、`SHA256SUMS`。

188 项载荷 = 184 个提交内文件 + 4 个生成文件。184 文件中 178 个为完整原 `src/parkweave` 源码/运行资源，另有 pyproject、预检/打包工具、两份当前说明及原接入合同。包不含第三方依赖、`.git`、`.runtime`、`.env`、数据库、会话、私有 pack/journal 或测试 setup 启动器。保留原项目源内 SQL 运行资源，但普通包入口不执行初始化、迁移、seed 或角色创建。源码模式无需安装本项目；也未制作或声称完整离线依赖安装包。

构建仅用标准库和 `git archive` 读取一个完整 SHA 的白名单，不取共享工作区字节；拒非普通文件/越界路径，以 exclusive create 保留旧产物。ZIP 时间戳、顺序和压缩参数固定。原包与重复构建逐字节一致；每个源码文件对照 Git archive，每个载荷对照 SHA256SUMS；解压后检查没有改动任何载荷。

## 用户能做什么

在已有合法环境中，原页面分别新建 A 设备维护事项、B 员工培训事项；两套不同文本、不同 Run/Case/preparation，分别追加双槽材料，专员独立 REVIEW，企业独立 CONFIRM，分别下载当前材料文本并记录实际 SHA256，刷新后重读。版本/正文/编号应相互独立。

原页面条件具备时才读取 NO_MODEL 唯一候选并另行明确采纳；原 Case 核对包还需当前计划与逐目标结果视图，不具备就记录“未生成”及原因。材料文本包与 Case 核对包分开记录。没有本 Run 既有合法 assignment 时准确止于接单前，不借旧 Case，不新增 assignment，不保证完整 P1–P5。

已有原页面/Chromium 证据引用 [MaterialReuseDOMValidation](MaterialReuseDOMValidation-20261018.md)、[OriginalCollaborationDOMValidation](OriginalCollaborationDOMValidation-20261018.md)、[DemoOriginalPageIntake](DemoOriginalPageIntake-20261017.md)。本轮不重做已有精确 assignment 的 P1–P5 或多人 DOM，也不将历史 PASS 计为本轮测试。

## 当前真实停点与最小下一步

Python3.12 与六个精确依赖元数据满足，但下面四项当前全部缺失，且未输出其私有值：

1. `PARKWEAVE_DSN`：已有 schema32 的普通应用身份，非迁移 owner/管理员。
2. `PARKWEAVE_MODE=LOCAL`。
3. `PARKWEAVE_SERVICE_PROFILE=LOCAL_SYNTHETIC_DEMO`。
4. `PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG`：已有 SYNTHETIC pack/私有 journal 的绝对路径、原 SHA256、实际数据库绑定、园区/组织、目录哈希与 xmin。

真正业务还需要原有当前会话、身份、READ/PREPARE/REVIEW_ASSIGNED 等 Grant、合法 preparation_catalog 及身份/字段/资源映射；继续办理还需其原 EXECUTE/资源 READ-HOLD/精确 Run assignment 与批准前置。本轮没有读取会话，也未验证或创建这些权利。现有 NativeRunAccess permit/writer 默认拒绝、普通批准 provider 缺口保持；IsolatedPlanApproval 不进入普通批准。

下一步由原环境提供方在其私有环境交付**已存在且合法**的上述配置与会话，先显式执行只读绑定检查，再按 A/B 卡操作。若没有这些前置，只能使用离线卡、包哈希核对与缺项拒绝，不存在合法业务启动成功的证据。正式来源专用 backend/真实映射仍需具体合同，C0 官方模板未得；本包没有编造。

## 预检行为与验证范围

旧默认库存保持原义。新增 `--local-synthetic` 只看资产、固定依赖元数据和配置缺项；只有再加 `--check-existing-inputs` 才可导入原 `local_synthetic_demo.configure`，不用 `configured_app` 做只读检查。该 probe 专用 Store **每次**连接先 READ ONLY、statement_timeout 3s、lock_timeout 1s，再检查 current/session 有效管理、DB/public 关系所有者成员身份并拒绝；原 connect_timeout 2s。失败固定码，不回显私有异常。

成功也只叫 `CURRENT_DEMO_INPUT_BINDINGS_VALIDATED_READ_ONLY`，sessions/grants/run_assignment 仍 NOT_CHECKED、business_ready=false。真实只读 SQL/角色检查/合法文件绑定的正向数据库运行**未验**，因为当前没有合法输入；标准库替身验证连接顺序/拒绝/关闭不替代真实 PG 证据。

| 本轮最终源码实际检查 | 结果 |
|---|---|
| 私有冻结镜像 `tests/test_demo_preflight.py -v` | root 13 PASS，0 F/E/S，1.701350983s；原6 + 新7 |
| 原源码/静态卡/预检测试镜像 321 文件 | POST 字节对照 Git archive 一致 |
| ZIP 188 项、184 源码、内部/外部 SHA256、重建 | 全部一致，解压载荷检查后无变化 |
| 解压包 local inventory | exit2；四配置缺失，database NOT_PROBED |
| 解压包显式 check-existing-inputs | exit2；缺项先拒绝，database NOT_PROBED |
| 原 uvicorn configured_app --factory | exit1；PARKWEAVE_DSN required，未成功启动 |
| 原普通 worker | exit2；PARKWEAVE_DSN required，未进入业务处理 |

独审在最终33bf的另一私有 Git archive 镜像实际运行同一模块：**13 PASS，0 F/E/S，0.668676784s**，逐ID与 root13 全部重叠，唯一覆盖仍13。321输入 shared/mirror PRE/POST及结束再核零漂移。独立实读 ZIP 188 项/184源码/178产品文件与187个内部校验和，并在其解压目录实跑空应用环境显式预检，exit2、四项缺失、database NOT_PROBED。独审未重复构建ZIP，也未启动 API/worker；根侧重建和启动拒绝证据独立列明。

独审开放 P1/P2/阻断均0；稳定JSON SHA256 `1efa827e45aa9edb078fc2c02eb300b4f6b05fa563158fb7e15112a89e2e23ee`。独审 c047 首准备在 HEAD 守卫中止，exit1、0tests、未创建镜像；原trace另存，没有冒称执行旧13项。

没有执行 PG、fixture setup、浏览器业务、真实模型或形式 AT runner。原完整 runner 的历史 SOURCE_BINDING 拒绝及0tests不变；本轮未重跑、未改 runner/分片/ATBindings。离线 HTML 只做结构/本地链接/实际产品文案/CSP 检查，没有冒称浏览器打开或业务操作通过。

## 失败、保全与范围

开发首轮 SQL 三引号语法错误，exit1、0tests；修正后开发13PASS。第一次冻结 c047b9683f6808c9e22f2badf891695f2112b7fd 的 root13PASS及包保留；独审指出 --help 文字需解释显式数据库只读例外，仅修正文案后冻结33bf并重新完整检查。早期与最终同名用例不累计为额外唯一覆盖。

一次保护路径只读 Git diff 误写基线 SHA，exit128、0tests；正确完整 SHA 的单次修正检查通过，无代码变动。原始输出、纠正回执均保留。

产品 `src` 树仍为 `9b21f97b8e25fd9a589e41bb9a3068d7943e0734`，178 文件/3,273,341bytes；算法、pyproject、验收规格、ATBindings、DataLedger 未改。继承33,467 evidence Git blobs 实际字节核对全部一致，未知锁保留。root 为唯一共享写入者，既有独审仅私有镜像与独立证据写入，没有新增并发 writer。

分支 `dev/f2-local-synthetic-experience-package-20261018`。起始远端114 heads，main=`31e7acb7e53bb1ab6465b9daae59de28757f7583`；正常开发推送保护要求所有原 heads 不变、只新增本分支，并显式 fetch 核0/0。最终完整交付SHA与实际远端差异以最终回执为准。无main改写/强推/部署/费用/凭据或安全网络权限扩张。

F2-T07/AT35 仍是完整项目目标：本包只完成固定版本体验交付切片，未解决正式来源/真实业务/正式模板、全部 AT35、Windows/Win11 正式 AT。隔离合成测试、普通已有合法输入、真实业务缺口严格分列。

原始日志、逐ID、镜像/包清单、首轮失败与拒绝、实际命令和独审稳定JSON归档于 [本次证据](evidence/local-synthetic-experience-package-20261018/archive-manifest.json)。它记录每个原文件与公开副本的字节数/SHA256；原始文件仍保留于本地 `.runtime/local-synthetic-experience-package-20261018`。实际推送后回执 `delivery-and-remote-verification.json` 留在该本地目录，避免报告提交自引用自己的 SHA。
