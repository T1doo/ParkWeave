# Catalog-only 单次实际验证结果

本次限定验证 **PASS：13 PASS / 0 FAIL / 0 UNKNOWN / 0 NOT_RUN**。原公开仓库 `T1doo/ParkWeave` 的免费标准 `ubuntu-24.04` runner 只运行一次，job 上限 15 分钟；[run 38338357467](https://github.com/T1doo/ParkWeave/actions/runs/38338357467)、job `115103499255` 均 success，`run_number=1`、`run_attempt=1`。平台记录开始 `2026-10-13T02:44:50Z`、完成更新时间 `02:45:11Z`。没有重跑、dispatch 或第二次试探。

| 提交 | 完整 SHA | 用途 |
| --- | --- | --- |
| 冻结源码 | `17cf9cdbff28ae759e68b7f66878e1c396ec6f0d` | 已完成纯测与独审的六文件候选 |
| 审查父提交 | `30979849d960a83c9ac4e3e7058072910521d431` | 只加候选文档/证据；437 源码与冻结版本相同 |
| 实际执行提交 | `f771b5eb73bfbc48c928c5a94bbb0af137c4c51a` | 单父为上行，唯一差异是当次 approval.json；另外 436 源码相同 |

公开摘要中的 `source_sha` 精确绑定审查父提交 `30979849…`；GitHub 实际 checkout 的 `head_sha` 为批准提交 `f771b5e…`，二者含义不同。候选分支仍为 pending 原版，执行分支保持批准提交不再推送。本报告在另一个正常开发分支 `dev/f2-catalog-only-acceptance-20261013` 交付；其分支不匹配任何 workflow。

已在同一全新自有临时 PG16 集群/UUID 库中实测：

| 阶段 | app | writer | 原 analyzer | changes |
| --- | --- | --- | --- | --- |
| 修复前 | 有效权 ALLOW，实际函数调用成功 | 有效权 ALLOW，实际函数调用成功 | REFUSED，唯一非 PASS 为 app 的 control-system 执行权 | EMPTY |
| 提交单函数 PUBLIC REVOKE 后 | 有效权 DENY；独立会话实际调用得到 42501，回滚后 SELECT 1 正控制成功 | 有效权 ALLOW；独立会话实际调用成功且返回同一集群标识 | PASS，无非 PASS 检查 | EMPTY |

实际使用原 owned 创建证明、storage installer、collector 与 analyzer。每个角色是独立 SQL 连接，校验 session_user/current_user、非 superuser、精确数据库/OID/socket/port；没有 SET ROLE 代替实际身份。封闭输出指探针公开摘要；完整 Actions 日志仍包含正常 checkout 路径、遮罩令牌、平台 HOME 临时覆盖及 Secret source/Cache mode 元数据，这些不能解读为探针读取已有密钥或启用了缓存。成功摘要还包括依赖准备、PG16 启动、存储、前后有效权与调用、修复提交、比较和 `CLEANUP=PASS`。清理只在拥有的 PG 正常 exit0 后删除本次 cluster；临时依赖与私有日志仍在本次新目录，后续由一次性托管 VM 收尾；本次摘要不独立证明整个 root 擦除或 VM 销毁，也不表示清理了任何既有库或系统服务。

本次真实结果已通过[独立限定验收](evidence/catalog-only-acceptance-20261013/independent/actual-acceptance-review.md)，原日志、封闭摘要、运行及提交元数据相符。原候选主测 372 PASS，独审 378 PASS，精确重叠 364、主测另 8、独审另 14；不能相加。6 个纯测原失败及同 ID 修复结果完整保留，437 源码测试窗口无漂移。原 7 项 PG 测试继续 NOT_RUN，本次 13 项实际 catalog 检查不代替那 7 项。候选归档的 `git diff --check` 有两处 FAIL，均为原始失败 XML/stdout 的 `E` 行尾空格；本次实际证据归档另有 10 行原始 Git 推送 stderr／原差异输出的尾空格，原样保留并记录 FAIL。源码与新报告正文的差异检查均 PASS，证据原件不为通过格式检查而改写。

环境恢复、单一代码写入者和原远端保护分支已先核实。父任务转达用户新授权后，分别独审父提交与精确批准提交才首次推送；用户批准的范围仅为本次免费、15 分钟内、新库/新 SQL 角色的 catalog 验证。没有新 OS 用户、既有安全权限扩大、已有凭据配置或密钥读取、生产部署/迁移、main 修改、模型/付费调用、浏览器或 host/lifecycle 执行。历史 GitHub 只读拒绝和 Chromium `ERR_BLOCKED_BY_ADMINISTRATOR` 均未重试。

旧两次受限试验的 FAIL 原样保留；尤其 run `38332150145` 仍是 3 PASS / 1 FAIL / 13 NOT_RUN。本次证明这一个实际新集群上的 catalog 缺陷与修复效果，不能倒推已销毁旧 VM 的唯一失败原因。SQL 角色通过私有 Unix socket 的 local trust 连接；不签 OS 身份隔离、密码认证、host/IPC、原 Run/Case、生命周期或完整首次接单前取消的实测验收。后续工作应回到原产品纵向验收缺口，使用相应范围的独立证据；本次运行次数已经用尽。

证据索引：[原始公开摘要行](evidence/catalog-only-acceptance-20261013/root/actual-public-summary-original-line.log)、[可读摘要](evidence/catalog-only-acceptance-20261013/root/actual-public-summary.json)、[运行元数据](evidence/catalog-only-acceptance-20261013/root/actual-run-projection.json)、[完整性清单](evidence/catalog-only-acceptance-20261013/manifest.json)、[验证与资格](evidence/catalog-only-acceptance-20261013/validation.json)。[候选实现与原失败证据](CatalogOnlyTrialCandidate-20261013.md)保持原记录，不回写历史 NOT_RUN。
