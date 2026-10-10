"""Versioned declarations for the existing adapter subgraph, never new authority."""
from copy import deepcopy
from uuid import UUID
import re
from . import controlled_plans as cp
from .store import Conflict

VERSION=1
MAX_COLLECTION_ROWS=256
COLLECTION_LIMIT=MAX_COLLECTION_ROWS
DECLARATIONS={
    'P1':['REQUEST','MATERIAL','FACT','SERVICE_RULE','OWNER_AUTHORITY'],
    'P2':['MATERIAL','RESOURCE','RESERVATION','RESOURCE_RULE_COLLECTION'],
    'P3':['MATERIAL','DISPATCH','ACCEPTANCE','RUN_ACCESS_COLLECTION'],
    'P4':['MATERIAL','RECEIPT','RECEIPT_EVENT_COLLECTION','LOCAL_EXECUTION'],
    'P5':['MATERIAL','RESOURCE','ACCEPTANCE','RECEIPT','LOCAL_CASE_CHECK'],
}
COLLECTION_ROOTS={'resources':'P2','existing_access':'P3'}


def collections(store,c,parent):
    """Reuse only already readable owner resource and original Run access queries.

    The extra row detects overflow; an incomplete set never becomes known.
    Raw rows remain in this stack frame, not in plan history or role projections.
    """
    resources=c.execute('SELECT r.id,r.revision,r.source,r.capacity,r.buffer_seconds,r.open_from,r.open_until,r.enabled,g.capability,g.active FROM synthetic_resources r JOIN synthetic_resource_grants g ON g.resource_id=r.id WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND r.park_id=g.park_id ORDER BY r.id,g.capability LIMIT %s',
                        (parent['owner_id'],parent['park_id'],parent['org_id'],COLLECTION_LIMIT+1)).fetchall()
    access=c.execute("SELECT a.principal_id,a.active,to_jsonb(a)->'managed_access' AS managed_access,p.role,p.active AS principal_active,g.active AS read_active,g.revision FROM run_assignments a JOIN principals p ON p.id=a.principal_id AND p.park_id=a.park_id AND p.org_id=a.org_id LEFT JOIN capability_grants g ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id AND g.capability='READ' WHERE a.run_id=%s AND a.park_id=%s AND a.org_id=%s ORDER BY a.principal_id LIMIT %s",
                     (parent['run_id'],parent['park_id'],parent['org_id'],COLLECTION_LIMIT+1)).fetchall()
    for source in access:
        if source['managed_access'] is None:continue
        store.lock_principal(c,source['principal_id'])
        principal=c.execute('SELECT * FROM principals WHERE id=%s',(source['principal_id'],)).fetchone()
        source['effective_active']=bool(principal and principal['active'] and source['read_active'] and store.assignment_allowed(c,principal,parent['run_id']))
    return {name:dict(known=len(rows)<=COLLECTION_LIMIT,count=len(rows),sha256=cp._hash(cp._normal(rows)))
            for name,rows in (('resources',resources),('existing_access',access))}


def manifest(steps,values):
    selected={s.get('adapter_id',s.get('id')) for s in steps}
    basis=dict(version=VERSION,declarations={a:deepcopy(DECLARATIONS[a]) for a in sorted(selected)},
               edges=[dict(upstream=dep,downstream=s.get('adapter_id',s.get('id')),kind='PRECEDES',provenance='COMPILED_REGISTERED_ADAPTER')
                      for s in steps for dep in s['depends_on']],
               collections={name:deepcopy(values[name]) for name,root in COLLECTION_ROOTS.items() if root in selected})
    return {**basis,'sha256':cp._hash(basis)}


def validate(value):
    try:
        if (not isinstance(value,dict) or set(value)!={'version','declarations','edges','collections','sha256'} or
            type(value['version']) is not int or not 1<=value['version']<=64 or
            not isinstance(value['declarations'],dict) or len(value['declarations'])>5 or
            any(k not in DECLARATIONS or not isinstance(v,list) or len(v)>16 or any(not isinstance(x,str) or not 1<=len(x)<=80 for x in v) for k,v in value['declarations'].items()) or
            not isinstance(value['edges'],list) or len(value['edges'])>25 or
            any(not isinstance(e,dict) or set(e)!={'upstream','downstream','kind','provenance'} or e['upstream'] not in DECLARATIONS or e['downstream'] not in DECLARATIONS or e['kind']!='PRECEDES' or e['provenance']!='COMPILED_REGISTERED_ADAPTER' for e in value['edges']) or
            not isinstance(value['collections'],dict) or not set(value['collections'])<=set(COLLECTION_ROOTS)):
            raise ValueError()
        for v in value['collections'].values():
            if (not isinstance(v,dict) or set(v)!={'known','count','sha256'} or type(v['known']) is not bool or
                type(v['count']) is not int or not 0<=v['count']<=MAX_COLLECTION_ROWS+1 or
                (v['known'] and v['count']>MAX_COLLECTION_ROWS) or (not v['known'] and v['count']==0) or not re.fullmatch('[a-f0-9]{64}',v['sha256'])):raise ValueError()
        if value['sha256']!=cp._hash({k:v for k,v in value.items() if k!='sha256'}):raise ValueError()
    except (TypeError,KeyError,ValueError,AttributeError):raise Conflict('registered dependency proof invalid')


def closure(steps,roots):
    """Follow actual declared edges rather than sorting numeric adapter names."""
    reached=set(roots)&{s['adapter_id'] for s in steps}
    for _ in steps:
        reached|={s['adapter_id'] for s in steps if reached.intersection(s['depends_on'])}
    return reached


def plan_proof(parent,plan):
    """Dependency journal proof; existing VERIFY diagnostics keep their semantics."""
    try:
        from .service_case_steps import Adopt,_adopt_request
        latest=None;step_ids={s['id'] for s in plan['steps']}
        UUID(plan['id'])
        if (type(plan['revision']) is not int or not 1<=plan['revision']<=64 or
            not isinstance(plan['events'],list) or len(plan['events'])!=plan['revision'] or
            not 1<=len(plan['steps'])<=5 or len(step_ids)!=len(plan['steps'])):raise ValueError()
        for id in step_ids:UUID(id)
        event_ids=set();keys=set()
        if plan.get('dependency_manifest') is not None:
            original=plan['adoption_preview']['steps']
            if len(original)!=len(plan['steps']):raise ValueError()
            for step,source in zip(plan['steps'],original):
                if (step['contract']!=source or
                    (step['adapter_id'],step['adapter'],step['adapter_revision'],step['depends_on'])!=
                    (source['id'],source['adapter'],source['revision'],source['depends_on'])):raise ValueError()
        for n,event in enumerate(plan['events'],1):
            UUID(event['id'])
            legacy_key=(n==1 and event['action']=='ADOPT' and isinstance(event['request_key'],str) and
                        re.fullmatch(r'tc:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:ADOPT_PLAN',event['request_key']))
            if (type(event['revision']) is not int or event['revision']!=n or event['plan_id']!=plan['id'] or
                event['id'] in event_ids or type(event['actor_id']) is not str or type(event['request_key']) is not str or
                (event['actor_id'],event['request_key']) in keys or not (re.fullmatch('[A-Za-z0-9_-]{1,100}',event['request_key']) or legacy_key) or
                not isinstance(event['fingerprint'],str) or not re.fullmatch('[a-f0-9]{64}',event['fingerprint']) or
                type(event['coordination_only']) is not bool or type(event['reason']) is not str or not 1<=len(event['reason'])<=1000 or
                event['action'] not in ('ADOPT','BEGIN','REPORT_FAILURE','RETRY','VERIFY','LOCK','UNLOCK') or
                (n==1 and event['action']!='ADOPT') or (event['step_id'] is None if event['action']=='ADOPT' else event['step_id'] in step_ids) is not True):raise ValueError()
            event_ids.add(event['id']);keys.add((event['actor_id'],event['request_key']))
            if event['action']!='ADOPT':continue
            if (event['actor_id']!=parent['owner_id'] or event['coordination_only'] is not True or
                event['source_sha256'] is not None or event['sources'] is not None):raise ValueError()
            value=event.get('dependencies')
            if value is not None:validate(value)
            if n>1:
                patch=event['local_revision'];request=Adopt.model_validate(patch['request'])
                if (request.local_revision is not True or request.expected_plan_revision!=n-1 or
                    request.required_goals!=plan['required_goals'] or request.reason!=event['reason'] or
                    request.expected_request_revision!=plan['binding']['request_intent']['revision'] or
                    event['actor_id']!=parent['owner_id'] or event['step_id'] is not None or
                    event['coordination_only'] is not True or event['source_sha256'] is not None or event['sources'] is not None or
                    event['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**_adopt_request(request))) or
                    patch['previous_sha256']!=(latest['sha256'] if latest else None) or
                    set(patch)!={'request','previous_sha256','affected','preserved'} or
                    not isinstance(patch['affected'],list) or not isinstance(patch['preserved'],list) or not patch['affected'] or
                    len(patch['affected']+patch['preserved'])!=len(step_ids) or set(patch['affected']+patch['preserved'])!=step_ids or value is None):raise ValueError()
                affected,_=impact_between(plan['steps'],latest,value)
                if (value!=manifest(plan['steps'],value['collections']) or any(not v['known'] for v in value['collections'].values()) or
                    set(patch['affected'])!={s['id'] for s in plan['steps'] if s['adapter_id'] in affected} or
                    set(patch['preserved'])!={s['id'] for s in plan['steps'] if s['adapter_id'] not in affected}):raise ValueError()
            latest=value
        if latest!=plan.get('dependency_manifest'):raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('registered dependency journal proof invalid')


def impact_between(steps,saved,current):
    """Rebuild the decision from both immutable manifests, including uncertainty."""
    if saved is not None:validate(saved)
    validate(current)
    unknown=bool(saved is None or any(not v['known'] for v in current['collections'].values()) or
                 any(not v['known'] for v in saved['collections'].values()) or
                 any(saved[k]!=current[k] for k in ('version','declarations','edges')))
    roots=set(DECLARATIONS) if unknown else {COLLECTION_ROOTS[name] for name,value in current['collections'].items() if saved['collections'].get(name)!=value}
    # Extra/missing collection declarations are an uncertainty, not an empty match.
    if saved is not None and set(saved['collections'])!=set(current['collections']):unknown=True;roots=set(DECLARATIONS)
    return closure(steps,roots),unknown


def inspect(plan,values):
    current=manifest(plan['steps'],values)
    affected,unknown=impact_between(plan['steps'],plan.get('dependency_manifest'),current)
    return current,affected,unknown
