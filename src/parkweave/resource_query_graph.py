"""Original resource query/member evidence, never authority or history repair."""
from collections import defaultdict
from copy import deepcopy
from uuid import UUID
from . import controlled_plans as cp, dependency_graph as graph

SCOPE = 'RESOURCE_QUERY_MEMBERS_V1'
MAX_ROWS, MAX_MEMBERS = 256, 96
RESOURCE_FIELDS = ('id', 'revision', 'source', 'capacity', 'buffer_seconds',
                   'open_from', 'open_until', 'enabled')
QUERY_FIELDS = (*RESOURCE_FIELDS, 'capability', 'active')


def _rows(values):
    """Canonical original query fields, preserving actual inactive rows."""
    if not isinstance(values, list) or len(values) > MAX_ROWS:
        raise graph.GraphError('resource query row bound exceeded')
    rows = cp._normal(deepcopy(values));seen=set();resources={}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(QUERY_FIELDS) or
            str(UUID(row['id'])) != row['id'] or type(row['revision']) is not int or
            type(row['capacity']) is not int or type(row['buffer_seconds']) is not int or
            type(row['enabled']) is not bool or type(row['active']) is not bool or
            row['capability'] not in ('READ', 'HOLD')):
            raise graph.GraphError('original resource query shape unavailable')
        key=(row['id'],row['capability'])
        if key in seen:raise graph.GraphError('duplicate original query row')
        seen.add(key)
        rule={k:row[k] for k in RESOURCE_FIELDS}
        if row['id'] in resources and resources[row['id']] != rule:
            raise graph.GraphError('resource query rows disagree')
        resources[row['id']]=rule
    if len(resources)>MAX_MEMBERS:raise graph.GraphError('resource member bound exceeded')
    rows.sort(key=lambda row:(row['id'],row['capability']))
    return rows


def historical_rows(source):
    """Reconstruct only rows evidenced by original selected-rule/true grants.

    false proves no matching active grant, not whether an inactive row existed.
    Same-resource holds legitimately repeat the same true grant evidence.
    """
    if not isinstance(source,dict):return []
    rules=source.get('resource_rules');grants=source.get('resource_grants')
    if not isinstance(rules,list) or not isinstance(grants,list):return []
    if len(rules)>MAX_MEMBERS or len(grants)>MAX_ROWS*2:
        raise graph.GraphError('historical resource evidence bound exceeded')
    by_id={};states={}
    try:
        for rule in rules:
            if (not isinstance(rule,dict) or not set(RESOURCE_FIELDS)<=set(rule) or
                rule.get('namespace')!='SYNTHETIC' or rule.get('authority')!='LOCAL_AUTHORITY'):
                return []
            value={k:deepcopy(rule[k]) for k in RESOURCE_FIELDS}
            if rule['id'] in by_id and by_id[rule['id']]!=value:return []
            by_id[rule['id']]=value
        for grant in grants:
            if (not isinstance(grant,dict) or set(grant)!={'resource_id','capability','active'} or
                type(grant['active']) is not bool or grant['capability'] not in ('READ','HOLD') or
                grant['resource_id'] not in by_id):
                return []
            key=(grant['resource_id'],grant['capability'])
            if key in states and states[key]!=grant['active']:return []
            states[key]=grant['active']
        return _rows([{**rule,'capability':cap,'active':True}
            for id,rule in by_id.items() if states.get((id,'READ')) is True
            for cap in ('READ','HOLD') if states.get((id,cap)) is True])
    except (KeyError,ValueError,TypeError,AttributeError):
        return []


def _stamp(value):
    if (not isinstance(value,dict) or set(value)!={'known','count','sha256'} or
        type(value['known']) is not bool or type(value['count']) is not int or
        not 0<=value['count']<=MAX_ROWS+1 or not isinstance(value['sha256'],str) or
        len(value['sha256'])!=64 or any(c not in '0123456789abcdef' for c in value['sha256'])):
        return None
    return deepcopy(value)


def _basis(rows,stamp,historical):
    stamp=_stamp(stamp);sha=cp._hash(rows)
    complete=bool(stamp and stamp['known'] and stamp['count']==len(rows) and stamp['sha256']==sha)
    return dict(legacy_collection=stamp,observed_rows_sha256=sha,observed_row_count=len(rows),
        member_count=len({row['id'] for row in rows}),complete=complete,
        reason=None if complete else 'HISTORICAL_QUERY_ROWS_NOT_FULLY_SAVED' if historical
        else 'CURRENT_QUERY_NOT_FULLY_READABLE_OR_CHANGED')


def _members(rows):
    grouped=defaultdict(list)
    for row in rows:grouped[row['id']].append(row)
    return {id:graph.digest(dict(resource={k:own[0][k] for k in RESOURCE_FIELDS},
        query_grants=[{k:row[k] for k in ('capability','active')} for row in own]))
        for id,own in grouped.items()}


def _edge(upstream,downstream,kind,source_kind):
    value=dict(upstream=upstream,downstream=downstream,kind=kind,
               source_kind=source_kind,state='CONFIRMED')
    return dict(id='rqedge:'+graph.digest(value),**value)


def preview(parent,plan,before_source,current_rows,current_stamp,binding,locks):
    """Thin raw-source adapter over the reviewed versioned graph kernel."""
    try:
        if not any(s['adapter_id']=='P2' for s in plan['steps']):
            raise graph.GraphError('original resource consumer required')
        old=historical_rows(before_source);new=_rows(current_rows)
        bases=[_basis(old,before_source.get('resource_collection') if isinstance(before_source,dict) else None,True),
               _basis(new,current_stamp,False)]
        members=[_members(old),_members(new)]
        query='resource-query:'+graph.digest(dict(owner_id=parent['owner_id'],
            park_id=parent['park_id'],org_id=parent['org_id'],query_version=1))
        scope=dict(park_id=parent['park_id'],org_id=parent['org_id'],package_id=plan['id'])
        by_adapter={s['adapter_id']:s['id'] for s in plan['steps']}
        snapshots=[]
        for revision,(basis,values) in enumerate(zip(bases,members),1):
            nodes=[dict(id='resource:'+id,type='RESOURCE',case_id=None,
                revision_sha256=sha,source_kind='ACTUAL_SNAPSHOT') for id,sha in values.items()]
            nodes.append(dict(id=query,type='CAPACITY_SNAPSHOT',case_id=str(parent['case_id']),
                revision_sha256=(basis['legacy_collection']['sha256'] if basis['legacy_collection'] else
                    graph.digest(dict(missing='HISTORICAL_QUERY_STAMP'))),
                source_kind='ACTUAL_SNAPSHOT' if basis['legacy_collection'] else 'UNVERIFIED',
                collection=dict(complete=basis['complete'],members=[dict(id='resource:'+id,
                    revision_sha256=sha) for id,sha in values.items()])))
            nodes.extend(dict(id=s['id'],type='PLAN_STEP',case_id=str(parent['case_id']),
                revision_sha256=graph.digest({k:s[k] for k in ('id','adapter_id','depends_on')}),
                source_kind='COMPILED') for s in plan['steps'])
            edges=[_edge('resource:'+id,query,'CAPACITY','ACTUAL_SNAPSHOT') for id in values]
            if 'P2' in by_adapter:edges.append(_edge(query,by_adapter['P2'],'CAPACITY','COMPILED'))
            edges.extend(_edge(by_adapter[dep],s['id'],'PRECEDES','COMPILED')
                for s in plan['steps'] for dep in s['depends_on'])
            snapshots.append(graph.snapshot(dict(graph_id='resource-query:'+plan['id'],
                revision=revision,scope=scope,nodes=nodes,edges=edges)))
        impact=graph.preview(*snapshots);a,b=map(set,members);complete=all(v['complete'] for v in bases)
        membership=dict(state='KNOWN' if complete else 'UNKNOWN',
            semantics='QUERY_MEMBERSHIP_ONLY',before_complete=bases[0]['complete'],
            current_complete=bases[1]['complete'],
            added=sorted(b-a) if complete else [],removed=sorted(a-b) if complete else [],
            newly_observed=sorted(b-a) if not complete else [],
            no_longer_observed=sorted(a-b) if not complete else [],
            retained=sorted(a&b),changed=sorted(id for id in a&b if members[0][id]!=members[1][id]) if complete else [],
            observation_changed=sorted(id for id in a&b if members[0][id]!=members[1][id]) if not complete else [])
        value=dict(scope=SCOPE,binding=deepcopy(binding),query_node_id=query,
            before_basis=bases[0],current_basis=bases[1],before=snapshots[0],current=snapshots[1],
            impact=impact,membership=membership,current_manual_locks=deepcopy(locks),
            lock_conflicts=[dict(**lock,reason='LOCK_CONFLICT') for lock in locks if lock['node_id'] in impact['affected']],
            read_only=True,can_adopt=False,execution_authorized=False,authority_verified=False,
            new_grants=False,automatic_execution=False,history_rewritten=False,
            automatically_replayed=False,case_goal_completed=False,qualification_decision='NOT_EVALUATED')
        return {**value,'sha256':graph.digest(value)}
    except (KeyError,ValueError,TypeError,AttributeError):
        raise graph.GraphError('bounded original resource graph unavailable') from None


def read_rows(c,parent):
    """Same original row projection; filter private rows before their read."""
    rows=c.execute('''SELECT r.id,r.revision,r.source,r.capacity,r.buffer_seconds,
        r.open_from,r.open_until,r.enabled,g.capability,g.active
        FROM synthetic_resources r JOIN synthetic_resource_grants g ON g.resource_id=r.id
        WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND r.park_id=g.park_id
        AND r.namespace='SYNTHETIC' AND r.authority='LOCAL_AUTHORITY'
        AND EXISTS(SELECT 1 FROM synthetic_resource_grants readable
            WHERE readable.principal_id=g.principal_id AND readable.resource_id=r.id
            AND readable.park_id=g.park_id AND readable.org_id=g.org_id
            AND readable.capability='READ' AND readable.active)
        ORDER BY r.id,g.capability LIMIT 257''',
        (parent['owner_id'],parent['park_id'],parent['org_id'])).fetchall()
    return _rows(rows)
