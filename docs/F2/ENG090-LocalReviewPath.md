# ENG090：可复现本地评审路径与最小合成初始化

本轮基线 a73e252c4556dd8878277dcc73fd9d1308320458。新增只读六步评审目录，将“原诉求→方案覆盖→资料准备→候选发布→候选访问→本地回执”整理到一个入口。前后三份历史产品代码证据及资料准备证据均使用合成输入；规则/访问则是独立 Mock。各段历史 Case 不同，不能拼成同一新事项闭环。交互候选结果不回写历史证据或产品正式状态。

## 本地复现

在已安装本仓库依赖的 Python 环境中，从仓库根运行：

```bash
PYTHONPATH=src:. python scripts/review_demo.py
```

打开 `http://127.0.0.1:8770/`。默认只读目录可查看六份固定证据；两个候选页面默认关闭，不创建候选数据库。目录按内嵌 SHA256 seal 验证六份固定 JSON 文件，只投影有限布尔检查与 UUID，不展示私有原诉求、原始 JSON、runtime 截图或凭据；并不动态查询 Git HEAD。来源缺失、hash变动、symlink或越界后均不作为通过依据。

本次推荐的最小交互演示可按现有本地合成授权显式启动：

```bash
PYTHONPATH=src:. python scripts/review_demo.py --isolated-mock --state-dir .runtime/review-demo-state
```

同入口的两个链接分别打开8771规则页与8772访问页，均显著标识Mock。规则：fixture-a保存→提交，prep-specialist-fixture-a审核，mock-publisher候选发布。访问：mock-run-owner申请，mock-run-access-approver独立批准，mock-run-executor探测合成单Run；返回owner撤销后，executor缓存清空且探测拒绝。mock-run-b明确拒绝。完成后用浏览器返回目录，历史Case不会前进。重复打开/刷新恢复候选审计，不自动批准。

启动器只绑定127.0.0.1的三端口，最小子环境不继承产品凭据/PG DSN；使用非秘密实例标识核对自己创建的三个子进程。端口占用立即拒绝，不杀或接管已有服务。Ctrl-C/SIGTERM只回收本次持有Popen句柄的三个子进程。专用state目录必须有精确namespace/对象marker；foreign目录、额外未知文件及symlink拒绝且保留原物。`--report`仅runtime或/tmp，foreign/symlink报告拒写，既有报告仅在带明确候选report marker时复用；该公开marker用于识别候选报告格式，不证明文件owner；不覆盖任意文件。state保留审计，启动和退出均不自动删除。

## 这次可以直接决定的最小方案

| 决定项 | 本次必要且推荐的最小合成演示 | 将来生产接入（另外审核，未执行） |
| --- | --- | --- |
| 精确对象/数据库 | park-a/org-a/candidate-intake；访问仅mock-run-a。专用state目录的rules.candidate.sqlite3、access.run-access.candidate.sqlite3及review-demo.json；产品PG不连接 | 源码roles.sql默认库名parkweave，实际目标endpoint/库/schema必须在获授权初始化前核实。真实park/org/service/Run清单目前未指定，不猜填 |
| 表/写权限 | rules仅candidate_meta、candidate_rules、candidate_releases、candidate_events、candidate_assessments；access仅access_meta、access_tickets、access_leases、access_events。仅本地OS目录文件写，不需SQL GRANT、PG DDL/owner/角色或真实账号初始化 | 拟新建rule_versions、rule_reviews、rule_releases、rule_events、rule_publication_authorities、run_access_requests、run_access_decisions、run_access_events、run_access_authorities，并补managed assignment批准ID/版本/expiry关联。app直接最小SELECT/INSERT及列明草稿/申请UPDATE；authorities只读；决定、发布、审计、assignment function-only。函数精确EXECUTE/受限静态SQL与search_path单列审核，app不获owner/DDL/DELETE/主体授权写权 |
| 主体/受益人 | Mock标签：fixture-a作者、prep-specialist-fixture-a审核、mock-publisher发布；mock-run-owner申请/撤销、mock-run-access-approver独立审批/撤销、mock-run-executor唯一READ受益人。均不是部署身份 | 具名已有目录经办/审核/发布账号分别按精确服务RULE_*；访问审批账号明确精确Run RUN_READ_APPROVE/REVOKE，受益人为已有同tenant service_executor且具现有READ。角色名称或材料审核权本身不授新权 |
| 最大范围/期限 | 单服务/单Run；访问固定READ，UI默认4小时、API最多8小时，UTC、当前审批范围与事实重验；不包含CONTROL/EXECUTE/FILE_READ。规则Mock来源2019–2099只是合成 fixture范围，候选快照仍受来源/规则有效期约束 | 清单试点不自动扩新Run；4h默认/8h上限为建议，具体名单及期限审核后才配置 |
| 撤销/清理/旧assignment | owner或精确Mock审批人撤销，过期及版本变化拒绝旧缓存，审计保留；停自己子进程，保留SQLite。必要时人工删除该专用合成目录，不能自动删除正式文件。完全不读写旧assignment | legacy原范围保持，不默认补期限/撤销/替换；已有合法访问不重复申请。新managed绑定撤销须匹配批准ID/版本。所有既有direct assignment读路径统一TTL/撤销guard。实际assignment还让已有单独分派的合成dispatch/receipt路径可达，审批须说明此影响，不能声称只多看一个状态页 |

推荐一次决定**仅采用本次隔离合成演示范围**。它不隐含批准未来生产DDL、技术写权、具名主体能力配置或真实单Run赋权；未创建真实凭据、身份、Grant或assignment。生产部分的具体已有账号/实际目标尚未确定，保持关闭。

## 验证与实际限制

最终冻结224源码完整Linux回归1564PASS/0FAIL/9原生SKIP/2WARN，321.54秒、冻结差异0；启动器8PASS/1WARN，初步候选相关62PASS/1WARN。最终验收结果及source SHA见[evidence](evidence/eng090-local-review-path.json)。测试涵盖默认无存储、清洁启动、同state重复启动、owned清理、busy端口不接管、foreign文件保留、hash变化与私有字段不投影。真实缓存Chromium点击两条候选链，1200/390/320目录及390/320候选无横溢；刷新/重复打开、四条规则事件及三条访问事件保留，Run B拒绝、撤销清缓存，历史6份SHA不变。结束后owned服务停止；同state再启动行数不变。

这不是同一新Case的产品端到端演示。T01真实性/跨材料裁决、T02通用编排/全部目标、T03正式Approval/ServicePlan组合绑定、T04真实新Run访问、T05完整事件/未知结果闭环、T06审核参数模板/新企业冷启动、T07原V1全链/视觉签收/原生门仍未完成。F1未签收、F2并行探索，Windows Server不是Win11；R4关闭、模型调用与预算0。本轮不push、新CI、merge或deploy；原环境/备份保持。
