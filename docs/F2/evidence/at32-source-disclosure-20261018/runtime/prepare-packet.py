from pathlib import Path
import hashlib,json
R=Path.cwd(); sha=lambda p:hashlib.sha256((R/p).read_bytes()).hexdigest()
ledger=R/'docs/F1/DataLedger.md'
old=ledger.read_text()
assert old.endswith('不以合成通过替代AT-31/32后续真实比较。\n')
ledger.write_text(old+'''
## 2026-10-18 AT32 无试点披露修订

上段为 F1 历史记录，末句把 AT31 真实比较与 AT32 来源披露合并，范围过宽。本修订明确取代该末句的门判断：AT31 的真实效果比较需要其适用输入；固定 AT32 允许没有真实试点时核查输入、输出、反馈和报告引用，如实披露无证据即可。合成、MOCK、FAULT 和冻结证据 REPLAY 可按原方案用于各自适用的技术验收，不都等待正式来源合同。

| 当前类别 | 来源与本次使用范围 | 原执行类型与可支持的主张 | 缺项／限制 |
| --- | --- | --- | --- |
| 用户设计／衍生规格 | 两份指定 Library V1 原件及其 manifest，用户授权本项目保存、开发和核查；衍生设计／固定 AT 是项目文件 | USER_DESIGN_ARCHIVE；原件字节核对与要求追溯 | 本地恢复 LF 后 hash，无独立上游 hash；不建立真实政策／企业事实，也不推断公开再许可 |
| 自建合成初态与输入 | tests、普通 LOCAL_SYNTHETIC_DEMO 合同及受审 DOM 记录；身份、Grant、目录、分派属于显式测试初态 | SYNTHETIC_FIXTURE；普通本地 HTTP／PG／Chromium 工程，demo producer 明示 NO_MODEL | 自动化角色 REVIEW／CONFIRM 不是园区专家或真实用户批准；不授予普通正式来源权限 |
| 模型模拟输出 | F1 http-smoke 与 ModelBoundary 的历史及 ENG007 更正 | MODEL_MOCK；字段形状、离线控制、LOCAL_CASE_CREATED | 没有本次 LIVE 调用或真实效果证据，不能把本地成功当外部受理 |
| 故障输出 | eng003-gateway-smoke 的 SIMULATED_RECORD；最近旧403延迟交付记录 | FAULT_INJECTION；前者模拟效果，后者本地真实 HTTP 加运输注入 | 旧403不是当前执行者撤权；模拟／注入不证明外部履约 |
| 材料包／人工动作记录 | 实际合成下载文件与来源 preview／provenance，保留 SYNTHETIC 标签、版本及 SHA | NO_MODEL／LOCAL；导出字节、独立副本及自动化审核路径 | 包明示真实性未核验、政策 UNKNOWN、外部 NOT_SUBMITTED、目标未完成；不是有效资格或真实收益 |
| 协议／文献引用 | V1、DocumentReview、ModelBoundary 中既有公开 URL，仅追溯设计／协议参考 | PUBLIC_REFERENCE_ONLY；本次不访问、不验证现时规则或模型服务 | 既有核对日期不升级成本次实测；Sim2Act 原件／代码未收到，第三方再利用权不推定 |
| 使用反馈与价值指标 | 本受审包未提供真实园区试点、访谈、用户满意度或独立外部专家反馈；代码独审和脚本角色动作另列 | NOT_PROVIDED；只能报告技术测试和代码核查 | 无完成率提升、节时、收益或真实上线证据；不存在可据此计算的效果数字 |
| 本次 AT32 核查 | 冻结包、原证据逐项阅读与 hash 核对 | REPLAY + MANUAL_REVIEW_BY_CODEX；原执行类型另轴保留 | 核查不是新的产品运行、真实用户反馈或现实部署；Windows／LIVE／真实履约未执行 |

本次有限受审文件及逐项引用见 `../F2/AT32SourceDisclosureCase-20261018.json`；范围为该发布说明使用的来源类别、代表性输入／输出和列明报告主张，不声称逐条语义审计全仓历史附件或验证所有第三方 URL。新增来源或效果主张必须重新核查。缺失真实材料与许可被明确记录，不用测试 fixture、普通只读批准或 IsolatedPlanApproval 填补。
''',encoding='utf-8')
p=R/'docs/F1/ATBindings.json';v=json.loads(p.read_text()); row=next(r for r in v['cases'] if r['id']=='AT-32'); row['gate']='NO_PILOT_DISCLOSURE_REVIEW: AT32SourceDisclosureCase-20261018.json binds separate REPLAY/document-review receipt; this archive selector alone remains PARTIAL_ENGINEERING_ONLY, whole_status NOT_RUN. Real-effect claims require their own evidence.';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=R/'docs/F2/RemainingDeliveryGates-20261018.md';s=p.read_text()
s=s.replace('截至 SUBMIT 完成顺序冻结 `9d08a09b6560cbb278e166c4e68f11eb34914fe8`。','截至 AT32 无试点来源披露切片，基线为 `aaac5263f5694535758a11b5c38cce31e156cccf`。')
s=s.replace('## PR0／正式运行仍需的条件','## 按用例适用的剩余条件')
s=s.replace('| 原合法运行输入与 AT08／12／35 | 当前工程安装包／fixture不是真实主体、分派、目录或批准。完整正式首办／再次使用及新企业模板验收尚未执行。 |','| 真实业务运行输入；AT08／12／35 逐项回执 | 合成安装包／fixture不是真实主体、分派、目录或批准。已有本地首办／再次使用工程证据可复用，技术用例可按原方案使用合成初态；真实业务场景和剩余固定用例回执分别待验。 |')
s=s.replace('| AT02／07／30／31，真实书生工具与 B0/B1/B2 | 本地工程均0真实模型调用；真实理解→工具→确定性反馈→修订及公平对照尚无本轮实跑证据。 |','| AT02／07／30／31 中适用 LIVE 的模型与效果子项 | 本地工程均0真实模型调用；真实理解→工具→确定性反馈→修订及公平对照尚无本轮实跑证据。其他 LOCAL／MOCK／FAULT／REPLAY 技术子项可独立执行并复用，不能把整组 AT 都挂在 LIVE 合同后。 |')
s=s.replace('| AT21–29，F3-T01–03／期限 | 已有有限合成三值、事实／来源变化、历史与局部修订算法和工程证据；未完成全部正式领域来源及固定AT验收。不能据此重做原算法或推断一般语义／真实性。 |','| AT21–29，F3-T01–03／期限 | 已有有限合成三值、事实／来源变化、历史与局部修订算法和工程证据；剩余固定用例应按各自 oracle 复用或执行合成技术核查。正式领域事实／真实期限承诺才需要对应来源，不能据此重做原算法或推断真实性。 |')
s=s.replace('按原固定场景执行；缺来源保持UNKNOWN，不编SLA、不打开非法停表。','合成规则／日历可用于明示的技术场景；按原固定 oracle 验，不宣称真实适用。真实来源缺项保持UNKNOWN，不编SLA、不打开非法停表。')
s=s.replace('| AT33，F3-T05 第二园区 | 既有限定合成配置／冷输入不能代表第二真实园区重新授权迁移。 |','| AT33，F3-T05 第二园区 | 合成配置迁移与隔离技术核查允许按原计划执行；既有限定合成配置／冷输入不能代表第二真实园区重新授权迁移。 |')
s=s.replace('| AT32，来源与效果声明 | 没有真实试点、真实用户材料／履约／收益证据可支撑效果主张。 | 原方案允许无试点时只核来源和披露完整性；限定技术版如实写无真实效果证据，不额外制造必须先做试点的PR0门。若提出真实价值主张，需合法来源、实际使用／反馈及可追溯结果，合成或专家检查不代替。 |','| AT32，来源与效果声明 | 本轮按冻结受审包执行无试点来源／披露核查，执行结果与限定见 [AT32 回执](AT32SourceDisclosureValidation-20261018.md)。没有真实试点、真实用户材料／履约／收益证据。 | 此门可在现有授权内核查，无须先取得正式来源合同或做试点。若新增来源／报告主张须重核；若提出真实价值主张，才需对应合法来源、实际使用／反馈及可追溯结果。合成或代码独审不代替园区上线。 |')
s=s.replace('在上述材料／环境已合法具备后，冻结每条case版本、初态／许可、oracle、预算、输入hash、服务／动作版本、允许人工作业与重置说明，按适用测试类型实际记录结果。','逐条选择原方案允许的测试类型，并只检查该用例实际需要的材料／环境；允许合成目录及 MOCK／FAULT／REPLAY，不把整套 PR0 固定 AT 一概挂到正式来源合同后。冻结该 case 版本、初态／许可、oracle、预算、输入hash、服务／动作版本、允许核查与重置说明，实际记录结果。')
s=s.replace('本次可交付的是确定性竞态结案、保全证据和本表。上述来源合同、真实Windows／模型环境与C0材料是下一实质交付的输入；收到对应合法材料后才选原方案对应切片，不用额外外围证明替代它们。','本次交付固定 AT32 无试点来源／披露核查、保全证据及收窄后的本表。正式来源专用接线、Windows、LIVE 效果及 C0 各自仅受其对应缺项限制；其他原计划允许的合成／MOCK／FAULT／REPLAY 固定用例可在现有授权内继续核查，优先复用已验结果，不增加外围功能。')
p.write_text(s,encoding='utf-8')
# Closed list: only explicit claims in this packet, not recursive verification of historical hyperlinks.
items=[]
def add(id,path,kind,mode,use,limit):
 b=(R/path).read_bytes();items.append(dict(id=id,path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),source_kind=kind,original_execution_mode=mode,review_use=use,limitation=limit))
add('spec','docs/验收规格.json','PROJECT_DERIVED_SPEC','NOT_RUN_TEMPLATE','固定 AT32 oracle；模板不改','本次实例单独回执，不回填所有 AT')
add('plan','docs/分阶段开发计划.md','USER_DESIGN_DERIVED','DESIGN_ONLY','§4/§10/§15及AT32允许合成技术核查与无试点披露','非现时比赛规则或实际效果')
add('product','docs/平台产品设计.md','USER_DESIGN_DERIVED','DESIGN_ONLY','§4合成目录及§15依赖按对应主张适用','不是获准真实来源合同')
add('v1_manifest','docs/sources/V1/manifest.json','USER_DESIGN_ARCHIVE','ARCHIVE','原件ID、size、lines、本地恢复LF后SHA','Library无独立上游hash')
for i,r in enumerate(json.loads((R/'docs/sources/V1/manifest.json').read_text())):add('v1_'+str(i), 'docs/sources/V1/'+r['name'],'USER_DESIGN_ARCHIVE','ARCHIVE','用户授权本项目保存开发与核查','不推定第三方公开再许可或真实事实')
add('document_review','docs/DocumentReview.md','PROJECT_SOURCE_REVIEW','DOCUMENT_REVIEW','来源缺项与外部参考历史说明','本次不重新验证链接；Sim2Act代码未收到')
add('ledger','docs/F1/DataLedger.md','PROJECT_DISCLOSURE','DOCUMENT_REVIEW','本次所有来源、用途、缺项分列','历史末句由本次修订更正，不伪改历史')
add('binding','docs/F1/ATBindings.json','PROJECT_TEST_BINDING','NOT_RUN_TEMPLATE','AT32仅一个archive工程selector','不把selector升级成四项oracle')
add('gates','docs/F2/RemainingDeliveryGates-20261018.md','PROJECT_DISCLOSURE','DOCUMENT_REVIEW','逐项依赖，不一概阻塞技术AT','完整项目仍IN_PROGRESS')
add('demo','docs/F2/LocalSyntheticDemoContract-20261017.md','SYNTHETIC_FIXTURE_CONTRACT','NO_MODEL_LOCAL','合成安装初态／现有身份权限与NO_MODEL','不是真实授权或普通正式批准')
add('model_boundary','docs/F1/ModelBoundary.md','PUBLIC_REFERENCE_ONLY_AND_SYNTHETIC','MODEL_MOCK','协议引用、模拟输出及ENG007历史更正','本次无URL复核、真实模型调用或上游效果')
add('mock_output','docs/F1/evidence/http-smoke.json','SYNTHETIC_FIXTURE','MODEL_MOCK_LOCAL','LOCAL_CASE_CREATED及NEEDS_INPUT','非真实受理／履约；历史执行不重跑')
add('fault_output','docs/F1/evidence/eng003-gateway-smoke.json','SYNTHETIC_FIXTURE','FAULT_INJECTION_WITH_MODEL_MOCK','SIMULATED_RECORD与OUTCOME_UNKNOWN轨迹','非外部服务回执')
reuse='docs/F2/evidence/ordinary-reuse-user-flow-20261018/runtime/'
settled='docs/F2/evidence/receipt-submit-settled-order-20261018/runtime/'
add('reuse_output',reuse+'retained-tmp/frozen/test_two_new_ordinary_cases_re0/actual-material-reuse-user-flow.json','SYNTHETIC_FIXTURE','NO_MODEL_LOCAL_HTTP_PG_CHROMIUM','合成preview/provenance与下载hash','脚本角色不是外部用户反馈')
add('download',reuse+'retained-tmp/frozen/test_two_new_ordinary_cases_re0/target-downloaded-pack.txt','SYNTHETIC_FIXTURE','NO_MODEL_LOCAL_EXPORT','输出披露和实际导出hash','未核真实性／UNKNOWN／NOT_SUBMITTED／目标未完成')
add('settled_output',settled+'retained-tmp/frozen/test_new_recovery_fully_settle1/refresh-proof.json','SYNTHETIC_FIXTURE','LOCAL_HTTP_CHROMIUM_WITH_TRANSPORT_FAULT','旧403为既有另一fixture运输注入','不是当前撤权，未跑正式业务')
for id,base,n in [('reuse',reuse,43),('settled',settled,6)]:
 add(id+'_junit',base+'frozen.xml','ENGINEERING_TEST_RECORD','LOCAL_SYNTHETIC','原窗口'+str(n)+'唯一PASS计数','只读复核，不是本次重跑或全仓')
 add(id+'_independent',base+'independent-final-review.json','CODE_REVIEW_AND_TEST_RECORD','LOCAL_SYNTHETIC','独测'+str(4 if id=='reuse' else 2)+'全与主窗重叠','独立代码复核，不是园区专家／用户试点')
for id,name in [('reuse_report','MaterialReuseDOMValidation-20261018.md'),('settled_report','ReceiptSubmitSettledOrderValidation-20261018.md'),('history_report','OriginalCollaborationDOMValidation-20261018.md')]:
 add(id,'docs/F2/'+name,'PROJECT_ENGINEERING_REPORT','HISTORICAL_LOCAL_WINDOWS','核类型、范围、重叠、不抹历史失败或UNKNOWN','WINDOWS在此枚举指测试窗口；Windows操作系统仍NOT_RUN；不重审报告所有外链附件')
# Replace ambiguous window enum before freezing.
for x in items:
 if x['original_execution_mode']=='HISTORICAL_LOCAL_WINDOWS':x['original_execution_mode']='HISTORICAL_LOCAL_TEST_WINDOWS';x['limitation']='测试窗口；Windows原生仍NOT_RUN；只审本包列出的主张，非所有历史外链附件'
case=next(c for c in json.loads((R/'docs/验收规格.json').read_text())['cases'] if c['id']=='AT-32')
packet=dict(schema='parkweave-at32-disclosure-case/1',case_id='AT-32',case_version='2026-10-18-no-pilot-1',baseline_head='aaac5263f5694535758a11b5c38cce31e156cccf',fixed_case=case,fixed_case_sha256=hashlib.sha256(json.dumps(case,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),review_mode=['REPLAY','MANUAL_REVIEW_BY_CODEX'],reviewer_kind='assistant code/document reviewer; not park operator, customer or external domain expert',initial_state='只读冻结受审文件；没有真实试点材料或反馈输入；不创建数据库、身份、Grant、目录、分派或批准',budget=dict(per_engineering_command_seconds=120,automatic_retries=0,model_calls=0,db_connections=0,network_during_case_review=0),reset='N/A：只读历史证据与项目披露，无生产或测试业务状态变化；新增本地回执文件独立保存',dependencies=['Python 3.12 / existing pinned .venv','stdlib hashlib/json/xml/ast; existing acceptance runner and pytest'],closed_scope='本文件列明输入、输出、反馈分类及报告主张。历史链接不是递归核查范围；本次报告只引用本清单文件及新执行证据。新材料或效果主张需要重核。',files=items,clauses=[
 dict(id='INPUT',steps='核对V1 manifest字节/行/SHA/LF、授权用途与无上游hash限制；逐行阅读ledger和demo来源/初态/公开引用限制。',evidence=['v1_manifest','v1_0','v1_1','document_review','ledger','demo','model_boundary'],expected='设计／自建合成／公开参考／未提供真实资料分别标型；不假造许可、真实身份或正式来源。'),
 dict(id='OUTPUT',steps='读取mock、fault、材料包及preview/provenance、旧403记录，核对原mode、合成标签、下载hash及状态限制；不以此次REPLAY覆盖原类型。',evidence=['mock_output','fault_output','demo','reuse_output','download','settled_output'],expected='MODEL_MOCK、NO_MODEL LOCAL、FAULT分列；无LIVE或真实受理／履约效果主张。'),
 dict(id='FEEDBACK',steps='核对ledger缺项与独审记录的操作者、场景、overlap和scope，明确代码独审／自动化角色不是外部园区使用反馈。',evidence=['ledger','reuse_independent','settled_independent','reuse_report','settled_report'],expected='真实试点、访谈、满意度及外部专家反馈未提供；无收益／效率数字，不当作上线。'),
 dict(id='REFERENCES',steps='逐件核受审文件hash；解析两主窗JUnit和独测subset计数；核报告的类型与限制、历史失败/UNKNOWN披露；固定spec和runner模板不改。',evidence=['spec','plan','product','binding','gates','reuse_report','settled_report','history_report','reuse_junit','settled_junit','reuse_independent','settled_independent'],expected='本报告主张均可定位受审证据；43/独4、6/独2分窗且重叠，不相加；无全项目/Windows/LIVE/现实效果结论。')],verdict_policy='四项实际逐条核查完整且无未披露缺项才给本AT32无试点披露实例PASS；缺项如实记INCOMPLETE/FAIL。工程selector只给PARTIAL_PASS，所有通用whole_status保持NOT_RUN。')
(R/'docs/F2/AT32SourceDisclosureCase-20261018.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'packet_files':len(items),'packet_sha256':sha('docs/F2/AT32SourceDisclosureCase-20261018.json'),'ledger_history_prefix_preserved':ledger.read_text().startswith(old)}))
