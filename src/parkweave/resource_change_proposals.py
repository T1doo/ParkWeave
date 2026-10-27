"""Finite V4 same-resource time alternatives; original commands retain authority.

A suggestion does not reserve, release, adopt or send anything. The owner must
explicitly create each original hold, confirm its original combination, inspect
and confirm the original Case binding comparison, and reverify actual outputs.
"""
from datetime import timedelta, timezone
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator
from . import case_resources as links, controlled_plans as cp, preparation as prep
from . import resource_combinations as rc, resource_holds as rh
from . import resource_plan_binding as binding, service_case_steps as steps
from . import registered_dependencies as dependencies
from .executor_receipts import bounded
from .store import Conflict, Denied

SCOPE='SYNTHETIC_V4_SAME_RESOURCE_TIME_ALTERNATIVES'


class Search(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    search_from: AwareDatetime
    search_until: AwareDatetime

    @field_validator('search_from','search_until')
    @classmethod
    def utc(cls,value):
        try:return value.astimezone(timezone.utc)
        except OverflowError as e:raise ValueError('UTC time outside supported range') from e

    @model_validator(mode='after')
    def window(self):
        if not timedelta(0)<self.search_until-self.search_from<=timedelta(hours=24):
            raise ValueError('positive search window of at most 24 hours required')
        return self


@bounded
def read(store,token,id,data):
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL lock_timeout='3s'")
        p=rh._auth(store,c,token)
        prep.grant(store,c,p,'PREPARE')
        parent=c.execute('SELECT * FROM preparations WHERE id=%s AND owner_id=%s AND park_id=%s AND org_id=%s',
                         (id,p['id'],p['park_id'],p['org_id'])).fetchone()
        if not parent or parent['namespace']!='SYNTHETIC':raise Denied('own synthetic preparation required')
        store.scoped_run(c,p,parent['run_id'])
        plan=parent.get('service_case_plan')
        if not plan or not steps._selection_plan(plan):raise Conflict('original adopted V4 plan required')
        projection=binding.proposal(store,c,p,parent)
        current=projection['current']['resource_link']
        if not current:raise Conflict('original Case resource link required')
        group=rc._group(c,p,current['record']['combination_id'])
        holds=rc._members(c,p,group['id']);rules=rc._scope_lock(c,p,holds)
        mapped={rid for step in plan['steps'] if step['adapter_id']=='P2'
                for mapping in step['contract'].get('instance_mappings',[])
                for rid in mapping['resources'].values()}
        if len(holds)!=2 or len(mapped)!=2 or {str(h['resource_id']) for h in holds}!=mapped:
            raise Conflict('exact selected two-resource mapping required')
        durations={h['ends_at']-h['starts_at'] for h in holds}
        if len(durations)!=1 or len({h['starts_at'] for h in holds})!=1:
            raise Conflict('same-start same-duration replacement profile required')
        duration=next(iter(durations))
        if not timedelta(0)<duration<=timedelta(hours=4) or duration>data.search_until-data.search_from:
            raise Conflict('search window must fit original bounded duration')
        blockers=list(projection['checkpoints']['P1']['issues'])
        if prep.case_write_blocked(c,parent):blockers.append('CASE_BUSINESS_WRITES_BLOCKED')
        if not projection['current']['grants']['EXECUTE']:blockers.append('OWNER_EXECUTE_REQUIRED')
        for h in holds:
            try:rh._scope(c,p,h['resource_id'],write=True)
            except Denied:blockers.append('RESOURCE_HOLD_PERMISSION_REQUIRED')
        collections=dependencies.collections(store,c,parent)
        _,affected,unknown=dependencies.inspect(plan,collections)
        if affected:blockers.append('DEPENDENCY_REVISION_REQUIRES_EXPLICIT_ADOPT')
        if unknown:blockers.append('UNKNOWN_DEPENDENCY_COLLECTION')
        now=rh._now(c)
        grid_count=(data.search_until-duration-data.search_from)//timedelta(minutes=15)+1
        scanned=min(grid_count,100);items=[];available_count=0
        observations=[]
        for index in range(scanned):
            start=data.search_from+index*timedelta(minutes=15);end=start+duration
            members=[];eligible=True
            for h in holds:
                r=rules[h['resource_id']]
                sample=rh.Preview(starts_at=start,ends_at=end,quantity=h['quantity'])
                try:
                    lo,hi=rh._window(r,sample,now)
                    peak=rh._peak(c,h['resource_id'],lo,hi,now)
                    fits=peak+h['quantity']<=r['capacity']
                except (Conflict,OverflowError):peak=None;fits=False
                observations.append(dict(resource_id=str(r['id']),start=start,occupied_peak=peak,available=fits))
                eligible=eligible and fits
                members.append(dict(resource_id=str(r['id']),expected_revision=r['revision'],quantity=h['quantity'],
                                    starts_at=start,ends_at=end,buffer_seconds=r['buffer_seconds'],occupied_peak=peak))
            if eligible:
                available_count+=1
                if len(items)<10:items.append(dict(starts_at=start,ends_at=end,members=members))
        basis=cp._normal(dict(preparation={k:parent[k] for k in ('id','case_id','run_id','revision','review_sha256')},
            plan=dict(id=plan['id'],revision=plan['revision'],binding=plan['binding'],required_goals=plan['required_goals']),
            original_link=current['record'],original_combination=group,original_holds=holds,
            resource_rules=[rules[k] for k in sorted(rules,key=str)],grants=projection['current']['grants'],
            dependency_collections=collections,
            search=data.model_dump(),observations=observations,blockers=sorted(set(blockers))))
        for item in items:item['option_sha256']=cp._hash(cp._normal(dict(source_sha256=cp._hash(basis),**item)))
        return dict(scope=SCOPE,actor_ref=p['id'],preparation_id=str(id),case_id=str(parent['case_id']),
            required_goals=plan['required_goals'],plan_id=plan['id'],plan_revision=plan['revision'],
            source_binding_sha256=cp._hash(plan['binding']),dependency_collections=collections,
            preparation_revision=parent['revision'],link_revision=current['revision'],source_sha256=cp._hash(basis),
            current_issues=current['issues'],state='BLOCKED' if blockers else 'AVAILABLE' if items else 'NO_SOLUTION',
            blockers=sorted(set(blockers)),items=[] if blockers else items,
            search=data.model_dump(),scanned_candidates=scanned,available_candidates=available_count,
            grid_minutes=15,grid_exhausted=grid_count<=100,results_truncated=available_count>10,
            coverage='SAME_SELECTED_RESOURCES_SEARCH_WINDOW_GRID_ONLY',ordering='START_ASC',
            original_combination_id=str(group['id']),old_occupancy_released=False,
            explicit_original_hold_required=True,explicit_original_combination_required=True,
            explicit_current_binding_comparison_required=True,required_rechecks=['P2','P3','P4','P5'],
            business_writes=False,authorization_writes=False,automatic_execution=False,server_time=now,
            offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)


def _match(row,expected):
    if row and expected is not None and row['fingerprint']!=expected:
        raise Conflict('original request fingerprint mismatch')


def _outcome(p,key,*,status,**values):
    return dict(scope=SCOPE,actor_ref=p['id'],request_key=key,status=status,
                historical_only=True,automatically_replayed=False,business_writes=False,
                not_observed_does_not_prove_uncommitted=True,**values)


@bounded
def recover_resource(store,token,key,kind,expected_fingerprint=None):
    """Read only original keyed receipts, including a commit whose reply was lost."""
    if kind not in ('HOLD','COMBINATION'):raise Conflict('original resource recovery kind required')
    with store.connect() as c:
        p=rh._auth(store,c,token);rh._key(c,p,key)
        single=c.execute('SELECT * FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        group=c.execute('SELECT * FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        row=single if kind=='HOLD' else group
        if not row:
            if single or group:raise Conflict('original request contract mismatch')
            return _outcome(p,key,status='NOT_OBSERVED')
        _match(row,expected_fingerprint)
        if kind=='HOLD':
            if row['action'] not in ('HOLD','CONFIRM','RELEASE'):raise Conflict('original hold receipt required')
            hold=rh._own(c,p,row['hold_id']);rh._scope(c,p,hold['resource_id']);rh._lock(c,hold['resource_id'],shared=True)
            hold=rh._own(c,p,row['hold_id']);rh._scope(c,p,hold['resource_id'])
            value=dict(hold=rh._public(hold,rh._now(c)))
        else:
            if row['payload'].get('scope')!=rc.SCOPE:raise Conflict('original two-resource contract required')
            g=rc._group(c,p,row['combination_id']);hs=rc._members(c,p,g['id']);rc._scope_lock(c,p,hs)
            g=rc._group(c,p,g['id']);hs=rc._members(c,p,g['id'])
            value=dict(combination=rc._view(g,hs,rh._now(c)))
        return _outcome(p,key,status='COMMITTED',fingerprint=row['fingerprint'],receipt=row['payload'],**value)


@bounded
def recover_link(store,token,id,key,expected_fingerprint=None):
    with store.connect() as c:
        p,parent=links._parent(store,c,token,id)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-resource-key:'+p['id']+':'+key,))
        row=c.execute('SELECT * FROM case_resource_links WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if not row:return _outcome(p,key,status='NOT_OBSERVED')
        if row['preparation_id']!=id:raise Conflict('original Case binding request scope mismatch')
        _match(row,expected_fingerprint)
        g=rc._group(c,p,row['combination_id']);hs=rc._members(c,p,g['id']);rc._scope_lock(c,p,hs)
        return _outcome(p,key,status='COMMITTED',fingerprint=row['fingerprint'],record=row)
