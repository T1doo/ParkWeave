# ENG086：带来源快照的本地材料准备度

基线 `6b647acc99432acee2299be033812981e4e1aff9`，承接原《平台产品设计》§5.3/§5.6/§6 的 ReadinessAssessment 与变化后重核。现有 ServiceSpec/Rule/Truth 合同只支持受控条件；本轮复用 `Rule(AND(EXISTS(service_need), MANUAL))` 和三值 conjunction，评估已有合成资料准备服务，不新增正式政策发布或资格裁决。

## 实际业务流程

企业和此事项当前获派专员可在资料详情保存准备度评估，查看每条条件的满足/不满足/未知、来源定位、缺材料、人工说明与下一步。记录保存后页面刷新恢复，GET 不写库。未保存时当前评估为未知；已保存但来源变化时标记 STALE、当前结论未知，保留历史结论及当时来源。

诉求摘要 EXISTS 只表示当前材料记录存在，不表示自述或摘录已验证真实。两个必需材料槽仍为诉求摘要与材料目录；所有提交源仍为 USER_STATEMENT 或 DOCUMENT_EXCERPT、真实性 UNVERIFIED。当前完整资料包经获派专员人工核对且快照匹配时，MANUAL 为 TRUE；当前专员明确 REQUEST_CHANGES 为 FALSE；缺材料、未核对、核对失效或审核权限不足为 UNKNOWN。AND 中 FALSE 优先，否则任一 UNKNOWN 保持 UNKNOWN。缺材料未知不会伪装为已核实不符合。

评估保存服务/材料来源与版本、每份材料 ID/文本/来源标签/SHA256、当前人工审核人/时间/说明/权限、规则版本/hash、父资料 revision 和总来源 hash。修改材料、重开/确认、修改诉求（既有 UPDATE_REQUEST 递增父 revision 并清审核）、服务来源变化或当前审核权限撤销，均使旧评估不适用于当前事项。历史幂等重放只返回当时记录；随后读取仍显示 STALE，不将旧重放当重新评估。

规则明确为 ENGINEERING_ONLY/DRAFT、business_publication=false；目录的 SYNTHETIC 来源不会被冒充正式政策。人工审核状态单独展示，材料核对不发布规则、不证明材料真实性。资格始终 UNKNOWN/NOT_EVALUATED，外部受理 NOT_SUBMITTED、线下履约 NO_EVIDENCE、Case goal_completed=false；不自动审批或关闭原 Case。受审正式 ServiceSpec 的导入、审核发布权威和适用日期规则引擎仍未实现，本切片不声称完整业务B已交付。

## 持久化与范围

schema20 只在已有 preparations 增加 nullable JSONB readiness_assessments（最多32条）。旧行NULL不造评估，原材料事件/版本与 Case/Run不回填或重写；重复迁移保留历史。应用沿用既有表UPDATE，迁移由原数据库迁移流程执行；无新表、Grant、身份、角色、Run assignment或owner修改。roles.sql/permissions.py/Windows隔离工作流不改。

GET/POST均重验当前身份、READ和原PREPARE或REVIEW_ASSIGNED；企业POST额外要求EXECUTE，专员仅当前获派事项。执行者及跨tenant用户拒绝。事务按actor身份→幂等key→当前reviewer身份→资料行的顺序锁定；不在拿资料行锁后逆序请求审核身份锁。POST绑定 expected_preparation_revision/source_sha256，变更409；actor-wide key绑定Case和请求，重复请求只追加一条评估，失败回滚。私有用户修订文本/必需目标及其hash不进入共享评估；父revision已足以使这类修改过期。

UI复用资料上下文代次/token/事项绑定，离开事项或换身份立即清空准备度来源/历史；迟到成功或错误不能重新投影。真正提交后丢响应，同原body/key重试只恢复原评估。

## 新 Run 合法访问的最小设计（未实现写入）

当前缺的是“哪个获授权主体可为哪个Run建立协作访问”的产品流程。store.scoped_run 与分派/回执目录已重验现有 active principal、service_executor角色、同park/org、当前READ和该Run active assignment；它们不申请或创建assignment。应用对run_assignments只有SELECT，Store.assign_status是合成测试设置helper，不是产品API。P3仍阻塞，不能用分派自动赋权、其他Case的assignment或手改SQL绕过。

本地Run assignment不创建或证明外部身份系统/OS/真实服务账户权限。外部账户事实只有在具体服务需要外部系统、且其权威流程明确拒绝或缺授权时才是外部权限缺口；当前新Case的P3缺口不能笼统写成Windows权限问题。

最小后续合同：先明确现有身份权威维护已存在、active、同tenant的执行者及READ；再冻结访问批准主体、单Run范围、拒绝/撤销/审计RACI，查明可复用的审批系统/授权接口。若主体或接口未知，保持BLOCKED。获正式授权后才实现显式申请→权威主体批准→精确Run assignment→执行者登录重新验当前身份/READ/assignment→专员按现有分派→本人接单。拒绝不存在/停用/跨tenant/缺READ/无或撤销assignment，所有拒绝零授权副作用；正向只改变获批准的Run访问行，撤销后的迟到响应不泄漏。当前仅设计，不增加owner写权限或新角色、不调用setup helper、不创建Grant/身份/assignment。

## 验证与发布边界

最终验证结果与源码/日志/截图hash见 [证据](evidence/eng086-source-bound-material-readiness.json)。相关PG/API最终107 PASS/0 FAIL/2既有WARN（44.75秒）：三值、来源变化、补正/审核、材料与诉求修改过期、刷新、历史重放、并发、权限撤销、跨Case/tenant/执行者拒绝、迁移不改授权、异常回滚和32条边界。首轮27 PASS/1 FAIL因测试executor token名称误用，改成既有executor-a；随后105 PASS，独立审查修锁顺序/私有hash后107 PASS。保留失败日志，不改变业务拒绝规则。

独立审查三项修复：提前锁审核身份，避免同Case企业评估与专员写入形成锁循环；共享来源移除私有intent hash；展开来源明确区分当前资料审核与最近人工决定，并为旧决定标版本/当前不可沿用，当前审核权限不能证明旧决定仍有效。最后15项材料准备度闭合回归通过（5.08秒），JS语法核验通过，实际浏览器新增当前/旧决定文字断言。最终实际Chromium/API/worker/PG tag `d7e7b8033aba`，新Case `95cf6f77-fc96-4b29-b824-bdf6472149cd`、资料 `eef4fae9-3b5d-4e79-9744-fb2abfd829d7`：7条评估历史；缺料UNKNOWN→补正FALSE→补件UNKNOWN→当前人工资料核对TRUE（资格UNKNOWN）→改材料STALE/当前UNKNOWN→reload恢复；真实丢响应同key只追加1条，commit后换执行者身份迟到回复不回显。1200/390/320无横溢出，来源/规则/审核草稿状态可读；四授权表摘要前后均 `f6ffd640f70a69fec8264de40f65a2080712322530555318ad4669918df38e30`，没有新assignment，Case保持NEEDS_INPUT。同Case只读展开来源/历史tag `9f79d05b0727`，3张1200/390/320截图、草稿未经审核发布文案与来源hash实际查看，完整业务数据摘要不变。最后冻结204源的完整Linux **1497 PASS/0 FAIL/9原生Windows SKIP/2既有WARN**（313.88秒），源hash0差异。冻结源码含上述历史决定呈现修复；9项原生skip不转为Windows通过，最终源码/日志/11张图hash与证据一致；独立最终核验 NO_BLOCKERS_FINAL。此前中间全量因独立审查要求统一草稿审核文案主动中断，438 PASS/1 SKIP/2 WARN（130.62秒）仅是部分运行，不计完整通过；原日志保留。第二次中间全量为修正历史人工决定误呈现主动中断，958 PASS/5 SKIP/2 WARN（236.18秒），也不计完整通过。真实运行不新增授权，API/worker自有子进程回收、PG停止并保留数据库。仅本地提交，不push/新CI/merge/deploy；下一次获授权发布应合并已验证的完整核心增量说明。Windows隔离CI只覆盖原隔离范围，不能当全量；Server不是Win11。F1未签收/F2仅并行，R4关闭，真实模型调用/预算0。

## 下一轮获授权发布的合并说明

发布说明应合并已验证的核心增量：ENG084当前事项四步方案/依赖/责任/验收预览；ENG085显式诉求与必需目标持久关联、UNKNOWN/PARTIAL阻止未覆盖启用、修改失效且保留原Case与既有记录；ENG086材料来源、当前/历史人工审核区分、三值材料准备度与刷新恢复。三者构成“明确诉求→明确有限方案与覆盖→材料补正和当前核对→来源变化后重核”的本地合成流程。不是完整自然语言理解、受审政策资格引擎、完整DAG或线下履约。

数据库按既有迁移流程依次执行19/20；旧数据不被回填为已理解目标或已评估，通过原授权边界读写。新Run的P3仍缺正常授权准备/批准路径，发布不能自动补Grant/assignment。下次普通push前先比较届时实际远端基线，遇未知冲突先报告；本轮不查询远端或push。发布验证应引用最终完整Linux与实际业务浏览器证据，并把原生Windows未验部分和Windows隔离CI范围单独标明；隔离CI成功不能代替网页/PG全量或Win11验收。
