# F1 真实日志

## 2026-10-05 DOC-001

仓库 origin=https://github.com/T1doo/ParkWeave.git；初始31e7acb7e53bb1ab6465b9daae59de28757f7583，work干净；新分支dev/f1-foundation。仓库与工作区没有可读AGENTS.md或相关技能文件。没有访问Sim2Act或用户电脑。

完整Library read：454行44220字节、410行31271字节；has_more=false。文本响应均少一个末尾LF；补一个LF后精确匹配元数据，哈希见sources/V1/manifest.json。原件不可修改，工作正文追加授权小修。

新增验收规格由全文转录，未收到原JSON/DocumentReview等原包附件；初态与执行器待实现，全部NOT_RUN。文档完整性核对PASS，仅为文档检查；产品测试NOT_RUN。模型/Windows/真实园区主张BLOCKED。代码提交：本记录随文档提交，实际SHA在下一日志记录。

## 2026-10-05 ENG-001（首个有界工程增量）

文档基线提交00f1d8a317e6676c9139cb8d9f6702ee504617a5，已push并用git ls-remote核对一致。本记录随首个工程提交；实际提交SHA通过Git历史/交付链接关联，执行代码逐文件hash见evidence/engineering-manifest.json。

变更：自建Python包/API/独立worker/PostgreSQL迁移及应用角色权限、严格0.1契约投影、有限三值函数、可信case.create/1、事务Operation/Receipt/outbox、租约fencing、当前授权锁、暂停取消、三工作区骨架；全部合成，本地建单不推进业务履约。没有访问或复用Sim2Act代码，没有调用真实模型API。

实际环境：Linux云x86_64，Python3.12.14，PostgreSQL16.2（pgserver0.1.4测试分发），其他精确版本见requirements-linux-evidence.txt。API/worker端口/PID、运行/操作ID、输入hash及状态见evidence/http-smoke.json；它们是本次历史进程证据，不代表一直在线。Windows精确版本尚未测。

失败与修复：
- 默认uv缓存/home/agent/.cache只读→失败；指定工作区缓存后安装成功。
- 第一次pytest：10 FAIL / 11 PASS。身份表FOR SHARE要求UPDATE权限，与最小角色冲突；改为共享advisory授权锁，owner撤权同键独占锁，不给应用身份修改权限。第二次21 PASS，最终21 PASS，见pytest-final.txt。
- 浏览器默认socket目录只读→指定XDG_RUNTIME_DIR；后续缺少容器沙箱参数失败→每次明确Chromium及--no-sandbox（仅测试容器）。初始UI刷新验证失败；点击轨迹显示布局切换后点击落在html根节点，补页面快照与语义定位后流程通过。另修复UI吞掉错误，显示请求错误。临时诊断和截图未纳入交付。

实际命令：uv venv/uv pip install；python -m pytest -q --tb=short；python scripts/linux_fixture_server.py（启动独立API/worker）；agent-browser0.38.2本机Chromium验证，由scripts/browser_smoke.py复现。浏览器open/页面内容/三入口/受理及状态读取PASS，错误为空；实际HTTP202、Case NEEDS_INPUT、Run LOCAL_CASE_CREATED、跨园区403，工程PASS。均仅Linux合成工程结果；未映射整个AT为PASS。

剩余：完整AT/EX NOT_RUN；AT-01/02/34的Windows/真实模型门BLOCKED，真实园区效果BLOCKED。资格自动判断、资源预约、文件导入、多角色/字段Grant、外部结果不明、长任务心跳、共享总限流/成本都未完成。Schema0.1仅当前投影，不宣称V1全契约已实现。C0模板正文/关联作品政策/截止时刻仍BLOCKED，用户当前报名和提交日期2026-11-05。

所有依赖为安装的上游包，不复制依赖源码/二进制进仓库；Linux测试包pgserver不作Windows运行依赖。当前未开展开源许可证发布选择，不宣称整个仓库已有开源许可。提交前排除.venv/.cache/.runtime/egg-info；审查差异及高置信秘密模式，原件hash重验。合成会话、数据库文件、访问日志与截图不提交。

下一步候选：补V1完整领域契约与事实冲突；增加作用域Grant与各角色；独立FAULT_INJECTION外部未知结果账本。Windows及模型条件未满足前保持对应门BLOCKED，不自动进入F2真实办理。

## 2026-10-05 ENG-002（第二有界F1增量）

基线05625e07db8d8b633843b40b92abfeb398c4ec9e，dev/f1-foundation干净，远端仍T1doo/ParkWeave；没有新增可读AGENTS/技能规则。复核Plan/AT后选择独立基础缺口：结果不明的持久核对与计划契约边界，不进入F2。

新增FAULT_INJECTION账本原型：测试单独安装fault-schema，模拟远端效果独立事务；DISPATCHED持久化后才发送；OUTCOME_UNKNOWN只核对，不重发；暂停取消令旧worker回报失效、未知不会变“无影响”；撤权后不新发，但可记已派发历史效果且用户不可再读；回执按企业/园区/ID/指纹/来源精确核对。常规迁移/角色/API/worker不注册故障能力，正常库缺表，HTTP任意故障动作422。没有使用真实账号或聊天密钥。

发现并修复：基线领域契约错误接受重复必需目标、重复覆盖引用和17项重复覆盖。用固定基线源码在临时.runtime重现，证据eng002-contract-defect.json；新约束拒绝空白/重复/过长/非ID引用及重复依赖。当前0.1投影仍不是完整V1资格/材料/有效期契约。

测试命令：python -m pytest -q --tb=short；第一轮31 PASS，补契约后37 PASS，补派发前控制/过期后最终40 PASS（2 WARN，沿用httpx deprecation和pgserver runtime目录fallback）。13新故障断言+6契约边界+原21。最终输出eng002-pytest-final.txt，代码hash及环境eng002-engineering-manifest.json。没有将任何完整AT预填PASS。普通API/worker浏览器回归由scripts/linux_fixture_server.py及scripts/browser_smoke.py --report docs/F1/evidence/eng002-browser-smoke.json完成，实测结果以该文件为准；Linux不能替代Windows。

失败记录：本轮pytest无FAIL；先前契约输入错误接受有固定提交复现，不隐藏该缺陷。修复仅严格化未发布0.1契约。故障账本还未接入正常Run/worker/outbox，这是NOT_IMPLEMENTED，不当作已通过。Windows/LIVE/真实园区主张仍BLOCKED，全部完整AT/EX仍NOT_RUN。

没有修改Sim2Act、共用数据库、持续凭据或预算；全为自建合成。提交前将审查秘密/个人数据和原件hash；原件不修改。代码提交本条随ENG-002提交，准确SHA通过Git历史与最终交付链接关联。下一轮最合适独立工作：字段级Grant及事实冲突契约；另由具备条件的执行者办理Windows/真实模型门。

证据工具记录：一次误用系统python导入项目时ModuleNotFoundError；改用项目.venv/bin/python后schema和manifest生成成功，原件hash再次核对一致。此错误不隐藏，未当产品测试FAIL或PASS。ENG-002 Linux Chromium回归PASS（202建单、持久读取、三入口、浏览器错误为空）；原ENG-001证据保持不变，新证据单独归档。

## 2026-10-05 ENG-003（正常worker网关与未知结果）

基线a1858b16846dfc981cad4a5aa23f8ea9abf96324，dev/f1-foundation干净，origin仍T1doo/ParkWeave。按父任务选定唯一主范围：把ENG-002核对语义接入正常runs/operations和真实API/worker，非只增旁路测试；完整V1契约/事实冲突/字段级Grant本轮不散开。

变更：ExecutionGateway连接正常worker；本地case.create和显式fault.record共用Store.locked_execution的当前身份、事务锁、租约/fencing；持久派发意图后才模拟效果，恢复只查不重发；未知自动观测最多3次（未知派发响应也计），之后保留RECONCILING，由当前授权手动核对重新启用查询；取消/暂停未知操作只记录意图并fence旧worker，已知效果不冒充撤销。已派发后撤权仍允许内核记录历史结果，不允许新发或原用户读。

Schema2为独立owner原子迁移，保留历史Run/Case/Receipt，版本健康检查改max(version)。显式fault模式需要API/worker双方配置及合成库fixture_effects权限；默认API422、LOCAL worker跳过故障任务。旧fault_operations旁路原型保留对照测试，但正常worker不使用它。没有新外部接口或真实调用。

真实路径：新增tests/test_worker_gateway.py启动uvicorn、HTTP客户端与独立CLI worker，使用最小应用角色及临时PG16.2库；崩溃注入after-dispatch/after-effect退出75，恢复按真实DB时钟到期（非手写Run终态），旧callback在同网关拒绝。迁移从原001历史库重建后检查ID和事实保留；无效回执只改变模拟远端输入，真实worker拒绝成功。已有40测试继续回归，完整AT没有预填PASS。

实际命令：python -m pytest -q --tb=short：初始40 PASS，新API/worker测试后51 PASS，追加迁移/无效回执后53 PASS，最终补默认模式拒绝派发测试的结果见eng003-pytest-final.txt（14新增+原40）。本轮pytest无FAIL；预期负例是旧fence Conflict、撤权403、非法回执EFFECT_KNOWN_INVALID、未来DB版本Conflict，并未当意外失败删除。两个既有WARN保留：Starlette/httpx弃用和pgserver runtime目录fallback。

实际连续运行：python scripts/linux_fixture_server.py --fault-fixtures（Linux云、独立API/worker、PG16.2、127.0.0.1:8765），python scripts/browser_smoke.py --report docs/F1/evidence/eng003-browser-smoke.json，python scripts/gateway_smoke.py。浏览器PASS；实际HTTP轨迹QUEUED/PREPARED→RECONCILING/OUTCOME_UNKNOWN→SUCCEEDED/VERIFIED，success_scope=FAULT_INJECTION_EFFECT_KNOWN，Case=null，跨园区403。输入hash、run/operation ID与历史PID见eng003-gateway-smoke.json，源码hash见eng003-engineering-manifest.json。模型0次调用，全部明确合成或FAULT_INJECTION，不代表真实外部受理/线下履约/模型链或Windows通过。

剩余：完整V1契约、事实冲突、字段级Grant及其他角色、长等待心跳、outbox撤权/消息完整语义与固定AT全执行器尚未实现。Windows/LIVE/真实园区条件保持BLOCKED，完整AT/EX NOT_RUN，F1未通过。未修改Sim2Act、未共用其数据库、未配置持续凭据、未读取隐藏密钥；提交前秘密/个人数据及原件hash检查，测试数据/会话/截图/访问日志不提交。实际代码SHA本条随工程提交，通过Git历史和交付链接关联。

最终回归54 PASS / 2 WARN（20.12秒），包括原40与新增14条实际API/worker/PG路径测试。当前仅该明确工程范围有PASS；完整AT/EX未改状态。本轮没有意外FAIL；所有注入失联和负例均保留断言与日志，不删用例。浏览器及连续worker HTTP证据各自单独保存，不覆盖ENG-001/002历史。
