"""Bounded, owner-only reverse lookup for two existing shared source scopes.

Every Case retains its own original transaction/lock order. The start/end
manifests detect observed changes; this is not a cross-Case atomic snapshot or
protection against an uncoordinated administrator after the final read. Cursor
checksums are integrity checks, not signatures, authority, or visited-page proof.
"""
import json
import re
from uuid import UUID
from . import preparation as prep, controlled_plans as cp, registered_dependencies as deps
from . import service_case_steps as service, source_change_adoption as adoption, typed_source_impact as typed
from .store import Conflict, Denied
from .executor_receipts import bounded

SCOPE='CURRENT_OWNER_SHARED_SOURCE_CASES'
# Projection semantics and pagination proof evolve together; a future version
# must reject cursors issued by a different projection schema.
PROJECTION_SCHEMA=1
KINDS=('OWNER_RESOURCE_QUERY_SET','SERVICE_CATALOG_REFERENCE')
MAX_CANDIDATES=32
MAX_PAGE=20
MAX_CURSOR_BYTES=4096
MAX_MANIFEST_BYTES=4*1024*1024


def _source(c,p,parent,kind):
    if kind=='OWNER_RESOURCE_QUERY_SET':
        scope=dict(kind=kind,owner_id=p['id'],park_id=p['park_id'],org_id=p['org_id'],query_version=1)
        rows=c.execute('SELECT r.id,r.revision,r.source,r.capacity,r.buffer_seconds,r.open_from,r.open_until,r.enabled,r.namespace,r.authority,g.capability,g.active,r.xmin::text AS resource_epoch,g.xmin::text AS grant_epoch FROM synthetic_resources r JOIN synthetic_resource_grants g ON g.resource_id=r.id WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND r.park_id=g.park_id ORDER BY r.id,g.capability LIMIT 257',(p['id'],p['park_id'],p['org_id'])).fetchall()
        available=len(rows)<=256 and all(r['namespace']=='SYNTHETIC' and r['authority']=='LOCAL_AUTHORITY' and isinstance(r['source'],dict) and r['source'].get('kind')=='SYNTHETIC' for r in rows)
        data=[{k:v for k,v in r.items() if k not in ('resource_epoch','grant_epoch')} for r in rows]
        epochs=[{k:r[k] for k in ('id','capability','resource_epoch','grant_epoch')} for r in rows]
        extra=dict(query_version=1)
    else:
        scope=dict(kind=kind,park_id=p['park_id'],service_id=parent['service_id'],service_version=parent['service_version'])
        row=c.execute('SELECT xmin::text AS row_epoch FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',(p['park_id'],parent['service_id'],parent['service_version'])).fetchone()
        data=service._catalog(c,parent);epochs=row
        available=cp.binding_catalog_known(data)
        extra=dict(service_id=parent['service_id'],service_version=parent['service_version'])
    return dict(kind=kind,scope_sha256=cp._hash(scope),source_sha256=cp._hash(cp._normal(data)),source_epoch_sha256=cp._hash(cp._normal(epochs)),available=bool(available),**extra)


def _snapshot(store,token,id,kind):
    """One bounded enumeration, retaining no locks when individual Cases open."""
    with store.connect() as c:
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator' or parent['service_id']!=prep.SERVICE:raise Denied('original synthetic Case owner required')
        source=_source(c,p,parent,kind)
        authority=c.execute('SELECT id,park_id,org_id,role,active,xmin::text AS row_epoch FROM principals WHERE id=%s',(p['id'],)).fetchone()
        grants=c.execute("SELECT capability,active,revision,xmin::text AS row_epoch FROM capability_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s ORDER BY capability",(p['id'],p['park_id'],p['org_id'])).fetchall()
        prepare=c.execute('SELECT capability,active,xmin::text AS row_epoch FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s ORDER BY capability',(p['id'],p['park_id'],p['org_id'])).fetchall()
        rows=c.execute("""SELECT ca.id AS case_id,ca.run_id,ca.xmin::text AS case_epoch,r.xmin::text AS run_epoch,
            pr.id AS preparation_id,pr.xmin::text AS preparation_epoch,to_jsonb(pr) AS preparation
            FROM cases ca JOIN runs r ON r.id=ca.run_id
            LEFT JOIN preparations pr ON pr.case_id=ca.id AND pr.run_id=r.id
              AND pr.owner_id=r.principal_id AND pr.park_id=r.park_id AND pr.org_id=r.org_id
              AND pr.namespace='SYNTHETIC' AND pr.service_id=%s
            WHERE r.principal_id=%s AND r.park_id=%s AND r.org_id=%s
              AND ca.park_id=r.park_id AND ca.org_id=r.org_id AND ca.source='SYNTHETIC'
              AND r.namespace='SYNTHETIC' AND r.input->>'action'='case.create'
            ORDER BY ca.id LIMIT %s""",(prep.SERVICE,p['id'],p['park_id'],p['org_id'],MAX_CANDIDATES+1)).fetchall()
        overflow='CANDIDATE_SET_BOUND_EXCEEDED' if len(rows)>MAX_CANDIDATES else None
        rows=rows[:MAX_CANDIDATES]
        identities=[dict(case_id=str(r['case_id']),run_id=str(r['run_id']),preparation_id=str(r['preparation_id']) if r['preparation_id'] else None) for r in rows]
        versions=[];size=0
        if not overflow:
            for row in rows:
                parent_row=row['preparation']
                # All original snapshots, plan/Case/Run row versions and actual
                # adapter epochs are bound, including Cases outside this page.
                try:case_epochs=adoption.epochs(c,parent_row) if parent_row else None
                except Conflict:overflow='CASE_SOURCE_VERSIONS_UNAVAILABLE';break
                data=dict(case_epoch=row['case_epoch'],run_epoch=row['run_epoch'],preparation_epoch=row['preparation_epoch'],preparation=parent_row,
                          source_epochs_sha256=case_epochs)
                size+=len(prep.canonical(cp._normal(data)).encode())
                if size>MAX_MANIFEST_BYTES:overflow='CASE_MANIFEST_BOUND_EXCEEDED';break
                versions.append(cp._hash(cp._normal(data)))
        prep.grant(store,c,p,'PREPARE')
        stamp=dict(actor_ref=cp._hash(dict(actor_id=p['id'])),preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            source_ref=source,candidates_sha256=cp._hash(dict(identities=identities,overflow=overflow)),
            case_versions_sha256=cp._hash(versions),authority_sha256=cp._hash(cp._normal(dict(principal=authority,capabilities=grants,preparation=prepare))))
        return stamp,rows,overflow


def _cursor(value):
    if value is None:return None
    try:
        if not isinstance(value,str) or not 0<len(value.encode())<=MAX_CURSOR_BYTES:raise ValueError()
        def unique(pairs):
            result={}
            for key,item in pairs:
                if key in result:raise ValueError()
                result[key]=item
            return result
        data=json.loads(value,object_pairs_hook=unique)
        keys={'schema','actor_ref','preparation_id','source_kind','limit','offset','source_sha256','source_epoch_sha256','scope_sha256','candidates_sha256','case_versions_sha256','authority_sha256','sha256'}
        if not isinstance(data,dict) or set(data)!=keys or type(data['schema']) is not int or data['schema']!=PROJECTION_SCHEMA:raise ValueError()
        if data['source_kind'] not in KINDS or type(data['limit']) is not int or not 1<=data['limit']<=MAX_PAGE or type(data['offset']) is not int or not 0<data['offset']<MAX_CANDIDATES:raise ValueError()
        UUID(data['preparation_id'])
        for key in keys-{'schema','preparation_id','source_kind','limit','offset'}:
            if not isinstance(data[key],str) or not re.fullmatch('[a-f0-9]{64}',data[key]):raise ValueError()
        if data['sha256']!=cp._hash({k:v for k,v in data.items() if k!='sha256'}):raise ValueError()
        return data
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError):raise Conflict('shared source cursor invalid or stale')


def _basis(stamp,kind,limit,offset):
    source=stamp['source_ref']
    return dict(schema=PROJECTION_SCHEMA,actor_ref=stamp['actor_ref'],preparation_id=stamp['preparation_id'],source_kind=kind,limit=limit,offset=offset,
        source_sha256=source['source_sha256'],source_epoch_sha256=source['source_epoch_sha256'],scope_sha256=source['scope_sha256'],
        candidates_sha256=stamp['candidates_sha256'],case_versions_sha256=stamp['case_versions_sha256'],authority_sha256=stamp['authority_sha256'])


def _one(store,token,row,source):
    id=row['preparation_id'];parent=row['preparation'];saved=parent.get('service_case_plan') if parent else None
    valid_plan=isinstance(saved,dict) and isinstance(saved.get('id'),str) and type(saved.get('revision')) is int and 1<=saved['revision']<=64
    if valid_plan:
        try:UUID(saved['id'])
        except ValueError:valid_plan=False
    result=dict(case_id=str(row['case_id']),run_id=str(row['run_id']),preparation_id=str(id) if id else None,
        plan_id=saved['id'] if valid_plan else None,plan_revision=saved['revision'] if valid_plan else 0,relationship='UNKNOWN',
        state='NO_PREPARATION' if id is None else 'NO_PLAN',source_changed=None,affected=[],preserved=[],blocking_reasons=[],
        source_impact_sha256=None,source_impact_schema=None,case_state='NO_PLAN',case_affected=[],case_preserved=[],case_blocking_reasons=[])
    if id is None or saved is None:
        result['blocking_reasons']=['CASE_SOURCE_BASE_UNAVAILABLE'];return result
    if not valid_plan:
        result.update(state='UNKNOWN',blocking_reasons=['CASE_SOURCE_PROOF_UNAVAILABLE']);return result
    try:view=typed.read(store,token,id)
    except Denied:raise
    except Conflict:
        result.update(state='UNKNOWN',blocking_reasons=['CASE_SOURCE_PROOF_UNAVAILABLE']);return result
    if (view['case_id']!=str(row['case_id']) or view['run_id']!=str(row['run_id']) or view['plan_id']!=saved['id'] or view['plan_revision']!=saved['revision']):
        raise Conflict('shared source lookup stale; read again')
    graph=view['source_impact'];steps=view['steps'];all_ids=[s['id'] for s in steps]
    if isinstance(graph,dict) and type(graph.get('schema')) is int:result['source_impact_schema']=graph['schema']
    if not isinstance(graph,dict) or type(graph.get('schema')) is not int or graph['schema']!=1:
        result.update(state='UNKNOWN',case_state=view['state'],affected=all_ids,blocking_reasons=['SHARED_SOURCE_GRAPH_SCHEMA_UNSUPPORTED']);return result
    result.update(case_state=view['state'],case_affected=graph['affected'],case_preserved=graph['preserved'],case_blocking_reasons=view['blocking_reasons'],source_impact_sha256=graph['sha256'])
    if source['kind']=='OWNER_RESOURCE_QUERY_SET':
        dependent=any(s['adapter_id']=='P2' for s in steps);roots={'P2'}
        facets={'RESOURCE_QUERY_SET','DEPENDENCY_RESOURCE_QUERY_SET'}
    else:
        target=(source['service_id'],source['service_version'])
        current=(parent['service_id'],parent['service_version'])
        old=saved.get('binding',{}).get('catalog') or {}
        original=(old.get('service_id'),old.get('version'))
        dependent=target in (current,original);roots={'P1'};facets={'SERVICE_RULE'}
        if dependent and current!=original:
            result.update(state='UNKNOWN',relationship='SHARED_SOURCE',affected=all_ids,blocking_reasons=['SHARED_SOURCE_IDENTITY_CHANGED']);return result
    if not dependent:
        result.update(relationship='NOT_DEPENDENT',state='NOT_DEPENDENT',source_changed=False,preserved=all_ids);return result
    result['relationship']='SHARED_SOURCE'
    nodes=[n for n in graph['nodes'] if n['facet'] in facets and n['adapter_id'] in roots]
    if not source['available'] or graph['unknown_scope'] or not nodes or any(not n['known'] for n in nodes):
        result.update(state='UNKNOWN',affected=all_ids,blocking_reasons=['SHARED_SOURCE_COMPARISON_UNAVAILABLE']);return result
    changed=any(n['changed'] for n in nodes)
    # Source-specific roots only. Unrelated material/receipt differences remain
    # in case_affected and do not become consequences of this selected source.
    selected=[dict(adapter_id=s['adapter_id'],depends_on=[next(v['adapter_id'] for v in steps if v['id']==e['upstream']) for e in graph['edges'] if e['provenance']=='COMPILED_REGISTERED_ADAPTER' and e['downstream']==s['id']]) for s in steps]
    reached=deps.closure(selected,roots) if changed else set()
    result.update(state='CHANGED' if changed else 'UNCHANGED',source_changed=changed,
        affected=[s['id'] for s in steps if s['adapter_id'] in reached],preserved=[s['id'] for s in steps if s['adapter_id'] not in reached])
    return result


@bounded
def read(store,token,id,*,source_kind='OWNER_RESOURCE_QUERY_SET',limit=10,cursor=None):
    if source_kind not in KINDS or type(limit) is not int or not 1<=limit<=MAX_PAGE:raise Conflict('bounded shared source lookup required')
    initial,rows,overflow=_snapshot(store,token,id,source_kind)
    old=_cursor(cursor)
    offset=old['offset'] if old else 0
    expected=_basis(initial,source_kind,limit,offset)
    if old and (offset>=len(rows) or offset%limit or {k:v for k,v in old.items() if k!='sha256'}!=expected):raise Conflict('shared source lookup stale; read again')
    unknown=[overflow] if overflow else []
    items=[] if overflow else [_one(store,token,row,initial['source_ref']) for row in rows[offset:offset+limit]]
    final,_,final_overflow=_snapshot(store,token,id,source_kind)
    if final!=initial or final_overflow!=overflow:raise Conflict('shared source lookup stale; read again')
    if not initial['source_ref']['available']:unknown.append('CURRENT_SHARED_SOURCE_UNAVAILABLE')
    if any(x['state'] in ('UNKNOWN','NO_PLAN','NO_PREPARATION') for x in items):unknown.append('CASE_COMPARISON_INCOMPLETE')
    has_more=not overflow and offset+len(items)<len(rows)
    # A bounded manifest proves candidate identity/version coverage, not that
    # other pages were compared. Cursors also carry no visited-page evidence.
    if has_more or offset>0:unknown.append('CASE_PAGES_NOT_CHECKED')
    next_cursor=None
    if has_more:
        body=_basis(initial,source_kind,limit,offset+len(items));next_cursor=json.dumps({**body,'sha256':cp._hash(body)},sort_keys=True,separators=(',',':'))
    return dict(scope=SCOPE,projection_schema=PROJECTION_SCHEMA,read_only=True,automatically_replayed=False,actor_ref=initial['actor_ref'],preparation_id=str(id),case_id=initial['case_id'],run_id=initial['run_id'],
        source_kind=source_kind,source_ref=initial['source_ref'],candidate_count=len(rows) if not overflow else None,candidate_limit=MAX_CANDIDATES,page_limit=limit,
        candidates_sha256=initial['candidates_sha256'],case_versions_sha256=initial['case_versions_sha256'],items=items,has_more=has_more,next_cursor=next_cursor,
        enumeration_complete=not overflow,all_cases_checked=not overflow and offset==0 and len(items)==len(rows) and not unknown,
        unknown_scope='CURRENT_OWNER_CASE_SET' if unknown else None,blocking_reasons=unknown,state='UNKNOWN' if unknown else 'AVAILABLE',
        new_grants=False,automatic_execution=False,case_goal_completed=False,qualification_decision='NOT_EVALUATED')
