# 两次不同输入的本地合成体验

先打开同目录的 **LocalSyntheticWalk.html**。这是离线操作卡；产品仍使用原页面。包内 `BUNDLE.json` 的 `source_commit` 是完整源码版本，`SHA256SUMS` 核对全部载荷。两次新事项的空白核对表见 `Comparison.txt`。本包不含数据库、会话、私有 pack/journal 或第三方依赖，不是零准备安装器。

能体验：使用已有合法环境，分别输入两件合成诉求，经各自材料、专员核对、企业确认，下载各自当前材料文本快照，比较编号和内容，刷新后重读。原页面具备条件时可继续读取 NO_MODEL 候选并显式采纳；缺本次 Run 访问即停止。包本身没有实际完成这两次业务操作。

不能据此申领：正式来源、真实业务、资格、线下履约、正式模板发布、Windows 正式 AT，或 AT35 全部通过。已有精确 assignment 的 Chromium P1–P5、多人 DOM 验证不在此包重复执行。

## 安装者先检查

在既有批准的 Python 3.12 环境解压。以包根目录为当前目录；下面的 `python` 必须是该解释器。安装好的运行依赖必须与 `pyproject.toml` 一致，另含 `psycopg-binary==3.3.6`。缺项即停，由环境提供方按已有授权准备；没有自动安装或联网下载。源码模式直接运行，**不需要安装本项目**。

```bash
python scripts/demo_preflight.py --local-synthetic --json
```

这是资产、精确依赖元数据与配置缺项盘点，不读取配置正文、不导入应用、不连数据库。返回 2 表示缺项或拒绝，返回 0 只表示盘点齐备。当前交付环境四项配置均缺失，实际结果是 `BLOCKED_MISSING_EXISTING_INPUTS`。

由既有环境提供方在私有运行环境设置以下**原有输入**；不要把会话、DSN 或私有 JSON 发到聊天、截图或公共日志：

- `PARKWEAVE_DSN`：已有普通 schema 32 的应用身份连接，不能使用迁移 owner、超级用户或其有效所有者成员身份。
- `PARKWEAVE_MODE=LOCAL`。
- `PARKWEAVE_SERVICE_PROFILE=LOCAL_SYNTHETIC_DEMO`。
- `PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG`：原严格配置，指向既有 SYNTHETIC pack 和私有 journal，绑定原始 SHA256、实际数据库、园区/组织、目录哈希与 xmin。字段见 [原接入合同](../F2/LocalSyntheticDemoContract-20261017.md)。不提供伪样本配置。

还须已有当前企业/专员会话、READ/PREPARE/REVIEW_ASSIGNED 等相应 Grant、合法 preparation_catalog、原身份/资源/字段映射及有效期；实际继续办理所需 EXECUTE、资源 READ/HOLD、精确 Run assignment 和批准仍按原业务条件检查。本预检不读取会话，不检查或补造这些业务权利。

当前固定 profile 不接入 `PARKWEAVE_RUNTIME_READ_CONFIG`、`PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG`、`PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG`。检测到它们则停止，交由环境提供方确认运行配置；不要自行删除其他环境的配置继续。

只有已经提供上述原有输入时，才显式运行：

```bash
python scripts/demo_preflight.py --local-synthetic --check-existing-inputs --json
```

它只调用原 `local_synthetic_demo.configure`：每次新连接先设只读事务、3 秒语句超时、1 秒锁超时，再拒绝管理/数据库或 public 关系所有者身份，随后复用原文件、目录、schema32、数据库绑定校验。连接超时沿用原 Store 的 2 秒。它不启动应用、不迁移、不写业务/目录、不装依赖，不修改数据库默认配置。失败输出固定拒绝码，不回显私有错误正文。每条语句有上限，不承诺整次校验总耗时。

成功的 `CURRENT_DEMO_INPUT_BINDINGS_VALIDATED_READ_ONLY` 仅证明**当前输入绑定**；sessions、grants、run_assignment 仍为 `NOT_CHECKED`，`business_ready=false`。文件或目录后续变化仍可能使原启动/操作拒绝。

## 复用原启动入口

仅在已有合法前置环境中操作。端口被占用、无法确认归属或权限不满足即停，不终止未知服务、不改安全策略。两个前台终端均在包根目录，使用同一份既有应用环境：

```bash
# 终端一：原 API 工厂，仅本机回环
PYTHONPATH=src python -m uvicorn parkweave.api:configured_app --factory --host 127.0.0.1 --port 8765
```

```bash
# 终端二：原普通 LOCAL worker，不加 model-fixture
PYTHONPATH=src python -m parkweave.worker
```

这两条是 Linux shell 命令，不是 Windows 已验安装方案。不要执行旧指南中的 `--fresh-fixture`、seed、migrate 或候选审批工厂来补齐本包前置。普通启动不会改数据库结构；启动后的原 worker 与用户明确操作会处理并持久化已有合法业务。worker 会处理该已有环境可领取的任务，须由环境提供方确认其范围。

浏览器打开安装者核实属于本次 API 的 `http://127.0.0.1:8765`，用提供方私下交付的当前合成会话登录。若检查 `/health`，PID 必须对应本次自己启动的 API，SYNTHETIC 标识须一致；健康响应不证明业务授权。关闭网页不会停服务，结束仅在自己启动的两个前台按 Ctrl+C，不停既有 PostgreSQL，不删数据或锁。

## 两次原页面路线

按离线卡依次完成 A、B；它们都是**新事项**，不沿用上次 Case、材料或审核。服务目录若不支持样本目标则记录停点，不修改算法或目录。

| 输入 | 本次资料整理目标 / 诉求摘要（合成） | 材料目录（合成） |
|---|---|---|
| A | SYNTHETIC A：整理厂房设备维护材料，核对三台设备的维护记录。 | SYNTHETIC A：设备清单 3 项；维护记录 2 份。 |
| B | SYNTHETIC B：整理员工培训材料，核对十二人的安全培训记录。 | SYNTHETIC B：培训名单 12 人；签到记录 1 份；课程提纲 4 项。 |

1. 企业在“服务”点“查看可选服务与专员”，选择当前获派专员，输入 A，点“开始资料准备”。等待原 worker；在“协同”→“我的资料准备事项”打开**本次**记录。记录实际 Run、Case、preparation 编号；界面未显示的编号由安装者用已有只读途径核对，不手改数据库。
2. 分别给“诉求摘要”“材料目录”追加本次材料版本，来源明确标为 SYNTHETIC，按原表单选择本人陈述或资料摘录及版本。不要把合成文本标作真实证明。专员本人查看当前材料，点“核对本地资料包”；企业本人再点“确认本地资料准备”。两者独立，权限拒绝即停。
3. 在当前资料页点“生成当前材料文本包”，检查 Case、材料版本、来源与未知项，再点“重新核对并下载文本”。记录文件名、实际 SHA256；保留下载文件。不能下载时记录实际拒绝，不用另一个 Case 文件代替。
4. 可选：在当前事项“查看此事项四步计划”中显式保存本次诉求与支持的必需目标，再从原持久步骤计划入口读取服务能力、生成合成候选。只接受明示 `LOCAL_SYNTHETIC_DEMO`、`NO_MODEL`、唯一合法解的结果；采纳需要用户另行明确确认。未知、多解、当前身份/映射或批准不满足即停。不得把 IsolatedPlanApproval 当普通批准。
5. 核对本 Case 协作入口和本 Run 已有访问。无该 Run 既有合法 assignment 时，记录“资料及下载已完成，后续接单/回执阻塞”，本包到此。已有条件的 P1–P5 操作按原说明进行，不以本包申领重复验收。
6. 结束 A 后从服务目录另建 B，重复 1–5，用 B 的独立材料、专员核对、企业确认和下载。A/B 的 Run、Case、preparation 应各自不同，A 的下载只含 A 内容，B 只含 B 内容。刷新页面、重新输入当前会话，重读各自已有事项和版本。

若当前已采纳计划及逐目标结果视图满足原条件，可点“只读核对逐目标结果”→“生成本次核对包”→“重新核对并下载 TXT”，它再次鉴权/核版本且不写业务记录。按钮不可用或缺前置时记录“本次核对包未生成及原因”；材料文本下载与 Case 核对包分别记录。包不保证每个新事项都能产生后者。

Linux 下载核对示例（路径替换为刚下载的单个合成文件，不用会话文件）：

```bash
sha256sum -- '<实际下载文件路径>'
```

文件中的 SYNTHETIC、真实性未核验、资格 UNKNOWN/PENDING、外部 NOT_SUBMITTED、实际履约 PENDING 等边界应保留。下载文件是当时快照，后续撤权/更新不会追回或更新已下载副本；核对表记录下载时间和版本。

## 停止与交接

403、缺 PREPARE/REVIEW_ASSIGNED、目录或源版本变化、混用 Case、无本 Run assignment、批准未接线、未知来源均准确记录停点，请原环境提供方核对**已有**输入。网络失败或 5xx 先保留原操作、原参数，用页面原结果核对入口；没有该入口或结果仍未知就停，不另发新意图。不得新建身份/Grant/分派/批准、改数据库绕过，或借旧 Case 授权。

最小下一步是由原环境提供方提供已存在且合法的上述运行输入与私下会话，先通过只读绑定校验，再按 A/B 卡操作。若这些前置不存在，本包可运行到离线卡、哈希核对和缺项拒绝，不存在合法业务启动成功的证据。

维护者历史参考：`docs/F2/MaterialReuseDOMValidation-20261018.md`、`OriginalCollaborationDOMValidation-20261018.md`、`DemoOriginalPageIntake-20261017.md`（仓库可查，不随最小包复制全部证据）。原 F2-T07/AT35 的完整闭环、正式来源专用 backend 与真实映射合同、C0 官方模板仍有独立缺口；本包没有补造它们。
