# R3三字段候选评审（ENG011）

只有region/employees/service_need，只有明确SYNTHETIC来源。正常POST /api/runs沿用facts.assess，显式candidate_review=true，fact_fields列必要字段，fact_candidates最多12条。候选输入沿用FactInput的值类型/单位/有效期和SourceRef版本，origin只能USER_STATEMENT或DOCUMENT_EVIDENCE。文档来源指用户提供的合成摘录/结构化断言，并非已收到/读取真实文件，也不证明出处权威；没有任意文档解析器、上传或资格引擎。

正常worker/gateway接入默认OFFLINE_MOCK_MODEL投影，保留输入来源，再严格解析模型候选；模型不能改变来源id/version、字段、单位、摘录或有效期，不能添加字段/伪称VERIFIED。模型值可以不同，但作为MODEL_CANDIDATE单独保存，不覆盖原来源；不同值进入CONFLICT。所有候选及已有USER_ASSERTED_SYNTHETIC断言在此评审都标UNVERIFIED，不写fact_assertions或晋升已核实。provider请求/真实授权预算0，没有读取model env/key，也不复用开发模型代答。

## 正常闭环与必要问题

初步权限/持久输入指纹校验后释放DB事务再作mock投影；返回后重验当前scope、企业经办角色、READ/WRITE/EXECUTE及action Grant、fence/lease/control、源输入未变。按字段汇总所有版本/双方来源，不猜权威：没有来源MISSING、无当前有效来源EXPIRED、有不同有效值CONFLICT，其余UNVERIFIED；统一state UNKNOWN和qualification_decision NOT_EVALUATED。一次返回必要字段的问题列表，已填自述仍需授权核查，不自动默认通过。

immutable fact_reviews保存完整document和canonical SHA256，与operation完成、Run终态、outbox同事务。operation VERIFIED只证明本地评审操作完成；success_scope CANDIDATES_REVIEWED_UNVERIFIED，不证明事实或资格已核实。无Case/外部受理/线下履约副作用。旧非候选facts.assess的“KNOWN一致自述”投影及历史回执不改写，不把其历史KNOWN解释成已核实来源。

GET /api/runs/{id}/fact-review返回统一问题、来源、hash及followup链接；当前owner/scope/READ检查，获派状态角色不能读候选。旧缓存不能绕撤权；已经展示到用户浏览器的文本无法远程收回，切换会话会清本页评审缓存。页面三字段表单创建候选，统一显示必要问题，自述补充/取消，不执行证据内HTML。

## 澄清、取消、重试与历史

POST /api/runs/{id}/clarifications携带review_sha256、Idempotency-Key以及decision ANSWER（1—3条FactInput）或CANCEL（无answers）。校验当前CONTROL/READ，回填还须当前EXECUTE/WRITE，字段只能来自父评审。hash不一致拒绝，key重复但body不同409；重复同key仍重验权限。主体锁/同key advisory锁串行，ANSWER以同一事务创建新Run/PREPARED operation/outbox和不可变fact_followups链接；追加USER_STATEMENT版本，旧候选/父review/事实不覆盖，合并来源最多12条/16KiB，达上限明确拒绝。

同key并发只建一个子Run，网络响应丢失可用原body/key安全重试。网页保留失败请求的原body（含有效期）/key，防止点击重试生成时间戳造成指纹不一致。CANCEL只记本次补充取消，不改变旧Run、事实或已知作用；已排队子Run可以用现有cancel/pause/resume，旧fence不能发布。mock期间撤权/取消会重验；未commit的评审可由失联后新worker重作，唯一review、receipt、terminal/outbox不会部分写入。

应用对fact_reviews/fact_followups只有SELECT/INSERT，无UPDATE/DELETE；schema8增量迁移保留既有Case/fact/plan/授权撤回，重复迁移不重写历史。来源版本都是所提供的合成声明，不冒充真实规则/原件包的证据。R4/native候选仍未启用；F2/F3及Windows/LIVE/真实园区签收不从本轮工程PASS推断。

## 独立证据

tests/test_candidate_review.py使用真实临时PG、正常API请求、独立CLI，oracle自己算canonical hash并查表、比对版本/分类/缺值/冲突/过期、断言旧事实不变、权限与当前撤回、模型篡改拒绝、澄清幂等/并发/取消/回填仍UNKNOWN、事务中断及旧fence恢复、immutable权限、迁移保留。scripts/candidate_browser_smoke.py在Linux Chromium/本地API/独立worker验证三个必要问题、回填仍UNKNOWN、取消/父历史不变、320/390无横向溢出与零browser error；非Windows/手机实机通过。全量证据见eng011-acceptance-summary.json，whole AT/EX仍NOT_RUN。
