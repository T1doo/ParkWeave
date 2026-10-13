# Case / owned PG 纵向验收候选

冻结源码 `54b15947f89eb1ba7524edb1119133d37ebc5326`，基线为已交付的 catalog-only 结果 `7cf76e7c0b8375717e704ec992d6e5c401b43ed2`。本候选回到原产品取消纵向验证：保留原 7 项物理 PG 负向回归，再验证普通 Case 的持久状态、事务回滚、真实锁等待、资源容量与旧通知，并在同一新库串联原 catalog 修复与取消 API。此候选记录时 **27 项实际用例均 NOT_RUN**，collection-only 不是执行。

| 范围 | 用例数 | 固定 ID |
| --- | --- | --- |
| 原 collector 无业务读写/锁、storage 冲突、伪造凭证/错误连接、既有危险系统角色识别 | 7 | PG01–PG07 |
| 原准备流程、本地关闭/重开及冷读、未分派/已 OFFERED 取消、跨租户拒绝、事件失败回滚 | 7 | PG08–PG14 |
| 取消先获得锁，阻止 ACCEPT/材料/首次分派/方案采用/资源关联 | 5 | PG15–PG19 |
| ACCEPT 先获得锁，取消等待后拒绝 | 1 | PG20 |
| 材料/分派/采用/关联先提交，取消等待后重核源版本 | 4 | PG21–PG24 |
| 取消仍占容量、独立释放；旧通知消费与打开重核 | 2 | PG25–PG26 |
| 同库 catalog 修复、真实成功 Run/Case、取消事务、原 key GET、异参冲突与独立释放 | 1 | PG27 |

精确 nodeid 见 [selection.json](../../scripts/case_pg_vertical/selection.json)。前 7 项原测试体及原 fixture 完整保留；部分 PASS 的正确行为是 analyzer REFUSED，不能把测试 PASS 写成预检全部通过。新 adapter 仅替换 session 的 PG 供应者，原 UUID 库、owned receipt、迁移、合成数据、应用授权、ASGI 和逐库清理不变。19 项旧 Case 用例在各自新库中验证原签发证明，然后提交单函数 PUBLIC REVOKE，实测 app 得到 42501、rollback 后 SELECT 1 成功。PG27 自行执行同库的修复前后比较，并保留 writer 的精确有效权与实际调用。

父任务转达的持续授权允许本次单个免费标准 Ubuntu runner、最多 25 分钟、全新自有临时 PG/SQL 角色和合成数据的开发验收。新入口 [workflow](../../.github/workflows/case-pg-vertical-once.yml) 只匹配新的 `dev/f2-case-pg-vertical-once-20261013` 首次 push，要求公开原仓库、run_number/attempt 均 1、精确单父和 approval-only 差异。候选分支不触发 workflow；本提交批准文件仍 false/null。下一步先独审文档父提交与源码等价性，再建立新批准提交并首次推送执行分支；不复用已用尽的 catalog-only 入口、不 rerun。Job 上限 25 分钟、step 23 分钟、probe 900 秒。

新 PG16 由一个保留的 Popen 启动，只监听新目录的私有 Unix socket；保留原数据库创建证明，应用连接限定新集群/新 UUID 库。仅有两个新 SQL login role，无新 OS 用户、密码认证、已有凭据配置、现有库或系统服务操作。依赖安装显式禁用交互、keyring、用户配置和缓存，使用新的空 NETRC。安装/测试日志留在新临时目录，公开只输出固定阶段、用例 ID、状态及失败位置/摘要 hash。未配置私有原日志上传；若 VM 回收，不能宣称私有完整 traceback 仍可取得。

执行成功必须同时满足精确 27 项收集、原 session provider 未运行、全部 setup/call/teardown PASS、19 次 app ACL 检查、所有新 fixture 库已删除及 owned PG 正常整数 exit0 后 cluster 删除。强杀、未知启动状态和清理错误均不能变成 PASS。清理资格限于该 cluster，不独立证明整个临时 root 擦除或 VM 销毁。

主测最终 **435 PASS / 0 FAIL / 0 ERROR / 0 SKIP**；独审 **444 PASS / 0 FAIL / 0 ERROR / 0 SKIP**；445 个源码 hash 前后相同。两窗重叠 427，主测另 8、独审另 17，不能相加。主测有 8 个明确 deselect（7 物理 PG、1 旧阶段 oracle）；独审另略过主测已跑的 8 个旧纯 pipeline 用例。纯测/DI 不签真实 PG、host 或网络运行。独审原件见 [review](evidence/case-pg-vertical-candidate-20261013/independent/review.md)。

失败证据原样保留：首窗 112 PASS / 1 FAIL，失败为旧 catalog pending 阶段断言与当前已消费批准不符；未重置旧批准或削弱旧测试，后续明确排除该过期 oracle，不能宣称同 ID 变绿。`bea44f4756dc77aa4d3e3efffeba79039183f5a2` 窗口 434 PASS / 1 FAIL，为新增 20 个函数未注册 diagnostic allowlist；本冻结提交仅补这些 ID，该失败在最终主测和独审中同 ID PASS。独审另有一次解释器 symlink 被解引用至系统 Python 的启动失败，发生在 collection 前；修正调用路径后的结果单独保留。大型原始 JUnit/run JSON 用确定性 gzip 无损存档，字节 hash 与压缩 hash 均可核对；通过窗口另有有界投影，未把删节投影称为原件。

此次不启动 host/IPC、外部 HTTP 服务、浏览器或真实模型，不签 OS 身份隔离、密码认证、进程重启/崩溃恢复、履约、生产迁移/部署。host 仍缺受保护 launcher、分离的 OS 身份及私有凭据边界；当前授权不扩大这些安全条件。旧 Chromium `ERR_BLOCKED_BY_ADMINISTRATOR` 和历史 GitHub 明确拒绝不重试。其余 Case 测试不在此 27 项内，完整功能覆盖需分别查看既有证据和后续明确验收，不能由本次最小纵向子集倒推。

候选归档的 `git diff --check` 为 FAIL（exit2）：原失败 XML/stdout 中 4 行 `E` 尾随空格原样保留；源码及报告正文检查 PASS。

归档：[完整性清单](evidence/case-pg-vertical-candidate-20261013/manifest.json)、[验证资格](evidence/case-pg-vertical-candidate-20261013/validation.json)。
