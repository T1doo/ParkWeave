# 明确授权后的独立合成材料演示

本次在原指定云环境建立**唯一一套**合成演示库和最小业务身份，真实 HTTP 完成两件不同事项的建单、双槽材料、独立专员核对及企业确认；随后同一 PostgreSQL/API/worker 完整重启，原记录和文本均保持。启用沙箱的 Chromium 在业务前启动失败，已停止且未重试，所以原页面交互、浏览器按钮及下载未验。

## 授权与实际状态

2026-10-18 父级提供了具体原问答及明确授权：本次独立演示库、仅本集群应用角色、企业/专员各1、私有会话各1、6条必要业务Grant及1条SYNTHETIC资料目录；不接真实园区、模型、付费或外网。授权不能推及未来任意创建凭据。父级状态询问期间没有再次初始化或并行 writer。

setup **只执行1次**，会话只生成1组。私有目录 `/tmp/parkweave-material-demo-fsnwe42i`，目录0700、文件0600、同一 uid1000；schema32、现场创建观察、原始失败/PG/application日志、旧state版本、会话和4份文本均保留。服务已停止，不存在“当前可以打开的已运行地址”承诺。会话无自动过期，关页面、停服务或目录被称临时均不撤销；撤销与清理另行确认。平台清理/tmp仍可能丢失。

凭据没有回传或提交仓库。原认证仅在本库 principals 存 token 哈希，明文只在私有 sessions 文件。公开证据不复制私有state、sessions、PGDATA或完整数据库日志。公开两份TXT仅含当次合成材料及业务编号。

## 版本、启动与精确范围

| 阶段 | 实际完整源码提交 |
|---|---|
| 开始基线 | `4fa85aac3b8961b35846800597208096c3a2e934` |
| 唯一setup及原schema32迁移 | `4e55fa77caa54bf15715189588c9dcd8fd0b890c` |
| 两事项真实HTTP材料写入与初次文本生成 | `ee4d69adb3d39ad4abcdd7e4e84e6733c2add765` |
| 最终正常重启、只读重读及相同文本 | `24f6db12490b7ba7f01099d311af97e926eeddd0` |

以上均保持原产品src树 `9b21f97b8e25fd9a589e41bb9a3068d7943e0734`；原算法、tests、pyproject、验收规格、ATBindings、DataLedger没有变动。没有把一次旧source运行说成最终source完整重新写入两事项。

[最小启动器](../../scripts/material_only_demo.py)只用已有 Python3.12.14、pgserver0.1.4自带 PostgreSQL16.2、psycopg3.3.6、FastAPI0.142.2/uvicorn0.54.0；无安装或下载。新建私有Unix socket集群，禁TCP监听；普通工厂/worker仅使用新集群的非管理员、非owner parkweave_app，HTTP只127.0.0.1。未新建系统账号，未动未知旧进程或锁，也未开放安全网络权限。

新集群初态精确9行：2 principals、3 capability_grants（企业READ/EXECUTE、专员READ）、1 case.create action_grant、2 preparation_grants（PREPARE/REVIEW_ASSIGNED）、1条SYNTHETIC preparation_catalog。field_grants、Run assignment、资源、资源授权均0，不建执行者或批准。不调用bulk seed、roles.sql、fresh-fixture、schema33、正式provider或IsolatedPlanApproval。

迁移沿用原 capture_fixture_cluster→本次CREATE DATABASE→同进程record_created_database→Store.migrate。保存的 creation-observation 不是可回放receipt，未从JSON重构任何issued对象。重启只读核对系统标识、库OID、schema32、authority与源码绑定，不执行迁移或修复。源码绑定范围为Git src树及启动器字节；本次单writer/干净冻结得到验证，不宣传成通用工作区防篡改机制。

SQL权限只列本次材料/普通worker所需表和列，应用无principal/Grant/目录写权限、无DDL/DELETE、无controlled-plan INSERT。原材料命令的空表FOR UPDATE也要求UPDATE，因此同一库显式补 controlled_plans.invalidated_from/invalidated_at 两列UPDATE，没有扩大业务Grant或建立计划。现场identity/OID/schema、9行authority、creation原字节和原state均保全后才显式修订source pin。

这是普通configured_app的材料路径，`PARKWEAVE_MODE=LOCAL`；未设置LOCAL_SYNTHETIC_DEMO profile。该严格profile另需执行者/资源/pack/journal，本次没有创建它们，也不声称固定包profile预检已通过。

## 两件实际事项及文本结果

| 项目 | A 设备维护 | B 员工培训 |
|---|---|---|
| Run | fa9ed6f5-30dd-4afb-95fa-4f9c889857fe | e820643a-fcae-4dda-8a9f-31834f07092c |
| Case | e8938e0f-eb4c-4eb8-9e4e-e973057a9c95 | e3071650-58dc-42e6-b371-b63cb9aea4df |
| preparation | c754b7f5-df93-4d6a-8aab-9ae20c6d6eb3 | 562f010b-2200-4ee6-9c7a-0e717ed48b08 |
| 最终资料状态 | LOCAL_CONFIRMED / revision5 | LOCAL_CONFIRMED / revision5 |
| 文本bytes | 1832 | 1851 |
| SHA256 | `23155ee525bc0de6bbb77ab32e9b0bdb89fc847921e99aa6a892b448ed0ed9ac` | `663994da635aab152b15c36e4617ec034f27530df857e12893650d2d43d611a9` |

实际HTTP从原 /api/runs 与普通worker建Case，再原preparations/commands逐条写本次材料、专员REVIEW、企业CONFIRM。4条错误角色请求均403，正常操作8条材料/审核命令成功；没有客户端改角色冒权，没有直接SQL写Case/材料。初态业务表全0，最终2runs/2cases/2preparations/4evidence/10events；model_steps/model_plans/Run assignment/controlled_plans全0，9行authority全程不变。

重启窗口9次GET（含原HTML字节核对）无业务POST，企业和专员重新读取各自原资料。原编号、revision、材料、review、状态和readiness响应均一致。PG/API/worker前后PID不同且均为本次owned子进程，正常关闭后postmaster标记消失、stop-unconfirmed不存在。

文本生成仅复用原 web.html 中两个标签常量及纯materialPackText函数，合计4242bytes，片段SHA256 `eae5ebba1f53241613e41fe41ef6445b0ac8b701c857b37fd74f065278a0645b`。它不是完整web/整个script哈希，也未执行原按钮handler、clipboard、Blob或浏览器download。原真实HTTP readiness进入NodeVM，两件分别生成；重启再生成两份，逐字节和各自SHA一致，A/B内容不混用。公开[两份文本及manifest](../../deliverables/material-only-demo-20261018/README.md)；下载副本是当时快照，不代表资格、外部受理或真实履约。

## 实际失败与限制

1. Chromium151 + Playwright1.62启用chromium_sandbox=True，一次启动即TargetClosedError/SIGABRT。原日志明示SUID sandbox helper所有者要求不满足；未加--no-sandbox、未改系统所有者/模式、未重试。业务页未打开，浏览器下载未验。这是本地进程拒绝，不是自动批准审查拒绝。
2. 独审在4e55静读发现controlled_plans空表行锁SQL权限不足，材料命令执行前已修正；同库仅补上述两列权限，没有再次setup/生成凭据。
3. 同次静审发现API/worker停止未确认时marker缺失，ee4d已补；此故障分支仅静审，未人为制造未知存活子进程做故障注入。
4. ee4d首HTTP窗口两业务链及2份文本已完成，随后首次restart在precheck遇OSError，**整个窗口exit1**。原errno未留下，不把后续成功冒称解释了原根因。后续独立bind诊断观察到原方式errno98，SO_REUSEADDR可绑定；24f采用该常规设置并把私有异常记录前置。新source pin在同库只读identity/9行authority/已有2事项验证后显式修订；旧state、creation、sessions原字节保留，不再setup。最终只读重启窗口exit0，没有重发任何原业务POST。

本轮不是pytest或原AT runner测试窗，没有用历史测试总数替代实际两场景；没有重做已具精确assignment的Chromium P1–P5/多人DOM。正式来源、真实园区/业务、C0模板、批准、Windows正式AT与AT35全部仍未验。最小下一步是在具备合法沙箱能力的环境完成原页面和浏览器下载；本轮停止该动作，不扩大安全权限。

独审最终24f及公开证据，35件输入PRE/POST零漂移，开放P1/P2/阻断均0；73项是静态/证据核对，**独立业务测试0**，不与根侧两场景相加。独立重算两case材料、完整review snapshot、readiness source及公开A/B TXT哈希，精确从Git blob抽取4242byte片段。私有DB、会话、creation、私有TXT及重启副本未由独审读取，相应实际证明明确来自根侧。稳定JSON SHA256 `b57efa4435c47e3182a0cbae749664a4e749ade0c8a1f3a3c2dc17bf7fd095e9`。

独审汇总曾把去重后35件输入误预期36，harness exit1；原脚本与失败回执保留，只修计数后exit0，没有执行业务或重跑测试，未掩盖根侧首窗口exit1。

## 留证与远端保护

原始敏感日志留在本次私有目录；可公开的命令脚本、分阶段结果、首失败与诊断、readiness、前后snapshot、纯JS片段和独审归档于 [evidence manifest](evidence/material-two-case-demo-20261018/archive-manifest.json)。公开副本不读取或复制私有凭据。继承33,554证据Git blobs实际字节验证全部不变，未知锁保留。

分支 `dev/f2-material-only-demo-20261018`，开始远端115heads，main=`31e7acb7e53bb1ab6465b9daae59de28757f7583`。正常推送要求所有原heads不变、只新增本dev分支；实际完整交付SHA和显式fetch 0/0见最终回执。无main写入、强推、部署、模型、费用、安装或外网预览。
