# 普通启动读取已有资料准备记录

基线 `db1084100a2477bbff3da8b49287c755dbc83c1b`；冻结源码 `5e287545dcf178053574cafeee092041689eb51e`；开发分支 `dev/f3-ordinary-preparation-entry-20261017`。本实例是唯一源码/Git写入者，不恢复原已完成任务的写入。完整项目尚未完成。

普通 `parkweave.api:configured_app` 的 `/` 页面新增“读取已有资料准备记录”。填写当前已有会话和原 preparation UUID，明确点击后，新增 GET `/api/preparations/{id}/entry` 在 READ ONLY 事务中复用原身份、角色和 preparation 范围检查，核对当前原获派专员及精确目录版本，再调用原材料读取页面。`/?preparation_id=<UUID>` 只预填编号，不自动读取；会话不放进链接或新增浏览器存储。本地启动说明页提供同一入口链接。

此入口不创建 preparation、身份、Grant、分派、目录或批准。`approval_granted=false` 仅说明本次导航没有授予批准；批准状态仍从原独立接口读取。普通工厂没有注入 IsolatedPlanApproval、NativeRunAccess permit 或 writer。原资料读取/来源预检/ADOPT和原角色要求保留；旧读取路径仍依原合同提供历史记录，本片不改其权限语义。

企业经办人须本人 PREPARE；专员须本人 REVIEW_ASSIGNED 且正是记录原获派人；两者均须当前 READ、同园区/企业范围和有效会话。新入口还要求原获派专员当前有效并有 READ/REVIEW_ASSIGNED，以及同园区、同服务、**记录所用精确版本**的 `preparation_catalog` 合成来源。缺来源返回409；权限/不存在/越界沿原统一403隐藏记录存在性，不公开内部拒绝原因。数据库原外键禁止删除或改版已被引用的目录，本片不绕过它。

读取新入口与原材料页不变更所列业务/权限表；HTTP拒绝仍可能写原授权审计。进入原来源预检后，原 `service-case-plan` GET 按既有合同保存观测到的失效标记；这不是本入口新增写能力，不等于ADOPT或新核验。用户仍从原机会卡预检受影响/保留步骤，填写原说明、勾选确认后，才调用原 `service-case-plan` ADOPT。原来源算法、稳定编号、历史、锁和事务接口不重做。未确认旧操作时，新入口不切换上下文；材料响应丢失后可用原 `command-recovery` GET 核对，不借新入口重发。

## 运行仍缺的输入

本次没有取得任何真实业务运行资料，也没有为普通启动补建以下输入：

1. 已合法配置的受限数据库连接、现有有效会话，以及该身份当前 READ 和本人 PREPARE，或原获派专员的 READ/REVIEW_ASSIGNED。原需写命令还须原 EXECUTE 等能力。
2. 已存在、同域且原 owner/reviewer 绑定正确的 preparation UUID、原 Case/Run 和原始资料记录。原普通合成协议所需的成功 `case.create`、资料槽/核对状态继续由既有接口约束。
3. 该记录精确服务版本的可信目录来源，以及当前原获派专员身份和授权。更高版本目录不能替代原引用；当前工程路径仅接受明确 SYNTHETIC 来源，不能拿它证明真实园区服务规则。
4. 如要采纳来源修订，还须既有稳定计划、当前最新且待审的机会卡及真实来源变化绑定、可采纳的原预检、受影响锁处理和明确说明/确认；这些不是入口代造的输入。
5. 完整 P1–P5 所需的已有合法执行者/Run访问分派，以及普通运行时可信目录和批准的跨进程接线仍未齐备。NativeRunAccess默认拒绝 permit/writer，`configured_app` 的普通 provider 注入缺口未由本片解决。IsolatedPlanApproval仅隔离测试，不作为普通批准；不得靠环境开关、测试签发证明或自动补权代替正式输入。

测试中的专员、Grant、目录和已有记录均来自原自有临时 PostgreSQL 合成 fixture；与上述真实运行缺口分开。普通默认初始化仍缺 preparation 授权/记录/目录，并按原门禁拒绝。

## 验证与限制

正式结果及原件配对见本目录下 `evidence/ordinary-preparation-entry-20261017/`；开发失败日志/XML均保留，不迁入最终通过数。开发窗口未另存完整源码快照；测试数据库沿用原 fixture 生命周期，不声称失败数据库均仍在运行。该目录的运行汇总明确记录独立审查状态。

同一冻结源码的 **9个完整相关模块、178个唯一pytest项全部PASS，0FAIL/ERROR/SKIP**，524.95秒、4个既有警告；新增两个模块21项已包含在178内。未把开发16/21项重复加入，未重跑原历史73项整组或全仓。本实例自审完成，独立审查 **NOT_RUN**，整体标记 `PASS_WITH_INDEPENDENT_REVIEW_NOT_RUN`。

712个源码/测试/脚本/配置输入冻结前后hash零漂移；基线 `docs/F2/evidence` 下26613个跟踪文件（含旧公开副本等）hash零漂移，不改称为新的测试或原始证据数量。42份本批公开原件配对已核对，日志/XML中37处合成会话候选串脱敏，私有原件保留在本实例 `.runtime/preparation-read`；公开JSON/XML解析及最终178个节点名保持。不同实例可从Git读取公开副本，不假定能读取本实例私有状态。

[运行汇总](evidence/ordinary-preparation-entry-20261017/gate.json) · [正式JUnit](evidence/ordinary-preparation-entry-20261017/final-v1.xml) · [实际来源链](evidence/ordinary-preparation-entry-20261017/process-evidence/test_ordinary_process_opens_or0/source-entry-proof.json) · [实际页面](evidence/ordinary-preparation-entry-20261017/process-evidence/test_ordinary_process_opens_or0/source-entry.png) · [失败台账](evidence/ordinary-preparation-entry-20261017/failure-ledger.json) · [原件配对](evidence/ordinary-preparation-entry-20261017/public-pairs.json)。配对核对与源码审查均为本实例自审，不充作独立验收。

| 完整模块 | PASS |
| --- | ---: |
| native preparation entry | 16 |
| ordinary-process Chromium entry | 5 |
| preparation | 35 |
| preparation command recovery | 11 |
| readiness | 15 |
| source change adoption | 23 |
| service plan recovery | 30 |
| native run access | 35 |
| local case entry | 8 |

开发首窗13FAIL/3PASS：10项HTTP断言误期待内部Denied原因、两项故障设置被原目录外键拒绝、一项浏览器误期待详细403；保留原统一403与外键，改为HTTP统一拒绝加原核心原因检查，并用合法合成来源缺失/未知及更高版本并存测试原精确版本。第二窗16PASS。首浏览器窗2FAIL/2PASS分别误将原计划GET观测当零写、误点击原POST重试而非已有GET恢复；修正测试后第二窗1FAIL/3PASS，仅剩不存在的状态元素断言，实际ADOPT已保存；改为原POST201与真实历史元素。第三开发窗21PASS。上述失败与修正不替代正式178项结果，也没有为测试放宽权限、修改原来源算法或绕过拒绝。

本轮使用仓库 `requirements-linux-evidence.txt` 的固定依赖，额外安装已有浏览器测试所用 `playwright==1.62.0`，使用已安装的 `/usr/bin/chromium`。正式命令如下；复验时须另选全新自有 `--basetemp` 与输出路径，不覆盖本轮原件：

```sh
.venv/bin/python -m pytest \
  tests/test_native_preparation_entry.py tests/test_native_preparation_entry_browser.py \
  tests/test_preparation.py tests/test_preparation_command_recovery.py \
  tests/test_readiness.py tests/test_source_change_adoption.py \
  tests/test_service_plan_recovery.py tests/test_native_run_access.py \
  tests/test_local_case_entry.py -q \
  --basetemp=/tmp/parkweave-preparation-entry-final-v1 \
  --junitxml=.runtime/preparation-read/final-v1.xml
```

新增验证包括普通默认工厂拒绝、已有 owner/获派专员读取、当前撤权与精确目录来源不可用、跨组织/园区/未获派隔离、工厂重建、实际 Chromium 和独立 Uvicorn 普通工厂进程、进程重启/新浏览器仅GET、来源预检和一次明确原ADOPT、编号ABA/迟到200及客户端注入迟到403、丢材料回执后的原键GET恢复。新入口前后的权限/业务快照，以及原预检仅保存失效标记的范围分开断言。客户端迟到403是故障注入；真实HTTP撤权由另一组用例验证。

原 `source_change_adoption.py`、`service_case_steps.py`、`service_plan_approval.py`、`native_run_access.py`、`store.py`、`readiness.py` 和原 launcher 与基线逐字相同。`preparation.scoped` 仅新增显式只读查询选项，旧默认锁和检查保持；新 entry不把读取预检作为后续命令授权。

本实例仅完成源码自审，未另行独立审查；交由父线程基于完整冻结SHA独审。Windows/Win11原生、正式AT/AT35、真实园区/身份/来源、真实模型、现实履约、生产部署和远端CI均未验收。不宣称全仓通过或完整项目完成。无main修改、强推、部署、新费用、新凭据或安全网络权限；不删除未知锁或进程，不绕拒绝。原封存证据保持。
