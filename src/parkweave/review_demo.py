"""Read-only review index over sealed, committed SYNTHETIC evidence.

It never connects to product PG or writes a Case, permission or Mock result to
product state. Interactive candidates run as separate apps and SQLite files.
"""
from pathlib import Path
import hashlib,json,re
from uuid import UUID
from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse

SOURCE_FILES={
 'request':'eng085-persistent-request-coverage.json',
 'plan':'eng084-case-plan-preview.json',
 'readiness':'eng086-source-bound-material-readiness.json',
 'rules':'eng088-isolated-rule-publication-candidate.json',
 'access':'eng089-single-run-access-candidate.json',
 'receipt':'eng032-dispatch-acceptance.json',
}
TITLES={'request':'1 原诉求与必需目标','plan':'2 方案覆盖与启用边界','readiness':'3 资料准备度','rules':'4 候选规则审核发布','access':'5 候选协作访问','receipt':'6 分派与本地回执'}
CHECKS={
 'request':[('original_request_preserved','原诉求保留'),('empty_explicit_goals_stay_unknown','空目标仍未知'),('unsupported_goal_saved_partial','不支持目标保留部分覆盖'),('page_reload_restores_request_goals_coverage','刷新恢复诉求和覆盖')],
 'plan':[('current_inputs_responsibility_outputs_acceptance_visible','前置、责任、产出和核验可见'),('unsupported_required_goal_preserved','不支持目标未抹掉'),('preview_no_business_or_plan_mutation','预览不自动办理')],
 'readiness':[('missing_materials_unknown','缺材料未知'),('current_manual_correction_false','明确补正不满足'),('local_manual_review_true_qualification_unknown','本地材料核对不判断资格'),('material_change_stales_old_true','修改使旧通过过期')],
 'rules':[('review_publish_separate','审核与候选发布分离'),('withdraw_preserves_history','撤回保留历史'),('expired_source_unknown_submission_rejected','过期来源拒绝使用')],
 'access':[('independent_approval','独立审批'),('revoked_cached_probe_denied','撤销后拒绝旧缓存'),('old_approval_replay_denied','旧批准重放拒绝'),('expiry_clears_cached_snapshot_and_denies_probe','到期清空快照并拒绝缓存')],
 'receipt':[('offer_decline_reoffer_withdraw_accept','拒绝、重新派送、撤回、本人接受'),('accepted_actor_is_executor','执行者本人接受'),('correction_acknowledgement_reopen','本地回执补正、确认、重开'),('application_creates_no_grants','应用没有创建授权')],
}
GAPS=[
 ('T01','资料真实性和跨材料事实裁决未完成；人工核对不证明真实性。'),
 ('T02','通用服务目录编排和全部必需目标覆盖未完成，当前是有限方案。'),
 ('T03','有限资源组合尚未全绑定正式Approval/ServicePlan规则。'),
 ('T04','真实新Run访问申请/审批未接入；Mock不写实际assignment。'),
 ('T05','局部事务与幂等不代表完整F2事件、未知结果闭环。'),
 ('T06','审核发布后的参数模板与完整冷新Case尚未形成。'),
 ('T07','同一新事项的诉求→规划→办理→核验、AT/视觉签收及Win11/F1/F2门仍未完成。'),
]

def _identifier(v):
    if not isinstance(v,str):return 'NOT_RECORDED'
    try:return str(UUID(v))
    except ValueError:return 'NOT_RECORDED'

class ReviewEvidence:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.seals=json.loads(Path(__file__).with_name('review_demo_sources.json').read_text())
        if set(self.seals)!=set(SOURCE_FILES) or any(not re.fullmatch('[0-9a-f]{64}',v) for v in self.seals.values()):raise ValueError('invalid sealed review source registry')
    def source(self,id):
        if id not in SOURCE_FILES:raise KeyError(id)
        relative='docs/F2/evidence/'+SOURCE_FILES[id];p=self.root/relative
        result={'id':id,'title':TITLES[id],'source':relative,'expected_sha256':self.seals[id],'state':'UNAVAILABLE','kind':'PRODUCT_CODE_HISTORICAL_SYNTHETIC_EVIDENCE' if id not in ('rules','access') else 'ISOLATED_MOCK_HISTORICAL_EVIDENCE','case_id':'NOT_RECORDED','run_id':'NOT_RECORDED','checks':[],'current_product_state':'NOT_READ','same_case_chain':False}
        try:
            if p.is_symlink() or not p.resolve().is_relative_to(self.root) or p.stat().st_size>512*1024:return result
            raw=p.read_bytes();actual=hashlib.sha256(raw).hexdigest();result['actual_sha256']=actual
            if actual!=self.seals[id]:result['state']='SOURCE_CHANGED_REVALIDATION_REQUIRED';return result
            data=json.loads(raw)
            if id in ('request','plan'):b=data['browser']
            elif id=='readiness':b=data['browser']['eng086-readiness-replay']['product']
            elif id in ('rules','access'):b=data['browser']['report']
            else:b=data['business_browser']
            result.update(state='VERIFIED_COMMITTED_EVIDENCE',case_id=_identifier(b.get('case_id')),run_id=_identifier(b.get('run_id')),checks=[{'label':label,'observed':b.get(field) if isinstance(b.get(field),bool) else None} for field,label in CHECKS[id]])
            return result
        except (OSError,ValueError,KeyError,TypeError):return result
    def path(self):
        return {'scope':'READ_ONLY_REVIEW_INDEX_NOT_A_SINGLE_CASE_BUSINESS_CHAIN','stages':[self.source(id) for id in SOURCE_FILES],'original_plan_gaps':[{'id':id,'gap':s} for id,s in GAPS],'current_product_database_connected':False,'product_state_written':False,'credentials_created':False,'actual_assignment_written':False,'case_goal_completed':False,'qualification_truth':'UNKNOWN','R4':'CLOSED','model_calls':0,'budget':0}

def create_review_app(root,mock_enabled=False,base_port=8770,instance_id='local-review'):
    if not 1024<=base_port<=65533:raise ValueError('bounded local port required')
    evidence=ReviewEvidence(root);app=FastAPI(title='ParkWeave local review index, real business disabled')
    @app.get('/',response_class=HTMLResponse)
    def page():return Path(__file__).with_name('review_demo_web.html').read_text()
    @app.get('/api/review/path')
    def path():return {**evidence.path(),'instance_id':instance_id,'isolated_mock_enabled':mock_enabled,'candidate_links':{'rules':f'http://127.0.0.1:{base_port+1}/','access':f'http://127.0.0.1:{base_port+2}/'}}
    @app.get('/api/review/source/{id}')
    def source(id:str):
        if id not in SOURCE_FILES:raise HTTPException(404,'not a registered review source')
        return evidence.source(id)
    @app.get('/__review_health')
    def health():return {'instance_id':instance_id,'kind':'hub','isolated_mock_enabled':mock_enabled}
    return app
