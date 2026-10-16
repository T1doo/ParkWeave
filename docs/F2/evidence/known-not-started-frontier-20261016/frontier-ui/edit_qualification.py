from pathlib import Path
p=Path(__file__).parent/'candidate/src/parkweave/web.html';s=p.read_text();start=s.index('function approvalReplacementBinding(');end=s.index('function approvalBaseDeliveryBody(',start);old=s[start:end]
legacy=old.replace('function approvalReplacementBinding(', 'function approvalReplacementBindingV1(',1)
new=old.replace('function approvalReplacementBinding(', 'function approvalKnownNotStartedReplacementBinding(',1)
new=new.replace("automatic_adoption,automatic_approval,automatic_release')||b.schema!==1||b.profile!=='ORIGINAL_V4_SERVICE_RELEASE_PLAN_REPLACEMENT_V1'", "automatic_adoption,automatic_approval,automatic_release,qualification')||b.schema!==2||b.profile!=='ORIGINAL_V4_SERVICE_RELEASE_KNOWN_NOT_STARTED_V1'",1)
assert new!=old and "b.schema!==2" in new
new=new.replace(' return a;',' validateKnownNotStartedQualification(b.qualification,a,q.context);\n return a;',1)
qualification="""function validateKnownNotStartedQualification(value,anchor,context){
 const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(',')===keys.split(',').sort().join(','),uuid=v=>typeof v==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v),sha=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),b=value?.birth;
 if(!exact(value,'schema,profile,state,preparation_id,case_id,run_id,previous_plan_id,birth,birth_sha256,protocol_sha256,epoch,ever_started,collection_bound,collections,verified_prefix,tail')||value.schema!==1||value.profile!=='KNOWN_NOT_STARTED_V1'||value.state!=='KNOWN_NOT_STARTED'||value.previous_plan_id!==anchor.previous_plan_id||!['preparation_id','case_id','run_id'].every(k=>uuid(value[k])&&value[k]===context[k])||value.epoch!==0||value.ever_started!==false||value.collection_bound!==1||!sha(value.birth_sha256)||!sha(value.protocol_sha256)||!exact(b,'scope,schema,generation,preparation_id,case_id,run_id,owner_id,park_id,org_id,birth_xid')||b.scope!=='OWNED_SYNTHETIC_BUSINESS_FRONTIER_V1'||b.schema!==1||!uuid(b.generation)||!['preparation_id','case_id','run_id','owner_id','park_id','org_id'].every(k=>b[k]===context[k])||typeof b.birth_xid!=='string'||!/^\\d{1,24}$/.test(b.birth_xid))throw Error('未取得此原计划的完整有限资格；不能由空记录或提示推断尚未启动');
 const tables=['service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events'],empty='4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945';
 if(!Array.isArray(value.collections)||value.collections.length!==tables.length||!value.collections.every((item,i)=>exact(item,'table,count,complete,known,sha256')&&item.table===tables[i]&&item.count===0&&item.complete===true&&item.known===true&&item.sha256===empty))throw Error('原业务完整历史不能核对，资格保持未知');
 if(!Array.isArray(value.verified_prefix)||value.verified_prefix.length!==2||!value.verified_prefix.every((item,i)=>exact(item,'adapter_id,step_id,event_id,event_revision,source_sha256,event_sha256')&&item.adapter_id===['P1','P2'][i]&&uuid(item.step_id)&&uuid(item.event_id)&&Number.isSafeInteger(item.event_revision)&&item.event_revision>=1&&item.event_revision<=64&&sha(item.source_sha256)&&sha(item.event_sha256))||new Set(value.verified_prefix.map(v=>v.step_id)).size!==2||new Set(value.verified_prefix.map(v=>v.event_id)).size!==2||!exact(value.tail,'P3,P4,P5')||value.tail.P3!=='NEVER_DISPATCHED_OR_ACCEPTED'||value.tail.P4!=='NO_RECEIPT_EFFECT'||value.tail.P5!=='NO_LOCAL_LIFECYCLE_EFFECT')throw Error('原 P1/P2 核验与 P3–P5 有限资格不匹配');
 return value;
}
"""
wrapper="""function approvalReplacementBinding(c,q){
 const requested=c.frontierProfile??null,observed=q.replacement_frontier_profile??null;
 if(requested!==observed||requested!==null&&requested!=='KNOWN_NOT_STARTED_V1')throw Error('有限资格与本人原明确选择不匹配，请重新预检');
 return requested===null?approvalReplacementBindingV1(c,q):approvalKnownNotStartedReplacementBinding(c,q);
}
"""
s=s[:start]+wrapper+legacy+new+qualification+s[end:]
def edit(a,b):
 global s
 assert a in s,a[:120]
 s=s.replace(a,b,1)
edit("function approvalBaseDeliveryBody(c,q){const data=", "function approvalBaseDeliveryBody(c,q){if(c.frontierProfile&&!c.planReplacement)throw Error('有限资格只用于明确选择的整计划替换');const data=")
edit("data.expected_previous_plan_id=q.expected_previous_plan_id;}", "data.expected_previous_plan_id=q.expected_previous_plan_id;if(c.frontierProfile)data.replacement_frontier_profile=c.frontierProfile;}")
edit("if(q.expected_previous_plan_id!==undefined||q.context?.plan_replacement)throw Error", "if(q.expected_previous_plan_id!==undefined||q.replacement_frontier_profile!==undefined||q.context?.plan_replacement)throw Error")
edit("q.expected_previous_plan_id!==undefined||q.context?.source_reapproval||q.context?.plan_replacement)", "q.expected_previous_plan_id!==undefined||q.replacement_frontier_profile!==undefined||q.context?.source_reapproval||q.context?.plan_replacement)")
marker=" if(x.status==='COMMITTED'){target.dataset.state"
edit(marker," if(q.plan_replacement?.compatibility?.schema===2&&q.plan_replacement.compatibility.profile==='ORIGINAL_V4_SERVICE_RELEASE_KNOWN_NOT_STARTED_V1')target.append(textElement('p','原计划资格核对时点：P1、P2 的原核验记录已纳入依据；P3–P5 记录为尚未启动。后续办理须另读当前状态，本次新批准不代替逐步骤核验。'));\n"+marker)
p.write_text(s)
# Old version body remains byte-for-byte intact, apart from the dispatch name.
assert legacy.replace('function approvalReplacementBindingV1(', 'function approvalReplacementBinding(',1)==Path(__file__).parent.joinpath('legacy-validator-original.js').read_text()
