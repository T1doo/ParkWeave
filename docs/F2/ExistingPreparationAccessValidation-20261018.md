# 既有主体 preparation 配置：有限交付验证（2026-10-18）

源码/测试/README/合同冻结 SHA：`c6aa4a9a7693079a96de4c4a9ec031012b48fc7e`；tree：`186fc147a6a43390ca4ce9bffbb5f5966757b27b`。分支 `dev/f1-existing-preparation-access-20261018`，基线 `a9c725babd36561a6a25733953cc374ee1b77bd5`。基线和最初指定 `db1084100a2477bbff3da8b49287c755dbc83c1b` 均是实际 HEAD 祖先。本片未重新证明前片整包，也未声称项目完成。

原方案缺口来自产品设计 §3/§9.3/§11，开发计划 F1-T03/§11/§13：CLI/Windows Setup 原来只有迁移、固定三企业 seed 与撤权，没有供合法既有 owner/reviewer 使用的 preparation 配置入口。具体原文锚点与边界见 [合同](ExistingPreparationAccessContract-20261018.md)。本片提供独立本机 `prepare-access --config`，默认真实只读事务，只引用既有身份、能力和精确原目录；只有实际直连数据库及相关表 owner，明确 `--apply` 与当前计划 SHA，才能 INSERT 缺失的原 PREPARE/REVIEW_ASSIGNED。inactive/错 scope 原键拒绝，身份/能力/目录只校验，不创建、不恢复、不发布。两项权限沿用原 principal/park/org 范围，目录引用不是 Case 专属权限或批准。

入口复用原 Store 当前身份/角色/能力、原目录 proof/known-source 和原 principal/catalog 锁；只调用原 provider 纯拒绝检查，不实例化或签发 IsolatedPlanApproval。原业务算法、schema、roles、conftest 均未变。793 个原 src/tests/scripts/pyproject 文件（排除有意接入的 CLI）逐字节等基线；已有文件另改 README，新增 adapter、测试和合同。普通 API/worker 不自动运行该管理命令。Native 默认 permit/writer 拒绝不变。

根冻结单窗：**38 PASS**，pytest 52.380 秒，外层 56.221109776 秒，exit 0；35 个新增节点加 3 个定向原回归。没有失败、跳过或重跑拼接。源 archive SHA256 `bf85dad32a92339d7546c9efa29f253b6cbd552215f7abedef703a3739ca6b39`。810 输入的 shared/mirror 前后四份 map 完全一致；116 个根 pytest 导入来源均位于固定 mirror，字节哈希吻合。该来源钩子未装入 API/CLI 子进程，不外推为子进程逐模块溯源；子进程固定 mirror cwd/PYTHONPATH，并验证 API health PID 与所拥有 child PID 相同。

| 根新增验证 | 节点 |
| --- | ---: |
| 只读预检、显式两项插入/原审计、旧 SHA 与 NO_CHANGE | 1 |
| 注入写操作被实际 READ ONLY 事务拒绝 | 1 |
| 主体/角色/域/能力/目录/inactive/错 scope 原键阻断 | 10 |
| 普通应用角色不能 apply | 1 |
| 第二审计故障，双 Grant 及首条审计全回滚 | 1 |
| 实际提交后注入连接错误：结果不确认、不自动重放，新预检看到 NO_CHANGE | 1 |
| 实际 PG advisory 等待后撤权/恢复 ABA、目录 ABA 均拒绝旧 SHA | 3 |
| Native/隔离/普通 provider 上下文拒绝 | 3 |
| 严格有界 JSON、重复/未知键/类型/编码拒绝且不回显输入 | 8 |
| 显式 CLI 参数边界，新选项不能触发旧 seed | 4 |
| 普通 CLI＋原资料完整人工流程及 API 冷读 | 1 |
| 补插新权限代际不能复活原 CaseStep marker | 1 |

3 个原回归是 `test_api_full_manual_preparation_confirm_and_reopen`、`test_real_worker_revocation_before_dispatch_and_after_effect[None]`、`test_grant_revoke_blocks_cached_receipt_new_read_and_write_and_seed_does_not_restore`。原受权范围、撤权与旧 CLI 行为定向检查通过，未全量重跑 F1/F2。

普通链节点真实启动 2 个 API、2 个 CLI，先验证缺准备权限的原 catalog 403，再 dry-run 零写入、owner 明确 apply、原 Run/Case 与资料槽补交、指定 reviewer REVIEW、owner CONFIRM 至 LOCAL_CONFIRMED、冷启动读回一致，其他企业仍 403。该节点的 Run 使用测试进程直接调用原 NO_MODEL local finish，worker OS 子进程为 0；身份/能力/action/目录由自有合成 fixture 预置，apply 只增 2 条准备权限及原审计。原始与冷读内容/原能力目录及 Run 分派不被初始化器改写。不是浏览器、Node VM、真实模型、外部材料或业务正式批准测试。

根 3 个并发节点均观察到真实 `pg_stat_activity.wait_event_type=Lock` / advisory 等待，释放前改变原能力或目录代际，旧 SHA 均 Conflict、0 准备 Grant/0 审计；具体 UTC 与原 query 见各 `administrator-wait-proof.json`。没有用 sleep 返回值冒充 PG 等待。提交连接异常节点是“实际提交之后注入 psycopg 错误”的合成探针，没有声称实际网络断连复现。

独审先从原文与合同冻结 16 条 literal oracle（20 个既定输入），再读最终 SHA 的实现；原 oracle SHA256 `af3085d86253e76ffe625757d8b4292d17da64d8e1933c36cbc80f81896c5fb7`。6 个独有私有探针涵盖嵌套重复键与实际 READ ONLY、单缺 Grant/旧行不修复、reason fence 与应用/provider 拒绝、实际能力行 FOR SHARE 等待后的 ABA、第二 INSERT 故障全回滚、旧 marker 冷实例拒绝；另有与根 3 个明确重叠节点。

独审窗1：9 收集，**8PASS/1FAIL**，pytest 47.394 秒、外层 53.1746993400011 秒；失败是私有探针将原 API 必须新增的拒绝审计误纳入“403 后业务摘要不变”。失败之前的冷 ordinary/default ACCEPT403、owner 历史读取、原截止及 marker/xmin 检查均通过，但原首窗失败长 repr 不能反推精确审计行数或声称仅某行有差异。原 `api.py` 拒绝路径和 `Store.audit_denial` 的静态证据支持最小私有修正：业务摘要排除 authorization_audit，并单独验证精确原拒绝审计，同时增加原 dispatch/receipt 表保护。未改产品、原测试、角色、fixture 或权限。

仅补原失败 selector 一次：**1PASS**，pytest 10.312 秒、外层 14.764582 秒；精确观察新增 2 条 executor-a/API_AUTHORIZATION/DENIED，其余业务表（含 dispatch/offer/event/receipt）摘要不变；原 grant generation 735→750，旧 marker 未动，冷 ordinary/default ACCEPT 均403，原截止保留。v1/v2 私有源码与失败 XML 均保全。独审有效 9 节点是首窗 8 加补窗 1，不能称独审单窗 9PASS。

本片合并去重为 **44 个有效唯一节点 = 根38 + 独审9 − 3重叠**，不累计开发窗口或前片节点。独审未发现未解决的实质 P1/P2；审计结论仅限已冻结合同和上述有限场景。独立保护核验 793 原文件 Git blob 与8个原授权/目录算法 AST 相等。两独窗各自810输入及私有 probe源无漂移；每窗114导入来源=113冻结输入+1私有probe，probe两版本分别归因，不能混为产品源码变化。

开发失败保全：首次 collection 因新测试误导入不存在的 dispatch 名称失败，未运行节点；首批 3 节点 2PASS/1FAIL（测试误期望 Run POST=200，原为202）；随后 35 节点 34PASS/1FAIL（测试误读顶层 state，原为 preparation.state）；只修正测试引用/断言，补跑普通链与原资料流程 2PASS。上述开发工作树结果不归属于最终冻结 SHA，不累计为新唯一通过数；日志/XML 原样留存并在公开副本中仅脱敏合成会话。最终 38PASS 是单独同 SHA 窗口。

公开证据见 [归档清单](evidence/existing-preparation-access-20261018/publication-files.json) 与 [独审报告](evidence/existing-preparation-access-20261018/independent/independent-final-review.json)。124 对 raw/public 中116逐字节相同、8份脱敏共8次替换；另3控制文件，总计127公开文件，清单包含自身且精确等于完整文件集合。177个已知自有合成会话完整值/16字符前缀与截断片段扫描均0命中；raw token库、PG data、整mirror及配置输入留在私有目录，公开预期由受测Git fixture源码表达。全部JSON/JSONL可解析，XML节点名与各阶段成败不变。独审74份规范化文件逐字节复制，不二次脱敏；其raw/public映射与根映射保留原归因。

独审稳定报告SHA256 `c0906857d6442dde0c11d65279e0ada6eff067fe9459f60cf899d7681773b36f`；独审公开清单 `8748f8fc0c90839597700fac2a29fb89b760be1d09420d05b2b4c76ff2daa128`；映射 `f82d19a7dd8ae2ac535c3563ca12abd5da460d2cda8bb9fe2002a6cf24856826`；raw manifest `c1acb8a37874f6e8ace60b8712f337b3c3229431508fbd5f1fa5baca8fc8da1c`。根与两独窗共12份810输入map一致，三archive相同。

归档控制器另保留一次非业务失败：首轮123文件集合及哈希/脱敏/XML均通过，最后排序断言混用了Path组件排序与完整相对字符串排序而失败；首脚本、stderr及首公开快照留存。仅统一控制器两侧排序规则后，新一轮完整归档通过，未改受测源码、独审canonical或重跑业务节点。`archive-revision-attribution.json` 明确首轮与修正版本，首轮快照本身不冒称已完成归档。

Git默认网络只读前后预检成功，131个既有heads无新增/删除/变化，main仍 `31e7acb7e53bb1ab6465b9daae59de28757f7583`，新目标分支尚不存在；默认fetch保持 `+refs/heads/main:refs/remotes/origin/main`。交付只正常推送当前新开发分支；post-push实际差异与完整交付SHA由最终私有收据和最终回复提供，不在提交前预称推送成功。

真实运行尚未提供或未完成的输入/代码边界：

- 当前没有对真实数据库或真实主体进行检查/写入。需业务方预先合法存在的 owner/reviewer ID、园区与企业、active 的 enterprise_operator/park_specialist 角色，以及 owner READ/EXECUTE、reviewer READ。能力、真实目录、执行者、资源的建档/导入仍无本片实现；不能把测试 seed 当管理来源。
- 需已有精确 service/version 目录、原 source kind/id/revision、SYNTHETIC/NOT_EVALUATED 与原可用 proof；有 journal 时须当前完整且 ACTIVE，无 journal 的原合法目录仍可用。当前原适配器只支持明确 SYNTHETIC 服务，FORMAL/真实目录来源转换与发布不是补 JSON 能完成的条件，仍缺正式来源协议/接入代码与合法数据。
- 两项原准备权限须已有合法授权来源；本片只交付默认 dry-run 和经独立授权管理员明确应用的代码，不代替该授权。需要实际可用 schema32/33、既有相关表及合法直连 DB/table owner 操作上下文；不接收凭据到配置文件，不在此会话发凭据、改 owner/权限或生产安装。生产迁移的 fixture 边界不能据此视为已解决。
- 原资料准备运行仍需 owner 本人当前可见的 Run/Case、原 action 权限及已完成的本地 Case 创建、两槽有来源材料、指定 reviewer 对当前版本明确 REVIEW、owner CONFIRM。后续 P1–P5 还需当前合法执行者/分派、本人接受和回执、资源/时段/组合等原条件，本命令不生成它们；真实 Native permit/writer 仍默认拒绝。
- Windows 原生启动、正式 AT35、真实组织多角色/目录/材料全链、外部履约及生产安装均 **NOT_RUN/未验收**；本 Linux owned-PG 合成结果不能外推。完整项目仍未完成。

暂存空白检查对原样保留的 patch/XML/终端证据报告16条诊断（含同一位置两类诊断）；未修剪原始证据或独审canonical。源码/合同/README与本验证文档分别检查通过，诊断原件保存在私有 `staged-whitespace-check.log`。

本片所有实际身份、权限、目录和用户操作仅发生于新拥有的 SYNTHETIC 测试库。未新增真实身份/Grant/分派/目录发布/批准/凭据，未改 main、强推、部署、真实模型调用、费用或安全网络权限；未知锁和进程未删除。Git/网络交付收据另存于私有 `.runtime/existing-preparation-access-20261018/delivery-and-remote-verification.json`，正式交付 SHA 在最终回复中给出。
