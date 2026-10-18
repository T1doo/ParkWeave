# 既有合成服务选择 → 普通 CaseStep → 冷恢复

已完成本轮用户能力：原 LOCAL_SYNTHETIC_DEMO 目录生成唯一 NO_MODEL 候选，经原页面明确 ADOPT 后直接进入原五步办理；原普通 API/worker 完成 P1–P5，并物理停止和重启同一 PostgreSQL/API/worker 后读回。新增窄模式 `LOCAL_DEMO_CURRENT_PREPARATION`，原 CURRENT_PREPARATION 的互斥不变。不是正式业务批准、F2-T02/T07 全部完成或项目完成。

基础 `f16d9cf7895e31ad7aab7594494c90bb1e8fa7fb`；最终受测源码 **`3f5fd029f335d132d9baecb79165b86e2159761a`**，交付只再增加本说明和证据。分支 `dev/f2-local-demo-case-step-chain-20261018`。合同与用法：[组合合同](LocalDemoCaseStepChainContract-20261018.md)。

## 接入及边界

精确 OrdinaryCaseStepAssignments 与独立 LocalSyntheticDemo/Catalog/Selector 在同 Store、同 catalog 对象配对；目录/选择/采用接入原普通受管事务，保留原全部最终检查。事务前后核原 hash-pinned pack/journal、私有 journal、DB、schema32、目录 hash/xmin 与有效期，parent 与既有 owner/reviewer/park/org 一致，执行者限定原包中的既有映射。历史读取/停止保持原最小权限，不统一强加所有执行权限。

未改原有限选择、注册图、ADOPT、P1–P5、恢复、worker、原 HTML、roles/SQL/schema/Native 算法。新模式不是 V4/真实模型启用开关，没有 fixture Approval/permit、Run assignment 或发布权；其他 Native/isolated/formal/Approval provider 继续拒绝。serve 的可选 `--local-demo-config` 只读既有文件，setup 不生成或修复这些来源。真实业务缺批准或合法来源仍拒绝。

## 最终实际验证

冻结镜像 **13 唯一 PASS，0 FAIL/ERROR/SKIP**；JUnit **105.774 秒**，外层 **109.291 秒**。815 项输入在共享目录/镜像的前后四份 hash 表完全一致；119 个产品及测试模块均来自该镜像，内容 hash 全符。根测试与独审不相加。

| 用例范围 | 最终节点 |
|---|---:|
| 新选择→原页面明确 ADOPT→完整原 P1–P5→物理冷恢复 | 1 |
| 新精确配对、事务尾部来源变化回滚、PREPARE/REVIEW_ASSIGNED 缺失、parent/executor 映射 | 5 |
| 原 CURRENT_PREPARATION 六种 provider 环境互斥 | 6 |
| 原单独 demo 默认关闭与隔离类型不可替代 | 1 |
| 合计 | 13 |

完整链使用原启动器的新 SYNTHETIC 空业务现场，原34条合成初态不扩展；读取这些既有主体/资源/目录后，测试在启动外准备3份明确合成输入 JSON（pack/journal/config）。普通实际 worker 新建一个 Run/Case，原 API 输入新诉求、两槽材料与 REVIEW/CONFIRM；原完整页面 NodeVM 只发一次选择和一次明确 ADOPT，未勾选不发送，五个原办理入口可见可用。P2 原两资源组合/关联，P3 专员 OFFER/执行者本人 ACCEPT，P4 人工 SUBMIT/owner ACK，P5 明确 REVALIDATE/CLOSE_LOCAL_RECORD/VERIFY，五目标为 LOCAL_OUTPUTS_VERIFIED，case_goal_completed=false。

完整链无 Store.finish、无模型 fixture；只有权限负例等旧 fixture 使用原合成辅助建单，与实际 worker 全链严格分开。普通启动及办理没有新增身份/Grant/目录/批准/凭据或 Run assignment 行；原34条合成初态由测试启动外的原 setup 新建。原权限与 state/session/input 文件 hash 不变。物理冷启动后三个 PID 均改变，原计划/结果等值，原 key 返回 COMMITTED、同 candidate ID/producer，原绝对期限不变；冷请求全部 GET。原 TXT 逐字节一致：16512 字节，SHA256 `e8213c79d88a15a67270d0e057c9409b0dd40cd8961f6a93b1a86f45e1e3f2e0`。

本轮未动态重跑旧锁等待窗口；沿用原3秒 lock_timeout、20秒 HTTP 和300秒期限，没有加时或绕拒绝。全链通过不关闭历史 HTTP 超时 UNKNOWN。

## 独审与保全

独审先对基础及原三合同源盲冻结10条 oracle，最终仅静态审查上述完整 SHA，产品 import/独立动态测试均 **0**，无开放 P1/P2。初版 `3b559f9340f2b6b958ded600f2a161269d67cf5c` 根13 PASS 后，静审发现另一 exact catalog 对象能借用已配对事务的字面缺口；补 `.catalog is self` 检查及负例后，最终重新验证13节点。初版通过数不累加，也不迁签到最终版本。静审仅从条件推出缺口，没有声称动态越权反例。

保留开发首轮1 FAIL/2 ERROR：NodeVM 未提供 URLSearchParams，且测试 runner 把 fixture basetemp 放在 /workspace，被原 owned `/tmp` 证明拒绝；未削弱该门。第二轮2 PASS/1 FAIL：全链与配对通过，回滚断言以无 SELECT 权的 app 读取 authorization_audit；改用原 fixture owner 做只读断言，未增权。第三轮5 PASS/1 deselected，只复验修正负例。断线首次 exec 进程未启动，只读一次重试恢复；核对文件/HEAD/进程/唯一写者，未知锁/僵尸未动，默认网络复读136 heads无变化。第一次归档漏3份 `.diff`，已补齐，原归档私有保留。

公开证据154文件，151 raw/public 对：150逐字节同、1份开发输出删除截断合成会话参数行；264个已知测试会话的完整值及16字符前缀扫描0命中，XML 节点/失败结果不变。包含明确合成输入 JSON；不包含原会话/凭据文件。独审24份清单文件及清单本身共25份逐字节保留。原件、失败和自有现场路径保存在 `.runtime/local-demo-case-step-chain-20261018`；未打包 PG 数据。

源码/测试/脚本/合同的 diff-check 通过。交付暂存检查仅保全证据有109处原始空白告警，全部定位在本轮 evidence 子树，没有修剪原日志或独审 diff。

- [最终根校验](evidence/local-demo-case-step-chain-20261018/runtime/root-verification-3f5fd029.json)、[JUnit](evidence/local-demo-case-step-chain-20261018/runtime/frozen-3f5fd029/results.xml)
- [源盲 oracle](evidence/local-demo-case-step-chain-20261018/independent/literal-oracle-plan.json)、[最终静态独审](evidence/local-demo-case-step-chain-20261018/independent/independent-final-review.json)
- [文件清单](evidence/local-demo-case-step-chain-20261018/publication-files.json)、[raw/public 映射](evidence/local-demo-case-step-chain-20261018/raw-public-redaction-map.json)、[归档核验](evidence/local-demo-case-step-chain-20261018/archive-validation.json)

## 真实运行尚缺的合法输入

必须由调用方已有：获授权 app DSN/普通 schema32；精确 SYNTHETIC preparation_catalog 内容及 xmin；已有三角色身份/会话、owner 原 case.create 与 READ/EXECUTE/PREPARE、reviewer READ/REVIEW_ASSIGNED、executor READ；原两资源及 READ/HOLD；原字段/服务映射、有效 pack、私有 journal 和精确 DB/hash 配置；用户新诉求、材料及原明确 REVIEW/CONFIRM/ADOPT。新模式要求没有 Run assignment/Native 历史，不能拿旧隔离批准替代输入。真实源或严格批准链仍缺其自身合法协议/批准输入，demo 不提供它们。

未验 Windows、真实浏览器正式场景、正式 AT、真实模型/真实业务或完整 F2-T07 反馈链。旧平台标记动态窗未重试，旧 HTTP `UNKNOWN_OPEN` 保留。不改 main、不强推、不部署、不新增费用/安全网络权限。实际交付完整 SHA、远端分支数量与 main/祖先/工作区差异以最终 Git 回执为准。
