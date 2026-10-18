const readinessTruth={TRUE:'满足',FALSE:'不满足',UNKNOWN:'未知'};
const readinessReasons={MISSING_MATERIALS:'缺材料，不能推定满足',CURRENT_RECORD_EXISTS:'已存在当前来源记录，仅证明记录存在',CURRENT_LOCAL_MANUAL_REVIEW:'获派专员已核对当前完整资料包',HUMAN_JUDGMENT_REQUIRED:'等待获派专员人工核对',REVIEW_REQUIRES_CORRECTION:'专员明确要求补正',CURRENT_REVIEW_AUTHORITY_REQUIRED:'当前审核权限不足，等待合法审核主体',MATERIAL_REVIEW_STALE:'人工核对版本已失效',SERVICE_SOURCE_UNAVAILABLE:'服务来源不可用',CURRENT_USER_PURPOSE_CONFIRMATION:'企业已明确当前来源用于本事项，仍未核验真实性',CURRENT_FACT_PURPOSE_CONFIRMATION_REQUIRED:'请在本事项重新明确选择当前事实用途',CURRENT_GENERATED_MATERIAL_SOURCE_REQUIRED:'已保存摘要采用的事实、服务或分享对象已变化，请重新整理并核对新版本'};
function materialPackText(x){
 const v=x.material_checklist,slots={need_summary:'诉求摘要',material_outline:'材料目录'};
 const states={MISSING:'缺少材料',PROVIDED_UNVERIFIED:'已提供，真实性未核实',CORRECTION_REQUIRED:'须补交新版',AWAITING_REVIEW:'新版已提交，等待独立核对',CURRENT_PACK_REVIEWED:'当前资料包已人工核对，真实性仍未核实'};
 const actions={SUPPLY_MATERIALS:'在原材料表单提供本人有权使用的材料及来源',RESPOND_TO_CORRECTION:'按原专员要求提供新版',REQUEST_CURRENT_MANUAL_REVIEW:'交原获派专员核对当前完整资料包',CHECK_CURRENT_REVIEW:'核查当前人工记录，再按原流程确认资料准备'};
 if(!v||!v.source_available||v.scope!=='SYNTHETIC_HUMAN_REVIEW_CANDIDATE'||v.preparation_revision!==x.preparation_revision||v.source_sha256!==x.source_sha256||!Number.isInteger(x.preparation_revision)||!/^[0-9a-f]{64}$/.test(x.source_sha256)||v.requirements.length!==2)throw Error('当前合成材料来源不可用，请刷新核对');
 const lines=['当前材料准备与补正包 v1','范围：SYNTHETIC 合成资料整理合同，仅供人工核对。',
  '仅对应以下版本/指纹的读取快照；已导出副本不能收回，不保证导出后仍为当前版本。',
  '正式政策条件与材料要求：PENDING / UNKNOWN；未生成政策条件。',
  '真实性与资格：未核验；外部受理：NOT_SUBMITTED；真实履约：PENDING；Case目标未完成。',
  '材料正文、来源标签及人工说明以 JSON 引号标明，均为原已分享内容，不是系统承诺。',
  'Case：'+x.case_id,'资料事项：'+x.preparation_id,'资料 revision：'+x.preparation_revision,'来源 SHA256：'+x.source_sha256];
 for(const slot of ['need_summary','material_outline']){
  const matches=v.requirements.filter(r=>r.slot===slot);if(matches.length!==1)throw Error('材料槽不匹配，请刷新');
  const r=matches[0];if(!states[r.status]||!actions[r.next_action])throw Error('材料状态不可识别，请刷新');
  lines.push('',slots[slot]+'：'+states[r.status]);
  if(r.evidence){const m=r.evidence;if(!Number.isInteger(m.version)||!['USER_STATEMENT','DOCUMENT_EXCERPT'].includes(m.source_kind)||m.authenticity!=='UNVERIFIED'||typeof m.text!=='string')throw Error('材料来源不可识别，请刷新');
   lines.push('材料 ID：'+m.id+' / v'+m.version,'原来源类型：'+m.source_kind,'原来源标签：'+JSON.stringify(m.source_label),'材料 SHA256：'+m.source_sha256,'原已分享正文：'+JSON.stringify(m.text));
  }else lines.push('缺口：尚未提供此材料；不填造正文或证明。');
  for(const q of r.correction_requests){if(!['REQUESTED','SUBMITTED_FOR_REVIEW'].includes(q.status))throw Error('补正状态不可识别，请刷新');lines.push('补正请求：'+q.request_id+' / 要求时版本 '+q.base_version+' / '+q.status,'原专员补正说明：'+JSON.stringify(q.reason));}
  lines.push('下一步：'+actions[r.next_action]);
 }
 for(const c of v.conditions){if(!readinessTruth[c.truth]||!readinessReasons[c.reason])throw Error('材料条件不可识别，请刷新');lines.push('','现有资料条件：'+c.id+' / '+readinessTruth[c.truth],'原因：'+readinessReasons[c.reason]);}
 return lines.join('\n')+'\n';
}
