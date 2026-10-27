"""Versioned explicit dependency previews. No discovery, persistence or authority."""
from collections import deque
from copy import deepcopy
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONTRACT = 'parkweave.dependency-graph/1'
LEGACY_SCOPE = 'BOUNDED_MULTI_SOURCE_V1'
MAX_NODES, MAX_EDGES, MAX_MEMBERS, MAX_UNKNOWN = 128, 256, 512, 32
Id = Annotated[str, Field(pattern=r'^[A-Za-z0-9_.:-]{1,80}$')]
Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Kind = Literal['REQUEST', 'FACT', 'SOURCE', 'SERVICE_RULE', 'RESOURCE',
               'CAPACITY_SNAPSHOT', 'PLAN_STEP', 'RESERVATION', 'MATERIAL',
               'RECEIPT', 'CHECK', 'RELEASE']
Source = Literal['COMPILED', 'ACTUAL_SNAPSHOT', 'HUMAN_CONFIRMED',
                 'MODEL_CANDIDATE', 'UNVERIFIED']
EdgeKind = Literal['ELIGIBILITY', 'MATERIAL', 'CAPACITY', 'PRECEDES',
                   'SEMANTIC', 'VERIFIED_BY', 'PACKAGED_IN']


class GraphError(ValueError):
    """Closed contract rejection; input values are never echoed."""


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Scope(Record):
    park_id: Id
    org_id: Id
    package_id: Id


class Member(Record):
    id: Id
    revision_sha256: Hash


class Collection(Record):
    complete: bool
    members: list[Member] = Field(max_length=256)


class Node(Record):
    id: Id
    type: Kind
    case_id: Id | None
    revision_sha256: Hash
    source_kind: Source
    locked_fields: list[Id] = Field(default_factory=list, max_length=16)
    collection: Collection | None = None


class Observation(Record):
    id: Id
    revision_sha256: Hash
    known: bool


class Edge(Record):
    id: Id
    upstream: Id
    downstream: Id
    kind: EdgeKind
    source_kind: Source
    state: Literal['CONFIRMED', 'CANDIDATE']
    observation: Observation | None = None


class Unknown(Record):
    id: Id
    kind: Literal['NODES', 'CASES', 'PACKAGE']
    node_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)
    case_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)
    reason: Id


class Graph(Record):
    contract: Literal['parkweave.dependency-graph/1'] = CONTRACT
    graph_id: Id
    revision: int = Field(ge=1, le=1_000_000)
    scope: Scope
    nodes: list[Node] = Field(min_length=1, max_length=MAX_NODES)
    edges: list[Edge] = Field(max_length=MAX_EDGES)
    unknown: list[Unknown] = Field(default_factory=list, max_length=MAX_UNKNOWN)
    legacy_sha256: Hash | None = None


def digest(value):
    """Only normalized contract records, never arbitrary business objects."""
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _unique(values):
    if len(values) != len(set(values)):
        raise GraphError('duplicate identity or relationship')


def snapshot(value):
    """Validate an explicit bounded DAG, copy and canonicalize without mutation."""
    try:
        graph = Graph.model_validate(value).model_dump(mode='json')
    except (ValidationError, TypeError, ValueError):
        raise GraphError('invalid bounded graph contract') from None
    nodes, edges = graph['nodes'], graph['edges']
    _unique([n['id'] for n in nodes])
    _unique([e['id'] for e in edges])
    _unique([(e['upstream'], e['downstream'], e['kind']) for e in edges])
    observations = [e['observation']['id'] for e in edges if e['observation']]
    _unique(observations)
    _unique([u['id'] for u in graph['unknown']])
    index = {n['id']: n for n in nodes}
    cases = {n['case_id'] for n in nodes if n['case_id'] is not None}
    member_count = 0
    for node in nodes:
        if node['type'] == 'PLAN_STEP' and node['case_id'] is None:
            raise GraphError('plan step requires explicit Case scope')
        _unique(node['locked_fields'])
        node['locked_fields'].sort()
        if node['collection'] is not None:
            members = node['collection']['members']
            _unique([m['id'] for m in members])
            member_count += len(members)
            members.sort(key=lambda m: m['id'])
    if member_count > MAX_MEMBERS:
        raise GraphError('collection member bound exceeded')
    adjacency = {id: [] for id in index}
    incoming = dict.fromkeys(index, 0)
    for edge in edges:
        if edge['upstream'] not in index or edge['downstream'] not in index:
            raise GraphError('dangling edge')
        if edge['state'] == 'CONFIRMED' and (
                edge['kind'] == 'SEMANTIC' or edge['source_kind'] == 'MODEL_CANDIDATE'):
            raise GraphError('candidate or semantic edge cannot be confirmed')
        adjacency[edge['upstream']].append(edge['downstream'])
        incoming[edge['downstream']] += 1
    queue = deque(sorted(id for id, count in incoming.items() if not count))
    visited = 0
    while queue:
        visited += 1
        for target in adjacency[queue.popleft()]:
            incoming[target] -= 1
            if not incoming[target]:
                queue.append(target)
    if visited != len(nodes):
        raise GraphError('cyclic graph including candidate edges')
    for unknown in graph['unknown']:
        _unique(unknown['node_ids'])
        _unique(unknown['case_ids'])
        if unknown['kind'] == 'NODES':
            valid = (bool(unknown['node_ids']) and not unknown['case_ids'] and
                     set(unknown['node_ids']) <= index.keys())
        elif unknown['kind'] == 'CASES':
            valid = (bool(unknown['case_ids']) and not unknown['node_ids'] and
                     set(unknown['case_ids']) <= cases)
        else:
            valid = not unknown['node_ids'] and not unknown['case_ids']
        if not valid:
            raise GraphError('unknown range must be explicit within graph scope')
        unknown['node_ids'].sort()
        unknown['case_ids'].sort()
    for field in ('nodes', 'edges', 'unknown'):
        graph[field].sort(key=lambda row: row['id'])
    return {**graph, 'sha256': digest(graph)}


def _checked(value):
    if not isinstance(value, dict) or 'sha256' not in value:
        raise GraphError('versioned graph snapshot required')
    result = snapshot({k: v for k, v in value.items() if k != 'sha256'})
    if result != value:
        # Canonical arrays are part of the frozen snapshot, unlike raw input order.
        raise GraphError('snapshot hash or canonical shape changed')
    return result


def _edge_identity(edge):
    return (edge['upstream'], edge['downstream'], edge['kind'],
            edge['observation']['id'] if edge['observation'] else None)


def _uncertain(edge, nodes):
    return (edge['state'] == 'CANDIDATE' or edge['kind'] == 'SEMANTIC' or
            edge['source_kind'] in ('MODEL_CANDIDATE', 'UNVERIFIED') or
            nodes[edge['upstream']]['source_kind'] in ('MODEL_CANDIDATE', 'UNVERIFIED') or
            bool(edge['observation'] and not edge['observation']['known']))


def preview(before, current):
    """Compare explicit versions; one canonical witness per target/certainty.

    Union traversal retains dependencies removed from the current version.
    'definite' means a declared certain dependency changed, not verified truth.
    """
    before, current = _checked(before), _checked(current)
    if any(before[k] != current[k] for k in ('graph_id', 'scope', 'contract')):
        raise GraphError('graph identity or scope cannot change')
    if (current['revision'] < before['revision'] or
            (current['revision'] == before['revision'] and current != before)):
        raise GraphError('changed snapshot requires increasing revision')
    old = {n['id']: n for n in before['nodes']}
    new = {n['id']: n for n in current['nodes']}
    old_edges = {e['id']: e for e in before['edges']}
    new_edges = {e['id']: e for e in current['edges']}
    for id in old.keys() & new.keys():
        if (old[id]['type'], old[id]['case_id']) != (new[id]['type'], new[id]['case_id']):
            raise GraphError('stable node identity cannot be rebound')
    for id in old_edges.keys() & new_edges.keys():
        if _edge_identity(old_edges[id]) != _edge_identity(new_edges[id]):
            raise GraphError('stable edge identity cannot be rebound')
    old_observations = {e['observation']['id']: (e['id'], e['upstream'], e['downstream'])
                        for e in before['edges'] if e['observation']}
    for edge in current['edges']:
        observation = edge['observation']
        if observation and observation['id'] in old_observations and (
                old_observations[observation['id']] !=
                (edge['id'], edge['upstream'], edge['downstream'])):
            raise GraphError('stable consumer observation cannot be rebound')

    union = {**old, **new}
    adjacency = {id: [] for id in union}
    variants = []
    for graph, nodes in ((before, old), (current, new)):
        for edge in graph['edges']:
            variant = dict(edge=edge, graph_sha256=graph['sha256'],
                           edge_sha256=digest(edge), uncertain=_uncertain(edge, nodes))
            if any(v['edge_sha256'] == variant['edge_sha256'] and
                   v['edge']['id'] == edge['id'] and
                   v['uncertain'] == variant['uncertain']
                   for v in adjacency[edge['upstream']]):
                continue
            adjacency[edge['upstream']].append(variant)
            variants.append(variant)
    for outgoing in adjacency.values():
        outgoing.sort(key=lambda v: (v['edge']['id'], v['edge_sha256'], v['graph_sha256']))

    witnesses, walk_seen, queue = {}, set(), deque()

    def mark(id, uncertain, reason, trigger, path=(), *, propagate=True):
        key = (id, uncertain)
        if key not in witnesses:
            witnesses[key] = dict(node_id=id, certainty='UNCERTAIN' if uncertain else 'DEFINITE',
                                  reason=reason, trigger_id=trigger, path=list(path))
        if propagate and key not in walk_seen:
            walk_seen.add(key)
            queue.append((id, uncertain, reason, trigger, path))

    def follow(variant, uncertain, reason, trigger, path):
        edge = variant['edge']
        evidence = {k: variant[k] for k in ('graph_sha256', 'edge_sha256')}
        evidence.update(id=edge['id'], kind=edge['kind'],
                        upstream=edge['upstream'], downstream=edge['downstream'])
        mark(edge['downstream'], uncertain or variant['uncertain'], reason, trigger,
             (*path, evidence))

    changed_nodes = sorted(id for id in union if old.get(id) != new.get(id))
    changed_edges = sorted(id for id in old_edges.keys() | new_edges.keys()
                           if old_edges.get(id) != new_edges.get(id))
    for id in changed_nodes:
        node = new.get(id, old.get(id))
        uncertain = node['source_kind'] in ('MODEL_CANDIDATE', 'UNVERIFIED')
        reason = 'NODE_ADDED' if id not in old else 'NODE_REMOVED' if id not in new else 'NODE_CHANGED'
        mark(id, uncertain, reason, id, propagate=False)
        only_source_revision_changed = (
            id in old and id in new and node['type'] != 'PLAN_STEP' and
            not uncertain and
            {k: v for k, v in old[id].items() if k != 'revision_sha256'} ==
            {k: v for k, v in new[id].items() if k != 'revision_sha256'})
        for variant in adjacency[id]:
            edge = variant['edge']
            prior, latest = old_edges.get(edge['id']), new_edges.get(edge['id'])
            # Each observed consumer retains its own before/current version.
            if (only_source_revision_changed and prior and latest and prior['observation'] and
                    prior == latest and prior['observation']['known']):
                continue
            follow(variant, uncertain, reason, id, ())
    for variant in variants:
        edge = variant['edge']
        if edge['id'] in changed_edges:
            follow(variant, False, 'EDGE_OR_OBSERVATION_CHANGED', edge['id'], ())
        if edge['observation'] and not edge['observation']['known']:
            follow(variant, True, 'OBSERVATION_UNKNOWN', edge['observation']['id'], ())
    for graph in (before, current):
        nodes = {n['id']: n for n in graph['nodes']}
        for node in graph['nodes']:
            if node['collection'] is not None and not node['collection']['complete']:
                mark(node['id'], True, 'COLLECTION_INCOMPLETE', node['id'])
        for unknown in graph['unknown']:
            targets = (unknown['node_ids'] if unknown['kind'] == 'NODES' else
                       [id for id, n in nodes.items() if n['case_id'] in unknown['case_ids']]
                       if unknown['kind'] == 'CASES' else list(nodes))
            for id in sorted(targets):
                mark(id, True, 'EXPLICIT_UNKNOWN_RANGE', unknown['id'])
    while queue:
        id, uncertain, reason, trigger, path = queue.popleft()
        for variant in adjacency[id]:
            follow(variant, uncertain, reason, trigger, path)

    definite = sorted(id for id, uncertain in witnesses if not uncertain)
    uncertain = sorted(id for id, uncertain in witnesses if uncertain)
    affected = sorted(set(definite) | set(uncertain))
    conflicts = []
    for id in affected:
        fields = sorted(set(old.get(id, {}).get('locked_fields', [])) |
                        set(new.get(id, {}).get('locked_fields', [])))
        if fields:
            conflicts.append(dict(node_id=id, fields=fields, reason='LOCK_CONFLICT'))
    result = dict(contract=CONTRACT, graph_id=current['graph_id'], scope=deepcopy(current['scope']),
                  before_sha256=before['sha256'], current_sha256=current['sha256'],
                  changed_node_ids=changed_nodes, changed_edge_ids=changed_edges,
                  definite=definite, uncertain=uncertain, affected=affected,
                  preserved=sorted(new.keys() - set(affected)), removed=sorted(old.keys() - new.keys()),
                  propagation_reasons=[witnesses[k] for k in sorted(witnesses)],
                  lock_conflicts=conflicts,
                  unknown_ranges=[dict(version_sha256=g['sha256'], **deepcopy(u))
                                  for g in (before, current) for u in g['unknown']],
                  read_only=True, can_adopt=False, execution_authorized=False,
                  authority_verified=False, discovery_performed=False)
    return {**result, 'sha256': digest(result)}


def from_unified_v1(value):
    """Read a frozen schema2 comparison without altering its original hash.

    This checks self-consistency of the existing snapshot, not its authority or
    current business proofs. It never writes back into the historical format.
    """
    from . import controlled_plans as cp
    try:
        graph = deepcopy(value)
        if (type(graph['schema']) is not int or graph['schema'] != 2 or
                graph['scope'] != LEGACY_SCOPE or
                graph['sha256'] != cp._hash({k: v for k, v in graph.items() if k != 'sha256'})):
            raise GraphError('invalid legacy graph hash or version')
        nodes, observations, edges, steps = (graph[k] for k in
                                             ('nodes', 'observations', 'edges', 'step_endpoints'))
        if not (len(nodes) + len(steps) <= 96 and len(observations) <= 96 and len(edges) <= 128):
            raise GraphError('legacy graph bound exceeded')
        _unique([n['id'] for n in nodes] + [s['id'] for s in steps])
        _unique([o['id'] for o in observations])
        _unique([e['id'] for e in edges])
        by_observation = {o['id']: o for o in observations}
        by_node = {n['id']: n for n in nodes}
        step_ids = {s['id'] for s in steps}
        if (set(graph['affected']) & set(graph['preserved']) or
                set(graph['affected']) | set(graph['preserved']) != step_ids or
                graph['unknown_scope'] not in (None, 'THIS_CASE')):
            raise GraphError('legacy partition invalid')
        for node in nodes:
            actual = [o for o in observations if o['source_node_id'] == node['id']]
            if (not actual or sorted(node['observation_ids']) != sorted(o['id'] for o in actual) or
                    node['changed'] is not any(o['changed'] for o in actual) or
                    node['known'] is not all(o['known'] for o in actual)):
                raise GraphError('legacy shared observation mismatch')
        for observation in observations:
            if (observation['source_node_id'] not in by_node or observation['step_id'] not in step_ids or
                    type(observation['known']) is not bool or type(observation['changed']) is not bool or
                    observation['changed'] !=
                    ((observation['before_present'], observation['before_sha256']) !=
                     (observation['current_present'], observation['current_sha256']))):
                raise GraphError('legacy observation invalid')
        observed = []
        for edge in edges:
            if edge['id'] != cp._hash(dict(scope=LEGACY_SCOPE, edge={k: v for k, v in edge.items() if k != 'id'})):
                raise GraphError('legacy edge hash changed')
            if 'observation_id' in edge:
                observation = by_observation[edge['observation_id']]
                if (edge['upstream'], edge['downstream']) != (
                        observation['source_node_id'], observation['step_id']):
                    raise GraphError('legacy observation consumer rebound')
                observed.append(observation['id'])
            elif (edge['upstream'] not in step_ids or edge['downstream'] not in step_ids or
                  edge['kind'] != 'PRECEDES'):
                raise GraphError('legacy predecessor invalid')
        if sorted(observed) != sorted(by_observation):
            raise GraphError('legacy observation edges incomplete')
        scope = dict(park_id=graph['binding']['park_id'], org_id=graph['binding']['org_id'],
                     package_id=graph['plan_id'])
        snapshots = []
        for revision, prefix in ((1, 'before'), (2, 'current')):
            converted_nodes = []
            for node in nodes:
                observations_for_node = [o for o in observations if o['source_node_id'] == node['id']]
                converted_nodes.append(dict(id=node['id'], type=node['type'], case_id=None,
                    revision_sha256=digest(sorted((o['id'], o[prefix+'_present'], o[prefix+'_sha256'])
                                                  for o in observations_for_node)),
                    source_kind='ACTUAL_SNAPSHOT'))
            converted_nodes.extend(dict(id=s['id'], type='PLAN_STEP', case_id=graph['binding']['case_id'],
                                        revision_sha256=digest(s), source_kind='COMPILED') for s in steps)
            converted_edges = []
            for edge in edges:
                converted = {k: edge[k] for k in ('id', 'upstream', 'downstream', 'kind')}
                converted.update(source_kind='ACTUAL_SNAPSHOT' if 'observation_id' in edge else 'COMPILED',
                                 state='CONFIRMED')
                if 'observation_id' in edge:
                    observation = by_observation[edge['observation_id']]
                    converted['observation'] = dict(id=observation['id'], known=observation['known'],
                        revision_sha256=digest([observation[prefix+'_present'], observation[prefix+'_sha256']]))
                converted_edges.append(converted)
            unknown = ([dict(id='legacy-unknown', kind='CASES', case_ids=[graph['binding']['case_id']],
                             reason='LEGACY_UNKNOWN')] if graph['unknown_scope'] or graph['unknown_reasons'] else [])
            snapshots.append(snapshot(dict(graph_id=graph['plan_id'], revision=revision, scope=scope,
                nodes=converted_nodes, edges=converted_edges, unknown=unknown, legacy_sha256=graph['sha256'])))
        result = preview(*snapshots)
        if (set(result['affected']) & step_ids != set(graph['affected']) or
                set(result['preserved']) & step_ids != set(graph['preserved'])):
            raise GraphError('legacy partition not reproduced')
        return dict(before=snapshots[0], current=snapshots[1], preview=result,
                    legacy_sha256=graph['sha256'], legacy_history_unchanged=True)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise GraphError('legacy snapshot cannot be converted consistently') from None
