"""Owner's recorded business queue; SELECT only, never a delivery verification."""
from uuid import UUID
from . import preparation as prep

SCOPE='CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST'
LABELS={
 'CANCELLED':('事项已撤销，保留历史','NONE','materials'),
 'RECONCILING':('撤销结果仍待核对，停止新办理','OWNER','materials'),
 'LOCAL_CLOSED':('本地记录已关闭，非现实履约完成','NONE','localcase'),
 'NEEDS_PREPARATION':('尚无本人可读取的资料准备','OWNER','run'),
 'NEEDS_MATERIALS':('资料待准备或重新核对','OWNER_AND_REVIEWER','materials'),
 'MATERIAL_CORRECTION':('专员要求补正资料','OWNER','materials'),
 'OWNER_CONFIRMATION':('资料已人工核对，待企业确认','OWNER','materials'),
 'NEEDS_DISPATCH':('资料已有本地确认，待专员分派','REVIEWER','dispatch'),
 'WAITING_ACCEPTANCE':('已分派，等待执行者本人接单','EXECUTOR','dispatch'),
 'NEEDS_REASSIGNMENT':('分派被拒绝或撤回，待专员处理','REVIEWER','dispatch'),
 'WAITING_RECEIPT':('本人已接单，等待回执','EXECUTOR','receipt'),
 'RECEIPT_CORRECTION':('回执已要求补正','EXECUTOR','receipt'),
 'OWNER_RECEIPT_REVIEW':('回执已记录，待企业核对','OWNER','receipt'),
 'LOCAL_ACKNOWLEDGED':('本地回执已有企业核对，仍须重验','OWNER','receipt'),
 'SOURCE_CHANGED':('资料版本已变化，原办理记录需重核','OWNER_AND_REVIEWER','materials'),
 'UNKNOWN':('当前记录无法一致核对','OWNER','run'),
}


def classify(case,parent,offer,step,local):
    if case['state'] in ('CANCELLED','RECONCILING'):return case['state']
    if local and local['state']=='LOCAL_RECORD_CLOSED':return 'LOCAL_CLOSED'
    if parent is None:return 'NEEDS_PREPARATION'
    state=parent['state']
    if state=='CHANGES_REQUESTED':return 'MATERIAL_CORRECTION'
    if state=='IN_PREPARATION':return 'NEEDS_MATERIALS'
    if state=='REVIEWED':return 'OWNER_CONFIRMATION'
    if state!='LOCAL_CONFIRMED':return 'UNKNOWN'
    source=offer or step
    if source and (source['preparation_revision']!=parent['revision'] or
                   source['preparation_sha256']!=parent['review_sha256']):return 'SOURCE_CHANGED'
    if offer:
        if offer['state']=='OFFERED':return 'WAITING_ACCEPTANCE'
        if offer['state'] in ('DECLINED','WITHDRAWN'):return 'NEEDS_REASSIGNMENT'
        if offer['state']!='ACCEPTED' or step is None:return 'UNKNOWN'
    if step:
        return {'AWAITING_RECEIPT':'WAITING_RECEIPT','CHANGES_REQUESTED':'RECEIPT_CORRECTION',
                'RECEIPT_RECORDED':'OWNER_RECEIPT_REVIEW','LOCAL_ACKNOWLEDGED':'LOCAL_ACKNOWLEDGED'}.get(step['state'],'UNKNOWN')
    return 'NEEDS_DISPATCH'


def read(store,token,*,limit=20,after=None):
    if type(limit) is not int or not 1<=limit<=50:raise ValueError('bounded Case page required')
    if after is not None and type(after) is not UUID:raise ValueError('Case UUID cursor required')
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        p=store.auth(c,token,lock=True);prep.grant(store,c,p,'PREPARE')
        # Auth waits use READ COMMITTED, so a completed revocation is re-read.
        # All business metadata comes from one statement snapshot, with no locks
        # or read-time plan invalidation calls.
        rows=c.execute("""SELECT ca.id,ca.run_id,ca.state,ca.goal,r.state AS run_state,
            CASE WHEN pr.id IS NULL THEN NULL ELSE jsonb_build_object('id',pr.id,
              'revision',pr.revision,'state',pr.state,'review_sha256',pr.review_sha256) END AS parent,
            CASE WHEN o.id IS NULL THEN NULL ELSE jsonb_build_object('state',o.state,
              'preparation_revision',o.preparation_revision,'preparation_sha256',o.preparation_sha256) END AS offer,
            CASE WHEN s.id IS NULL THEN NULL ELSE jsonb_build_object('id',s.id,'state',s.state,
              'preparation_revision',s.preparation_revision,'preparation_sha256',s.preparation_sha256) END AS step,
            CASE WHEN lc.preparation_id IS NULL THEN NULL ELSE jsonb_build_object('state',lc.state) END AS local,
            d.id IS NOT NULL AS dispatch_exists,
            EXISTS(SELECT 1 FROM service_receipt_steps old WHERE old.preparation_id=pr.id) AS receipt_exists
            FROM cases ca JOIN runs r ON r.id=ca.run_id
            LEFT JOIN preparations pr ON pr.case_id=ca.id AND pr.run_id=r.id
              AND pr.owner_id=r.principal_id AND pr.park_id=r.park_id AND pr.org_id=r.org_id
              AND pr.namespace='SYNTHETIC' AND pr.service_id=%s
            LEFT JOIN service_dispatches d ON d.preparation_id=pr.id
            LEFT JOIN service_dispatch_offers o ON o.dispatch_id=d.id AND o.id=d.current_offer_id
            LEFT JOIN LATERAL (SELECT rs.* FROM service_receipt_steps rs
              WHERE rs.preparation_id=pr.id AND rs.run_id=pr.run_id AND rs.case_id=pr.case_id
                AND rs.owner_id=pr.owner_id AND rs.park_id=pr.park_id AND rs.org_id=pr.org_id
                AND rs.service_id=pr.service_id AND rs.service_version=pr.service_version
                AND rs.namespace='SYNTHETIC' AND (
                 (d.id IS NOT NULL AND o.state='ACCEPTED' AND rs.id=o.receipt_step_id
                  AND rs.executor_id=o.executor_id AND rs.preparation_revision=o.preparation_revision
                  AND rs.preparation_sha256=o.preparation_sha256)
                 OR (d.id IS NULL AND (SELECT count(*) FROM service_receipt_steps legacy
                                       WHERE legacy.preparation_id=pr.id)=1))) s ON true
            LEFT JOIN case_local_lifecycles lc ON lc.preparation_id=pr.id AND lc.case_id=ca.id
            WHERE r.principal_id=%s AND r.park_id=%s AND r.org_id=%s
              AND ca.park_id=r.park_id AND ca.org_id=r.org_id
              AND ca.source='SYNTHETIC' AND r.namespace='SYNTHETIC'
              AND r.input->>'action'='case.create'
              AND (%s::uuid IS NULL OR ca.id>%s::uuid)
            ORDER BY ca.id LIMIT %s""",(prep.SERVICE,p['id'],p['park_id'],p['org_id'],after,after,limit+1)).fetchall()
        items=[]
        for case in rows[:limit]:
            parent,offer,step,local=(case[k] for k in ('parent','offer','step','local'))
            attention=classify(case,parent,offer,step,local) if case['run_state']=='SUCCEEDED' else 'UNKNOWN'
            if case['dispatch_exists'] and offer is None and attention not in ('CANCELLED','RECONCILING','LOCAL_CLOSED'):attention='UNKNOWN'
            if attention=='NEEDS_DISPATCH' and case['receipt_exists'] and step is None:attention='UNKNOWN'
            label,waiting_on,target=LABELS[attention]
            if parent is None:target='run'
            items.append(dict(case_id=str(case['id']),run_id=str(case['run_id']),title=case['goal'],
                preparation_id=str(parent['id']) if parent else None,
                preparation_revision=parent['revision'] if parent else None,
                case_state=case['state'],run_state=case['run_state'],attention=attention,label=label,waiting_on=waiting_on,
                open_target=target,receipt_step_id=str(step['id']) if step and target=='receipt' else None,
                evidence_verified=False,case_goal_completed=False,
                resource_release_required_separately=case['state'] in ('CANCELLED','RECONCILING')))
        return dict(scope=SCOPE,read_only=True,automatically_replayed=False,recorded_states_only=True,
                    items=items,next_after=str(rows[limit-1]['id']) if len(rows)>limit else None)
