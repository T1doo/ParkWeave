"""Explicit versioned synthetic Case/resource association.

Current app-controlled dependencies are locked and compared before insertion.
The catalogue is SELECT-only and has no app update/publishing route: late
committed changes seen by the final response projection reject a first strict
confirmation, but an uncoordinated admin can still update after that last read
and before commit. Snapshot isolation does not close this interval. No formal
Approval, implicit cancellation, or catalogue-publication guarantee is created.
"""
import json
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from . import preparation as prep,resource_combinations as rc,resource_holds as rh
from .executor_receipts import bounded
from .store import Conflict,Denied,digest
SCOPE='SYNTHETIC_CASE_RESOURCE_ASSOCIATION_ONLY'
class Bind(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    combination_id: UUID=Field(strict=False)
    expected_preparation_revision: int=Field(ge=1)
    expected_link_revision: int=Field(ge=0)
    reason: str=Field(min_length=1,max_length=1000)
    expected_comparison_sha256: str|None=Field(default=None,pattern='^[a-f0-9]{64}$')

def _parent(store,c,token,id,write=False):
    p=rh._auth(store,c,token,write=write)
    row=prep.scoped(store,c,p,id,write=write)
    store.scoped_run(c,p,row['run_id'])
    return p,row

def _history(c,p,parent):
    return c.execute('SELECT * FROM case_resource_links WHERE case_id=%s AND owner_id=%s AND park_id=%s AND org_id=%s ORDER BY revision',(parent['case_id'],p['id'],p['park_id'],p['org_id'])).fetchall()

def _resource_locks(c,p,holds,write_ids=()):
    ids=sorted({h['resource_id'] for h in holds},key=str)
    for id in ids:rh._scope(c,p,id,write=id in write_ids)
    for id in ids:rh._lock(c,id,shared=id not in write_ids)
    return {id:rh._scope(c,p,id,write=id in write_ids) for id in ids}

def _reason(c,parent,g,holds,rules,now):
    if g['state']!='CONFIRMED' or any(h['state']!='CONFIRMED' for h in holds):return 'RESOURCE_CANCELLED'
    if any(h['ends_at']<=now for h in holds):return 'RESOURCE_WINDOW_ENDED'
    if any(not rules[h['resource_id']]['enabled'] or rules[h['resource_id']]['revision']!=h['resource_revision'] for h in holds):return 'RESOURCE_RULE_CHANGED'
    claim=c.execute('SELECT case_id FROM resource_case_claims WHERE combination_id=%s',(g['id'],)).fetchone()
    if claim and claim['case_id']!=parent['case_id']:return 'COMBINATION_BELONGS_TO_OTHER_CASE'
    return 'CURRENT'

def _view(c,p,parent,rows,event=None):
    groups={r['combination_id']:rc._group(c,p,r['combination_id']) for r in rows}
    members={id:rc._members(c,p,id) for id in groups}
    rules=rc._scope_lock(c,p,[h for hs in members.values() for h in hs])
    now=rh._now(c);items=[]
    for row in rows:
        g=rc._group(c,p,row['combination_id']);holds=rc._members(c,p,g['id'])
        flags=[]
        if parent['state']!='LOCAL_CONFIRMED' or parent['revision']!=row['preparation_revision'] or parent['review_sha256']!=row['preparation_sha256']:flags.append('PREPARATION_CHANGED')
        reason=_reason(c,parent,g,holds,rules,now)
        if reason!='CURRENT':flags.append(reason)
        document=row['snapshot'].get('binding_impact')
        if document:
            from .resource_plan_binding import impact_issues
            flags+=impact_issues(c,parent,document,g,holds,{h['resource_id']:rules[h['resource_id']] for h in holds},now)
        flags=sorted(set(flags))
        items.append(dict(binding_impact=row['snapshot'].get('binding_impact'),record=row,status='CURRENT' if not flags else 'NEEDS_RECHECK',reasons=flags,combination=rc._view(g,holds,now)))
        if document:items[-1]['source_status']='NEEDS_RECHECK' if flags else 'CURRENT'
    case=c.execute('SELECT state FROM cases WHERE id=%s',(parent['case_id'],)).fetchone()
    return dict(scope=SCOPE,case_id=parent['case_id'],case_state=case['state'],preparation_revision=parent['revision'],link_revision=rows[-1]['revision'] if rows else 0,current=items[-1] if items else None,history=items,event=event,server_time=now,offline_fulfillment='NO_EVIDENCE',external_acceptance='NOT_SUBMITTED',case_goal_completed=False,approval='NOT_IMPLEMENTED',execution_enabled=False,impact_history=[dict(link_id=i['record']['id'],revision=i['record']['revision'],source_status=i['source_status'],document=i['binding_impact']) for i in items if i['binding_impact']])

@bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=_parent(store,c,token,id)
        return _view(c,p,parent,_history(c,p,parent))

@bounded
def bind(store,token,id,key,data):
    fp=digest(json.dumps({'preparation_id':str(id),**data.model_dump(mode='json',exclude_none=True)},ensure_ascii=False,sort_keys=True,separators=(',',':')))
    with store.connect() as c:
        p,parent=_parent(store,c,token,id,write=True)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-resource-key:'+p['id']+':'+key,))
        old=c.execute('SELECT * FROM case_resource_links WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if old and (old['fingerprint']!=fp or old['preparation_id']!=id):raise Conflict('case resource request key fingerprint mismatch')
        rows=_history(c,p,parent)
        # Lock every previously referenced resource too: a response is one coherent snapshot.
        ids={data.combination_id,*[r['combination_id'] for r in rows]}
        groups={gid:rc._group(c,p,gid) for gid in ids};members={gid:rc._members(c,p,gid) for gid in ids}
        rules=_resource_locks(c,p,[h for hs in members.values() for h in hs],{h['resource_id'] for h in members[data.combination_id]})
        # Group and hold row locks cover direct concurrent source changes too.
        for gid in sorted(ids,key=str):
            groups[gid]=rc._group(c,p,gid,lock=True)
            members[gid]=rc._members(c,p,gid,lock=True)
        g=groups[data.combination_id];holds=members[g['id']]
        case=c.execute('SELECT id,run_id FROM cases WHERE id=%s FOR UPDATE',(parent['case_id'],)).fetchone()
        if not case or case['run_id']!=parent['run_id']:raise Denied('Case Run binding unavailable')
        if old:return _view(c,p,parent,rows,old)
        projection=None
        if data.expected_comparison_sha256 is not None:
            from . import resource_plan_binding as binding
            # The catalogue has SELECT-only app scope and no supported publishing
            # route. Do not manufacture UPDATE authority merely to obtain a row
            # lock: compare its complete current version again after the gate.
            comparison_plan=c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s FOR UPDATE',(id,)).fetchone()
            projection=binding.proposal(store,c,p,parent,data.combination_id)
            comparison=projection['comparison']
            if comparison['sha256']!=data.expected_comparison_sha256:raise Conflict('resource comparison changed; refresh and explicitly confirm again')
            if data.expected_preparation_revision!=comparison['preparation_revision'] or data.expected_link_revision!=comparison['link_revision']:raise Conflict('resource comparison revision changed; refresh and explicitly confirm again')
            if not comparison['can_confirm']:raise Conflict('resource comparison prerequisites require correction and recheck')
        from .controlled_plans import gate
        gate(store,c,parent,1)
        if projection is not None:
            # Gate locks its current dependencies and may persist an observation
            # that an already stale downstream check needs revalidation. That is
            # this transaction's own effect, not a concurrent plan edit. Bind the
            # final comparison to the locked plan before this observation while
            # resampling every source, state, permission, and time-derived issue.
            final=binding.proposal(store,c,p,parent,data.combination_id,comparison_plan=comparison_plan)
            if final['comparison']['sha256']!=data.expected_comparison_sha256 or not final['comparison']['can_confirm']:
                raise Conflict('resource comparison changed during confirmation; refresh and explicitly confirm again')
        if parent['state']!='LOCAL_CONFIRMED' or parent['revision']!=data.expected_preparation_revision:raise Conflict('current locally confirmed preparation required')
        revision=rows[-1]['revision'] if rows else 0
        if data.expected_link_revision!=revision:raise Conflict('stale Case resource link revision; refresh required')
        if revision>=64:raise Conflict('Case resource link history limit reached')
        # The final Case lock can wait across the reservation end. Sample the
        # database clock after that wait, immediately before checking freshness.
        now=rh._now(c)
        why=_reason(c,parent,g,holds,rules,now)
        if why!='CURRENT':raise Conflict(why)
        if rows and rows[-1]['combination_id']==g['id'] and rows[-1]['preparation_revision']==parent['revision']:raise Conflict('current Case association already recorded; no new version needed')
        new_id=uuid4()
        snapshot=rc._view(g,holds,now);snapshot=json.loads(json.dumps(snapshot,default=str))
        if projection is not None:
            snapshot['binding_impact']=binding.impact(projection,dict(id=new_id,revision=revision+1),data.expected_comparison_sha256,data.reason)
        c.execute('INSERT INTO resource_case_claims(combination_id,case_id,owner_id,park_id,org_id) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(g['id'],parent['case_id'],p['id'],p['park_id'],p['org_id']))
        row=c.execute('''INSERT INTO case_resource_links(id,preparation_id,case_id,run_id,owner_id,park_id,org_id,combination_id,revision,preparation_revision,preparation_sha256,service_id,service_version,reason,snapshot,actor_id,request_key,fingerprint)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',(new_id,id,parent['case_id'],parent['run_id'],p['id'],p['park_id'],p['org_id'],g['id'],revision+1,parent['revision'],parent['review_sha256'],parent['service_id'],parent['service_version'],data.reason,Jsonb(snapshot),p['id'],key,fp)).fetchone()
        from .controlled_plans import invalidate
        invalidate(c,id,2)
        result=_view(c,p,parent,rows+[row],row)
        if projection is not None and result['current']['source_status']!='CURRENT':
            # This is a first strict association, not historical-key recovery.
            # Reject a source change that this transaction has actually observed
            # after the final comparison (including one during INSERT waiting).
            # Plain SELECT cannot prevent an administrator from changing the
            # catalogue after this projection and before the connection commits.
            raise Conflict('resource binding source changed before commit; refresh and explicitly confirm again')
        return result

@bounded
def candidates(store,token,id):
    with store.connect() as c:
        p,parent=_parent(store,c,token,id)
        groups=c.execute('''SELECT g.* FROM synthetic_resource_combinations g WHERE principal_id=%s AND park_id=%s AND org_id=%s
           AND (SELECT count(*) FROM synthetic_resource_combination_members m JOIN synthetic_resource_holds h ON h.id=m.hold_id JOIN synthetic_resource_grants a ON a.resource_id=h.resource_id AND a.principal_id=h.principal_id AND a.park_id=h.park_id AND a.org_id=h.org_id WHERE m.combination_id=g.id AND a.capability='READ' AND a.active)=2
           ORDER BY created_at DESC,id DESC LIMIT 101''',(p['id'],p['park_id'],p['org_id'])).fetchall()
        members={g['id']:rc._members(c,p,g['id']) for g in groups[:100]};rules=rc._scope_lock(c,p,[h for hs in members.values() for h in hs]);now=rh._now(c)
        items=[]
        for g in groups[:100]:
            g=rc._group(c,p,g['id']);holds=rc._members(c,p,g['id']);reason=_reason(c,parent,g,holds,rules,now)
            if reason=='CURRENT':
                try:
                    for h in holds:rh._scope(c,p,h['resource_id'],write=True)
                except Denied:reason='RESOURCE_HOLD_PERMISSION_REQUIRED'
            items.append(dict(combination=rc._view(g,holds,now),eligible=reason=='CURRENT',reason=reason))
        blocked=None
        try:store.check_capability(c,p,'EXECUTE')
        except Denied:blocked='OWNER_EXECUTE_REQUIRED'
        return dict(scope=SCOPE,items=items,has_older_records=len(groups)>100,preparation_revision=parent['revision'],ready=parent['state']=='LOCAL_CONFIRMED' and blocked is None,blocked_reason=blocked,server_time=now)
