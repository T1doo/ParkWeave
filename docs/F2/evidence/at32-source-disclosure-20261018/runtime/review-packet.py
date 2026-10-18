"""One-off read-only AT32 evidence check; document judgments are listed separately below."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time,xml.etree.ElementTree as ET
R=Path.cwd();D=R/'.runtime/at32-source-disclosure-20261018';SOURCE='d74c7b4e22c648e125b5aa135d2506e94242f76e';BASE='aaac5263f5694535758a11b5c38cce31e156cccf'
start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def digest(b):return hashlib.sha256(b).hexdigest()
packet_path='docs/F2/AT32SourceDisclosureCase-20261018.json';packet_bytes=(R/packet_path).read_bytes();P=json.loads(packet_bytes)
assert git('rev-parse','HEAD').decode().strip()==SOURCE and not git('status','--porcelain')
assert packet_bytes==git('show',SOURCE+':'+packet_path)
files={f['id']:f for f in P['files']}; checks=[]
for f in files.values():
 b=(R/f['path']).read_bytes();assert len(b)==f['bytes'] and digest(b)==f['sha256'] and b==git('show',SOURCE+':'+f['path']),f['id']
 checks.append(dict(id=f['id'],path=f['path'],bytes=len(b),sha256=digest(b),source_blob_equal=True))
def raw(id):return (R/files[id]['path']).read_bytes()
def obj(id):return json.loads(raw(id))
case=next(c for c in obj('spec')['cases'] if c['id']=='AT-32')
assert case==P['fixed_case'] and digest(json.dumps(case,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())==P['fixed_case_sha256']
assert case['status']=='NOT_RUN' and case['oracle']=='各类分列；无真实试点就明确无证据；不能把校园模拟/专家检查当园区上线'
archive=[]
for i,item in enumerate(obj('v1_manifest')):
 b=raw('v1_'+str(i));assert len(b)==item['size'] and len(b.splitlines())==item['lines'] and digest(b)==item['sha256'] and b.endswith(b'\n') and item['terminal_newline_restored'] is True
 archive.append(dict(name=item['name'],bytes=len(b),lines=len(b.splitlines()),sha256=digest(b),upstream_hash='NOT_PROVIDED'))
m=obj('mock_output');assert m['health']['data']=='SYNTHETIC' and m['run']['model_mode']=='MODEL_MOCK' and m['run']['success_scope']=='LOCAL_CASE_CREATED' and m['run']['case']['state']=='NEEDS_INPUT' and m['run']['case']['external_acceptance']=='NOT_SUBMITTED' and m['run']['case']['offline_fulfillment']=='NO_EVIDENCE'
f=obj('fault_output');assert f['type']=='FAULT_INJECTION' and f['real_model_calls']==0 and f['result']['operation']['receipt']['effect']=='SIMULATED_RECORD'
u=obj('reuse_output');assert u['scope'].startswith('SYNTHETIC_LOCAL_') and u['real_model_calls']==0 and u['real_business']=='NOT_RUN' and u['Windows']=='NOT_RUN' and u['initial_business_rows']==0
assert digest(raw('download'))==u['target_pack']['sha256']
assert all(s in raw('download').decode() for s in ['SYNTHETIC','UNKNOWN','未核验','NOT_SUBMITTED','Case目标未完成'])
s=obj('settled_output');assert s['old_status']==403 and s['old_403_transport_injection']=='existing other-tenant token used only for captured read' and s['completion_order']=='new_settled_then_old'
assert all(p['view']['scope'].startswith('SYNTHETIC') and p['view']['external_acceptance']=='NOT_SUBMITTED' and p['view']['offline_fulfillment']=='NO_EVIDENCE' and not p['view']['case_goal_completed'] for p in s['phases'])
counts=[]
for prefix,n,k,key in [('reuse',43,4,'overlap_in_parent43'),('settled',6,2,'overlap_in_main6')]:
 cases=list(ET.fromstring(raw(prefix+'_junit')).iter('testcase'));ids=[(c.get('classname'),c.get('name')) for c in cases]
 assert len(cases)==n and len(set(ids))==n and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
 ind=obj(prefix+'_independent');assert ind['passed']==k and ind[key]==k and ind['failures']==ind['errors']==ind['skipped']==0
 counts.append(dict(window=prefix,root_junit_unique_passed=n,independent_report_passed=k,independent_report_overlap=k,overlap_verification='existing independent JSON statement; no new per-ID independent rerun',new_business_tests=0))
assert all(x['whole_status']=='NOT_RUN' for x in obj('binding')['cases'])
old=json.loads(git('show',BASE+':docs/F1/ATBindings.json'));delta=[]
for before,after in zip(old['cases'],obj('binding')['cases']):
 if before!=after:
  assert before['id']==after['id']=='AT-32';delta.append('AT-32.gate');assert {k:v for k,v in before.items() if k!='gate'}=={k:v for k,v in after.items() if k!='gate'}
assert delta==['AT-32.gate']
protected={}
for name in ['src','tests','scripts','pyproject.toml','docs/验收规格.json']:
 a=git('rev-parse',BASE+':'+name).decode().strip();b=git('rev-parse',SOURCE+':'+name).decode().strip();assert a==b;protected[name]=a
# Actual document review observations: these are judgments by the assistant reviewer,
# not generated from keyword assertions, not external domain/user feedback.
review=[
 dict(id='INPUT',result='PASS',observations=[
  '两V1原件与manifest实测字节/行/本地SHA/LF一致；DocumentReview明确无独立上游hash，用户设计只作开发要求。',
  'ledger逐行区分用户设计、自建合成、公开协议参考和未提供真实来源；demo合同将身份/Grant/目录/分派列启动外显式合成初态。',
  '公开文献/协议URL本次未访问或验证现时内容，不推定Sim2Act代码取得、真实政策事实或第三方公开再许可。'
 ],evidence=P['clauses'][0]['evidence']),
 dict(id='OUTPUT',result='PASS',observations=[
  'F1历史http-smoke为MODEL_MOCK、LOCAL_CASE_CREATED且Case NEEDS_INPUT；故障窗口为SIMULATED_RECORD，不是现实履约。',
  'demo producer NO_MODEL，材料preview/provenance显式合成，导出文件实际SHA与记录相等；正文列UNKNOWN、真实性未验、未外部受理、Case目标未完成。',
  'settled旧403为另一fixture token的运输注入，未写作当前执行者撤权；本次REPLAY不改写原执行类型。'
 ],evidence=P['clauses'][1]['evidence']),
 dict(id='FEEDBACK',result='PASS',observations=[
  '本受审包未提供真实园区试点/访谈/满意度/外部专家反馈及节时/收益/完成率数据；ledger明示缺项，未以0%或虚构指标代替。',
  '独审是代码/测试镜像复核；fixture reviewer与企业CONFIRM是自动化角色路径，未解释成真实园区专家批准或用户使用反馈。',
  '本次助手文档核查不是新的用户调研或试点。结论仅无试点披露完整性。'
 ],evidence=P['clauses'][2]['evidence']),
 dict(id='REFERENCES',result='PASS',observations=[
  '24件有限清单全部与源提交Git blob及声明SHA/长度相等；固定AT32 oracle完整，未降低或回填模板状态。',
  '原root JUnit实核43/6唯一PASS；独审JSON分别声明4/2全重叠，不计新唯一数，不称本次重新跑业务或全项目通过。',
  '三历史报告明确合成/本地范围、旧开发失败及301/382/启动清理UNKNOWN；本次仅审核其披露，不重算所有链接附件或解释旧失败。',
  'RemainingDeliveryGates把真实合同限制对应接线和真实主张；技术AT不一概等待，Windows/LIVE/现实履约/C0仍各有适用缺项。'
 ],evidence=P['clauses'][3]['evidence'])]
assert git('rev-parse','HEAD').decode().strip()==SOURCE and not git('status','--porcelain')
result=dict(schema='parkweave-at32-disclosure-receipt/1',case_id='AT-32',case_version=P['case_version'],source_sha=SOURCE,packet_path=packet_path,packet_sha256=digest(packet_bytes),fixed_case_sha256=P['fixed_case_sha256'],review_mode=P['review_mode'],reviewer='Codex primary assistant; document and code review, not external park/customer expert',started_utc=started,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mechanical_check_elapsed_seconds=time.monotonic()-start,manual_review_timing='document review occurred before and during freeze; not a timed product/user trial',initial_state=P['initial_state'],reset=P['reset'],files=checks,archive_integrity=archive,original_window_counts=counts,protected_trees_equal_to_baseline=protected,binding_delta=delta,clauses=review,case_verdict='PASS',case_verdict_scope='固定AT32本实例：有限受审发布包，无真实试点时的来源与披露完整性；非真实效果或其他AT',whole_AT_EX='NOT_RUN',original_case_template_status='NOT_RUN',real_pilot='NO_EVIDENCE_IN_REVIEWED_PACKET',real_user_feedback='NOT_PROVIDED',real_effect_metrics='NOT_PROVIDED',new_product_runs=0,new_business_pytest_cases=0,real_model_calls=0,network_requests_during_review=0,db_connections=0,native_windows='NOT_RUN',automatic_retries=0)
(D/'case-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['case_id','source_sha','case_verdict','case_verdict_scope','whole_AT_EX','mechanical_check_elapsed_seconds']},ensure_ascii=False))
