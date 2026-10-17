"""Bounded declarative selection and independent exhaustive coverage oracle.

Inputs are current, server-authorized synthetic releases and park instances.
This module confers no authority and performs no business action. Mapping states
mean current referenced objects exist and may be read, never evidence completion.
"""
from copy import deepcopy
from itertools import combinations
import json

from .intern_adapter import ModelBoundaryError, strict_json
from .planner_proposal import _json_tree, _equal
from . import bounded_planning as bp

MAX_RELEASES = 16
MAX_SELECTIONS = 16
ORACLE_GOAL_TARGETS = {
    'LOCAL_MATERIAL_PREPARATION': 'P1', 'LOCAL_CASE_RESOURCE_ASSOCIATION': 'P2',
    'LOCAL_INTERNAL_ACCEPTANCE': 'P3', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT': 'P4',
    'LOCAL_SYNTHETIC_COORDINATION_RECORDS': 'P4', 'LOCAL_CASE_RECORD_RECHECK': 'P5',
}
ORACLE_ADAPTERS = {
    'P1': ('preparation', []), 'P2': ('case-resources', ['P1']),
    'P3': ('dispatch', ['P2']), 'P4': ('executor-receipts', ['P3']),
    'P5': ('case-lifecycle', ['P4']),
}
REF_KEYS = frozenset(('release_id', 'revision', 'release_sha256', 'instance_id', 'config_revision', 'config_sha256'))


class SelectionError(ModelBoundaryError):
    def __init__(self):
        super().__init__('INVALID_SERVICE_SELECTION')


def selection_ref(release, instance):
    return dict(release_id=release['release_id'], revision=release['revision'],
                release_sha256=release['release_sha256'], instance_id=instance['instance_id'],
                config_revision=instance['config_revision'], config_sha256=instance['config_sha256'])


def _identity(ref):
    return (ref['release_id'], ref['revision'], ref['instance_id'], ref['config_revision'])


def parse_selection(raw, expected_binding):
    """Only exact trusted reference identities and the complete opaque binding."""
    try:
        if type(raw) not in (str, bytes):
            raise ValueError()
        encoded = raw.encode('utf-8') if type(raw) is str else raw
        if not 0 < len(encoded) <= 16384:
            raise ValueError()
        value = strict_json(encoded.decode('utf-8'))
        _json_tree(value)
        _json_tree(expected_binding)
        if (type(value) is not dict or set(value) != {'schema_version', 'binding', 'selections'}
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or not _equal(value['binding'], expected_binding)):
            raise ValueError()
        refs = value['selections']
        if type(refs) is not list or not 1 <= len(refs) <= MAX_SELECTIONS:
            raise ValueError()
        for ref in refs:
            if type(ref) is not dict or set(ref) != REF_KEYS:
                raise ValueError()
            for key in ('revision', 'config_revision'):
                if type(ref[key]) is not int or not 1 <= ref[key] <= 64:
                    raise ValueError()
            for key in ('release_id', 'instance_id'):
                if type(ref[key]) is not str or not 0 < len(ref[key]) <= 120:
                    raise ValueError()
            for key in ('release_sha256', 'config_sha256'):
                if type(ref[key]) is not str or len(ref[key]) != 64 or any(c not in '0123456789abcdef' for c in ref[key]):
                    raise ValueError()
        if len({_identity(ref) for ref in refs}) != len(refs):
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise SelectionError() from None


def _catalog(releases, instances, request, now):
    from .service_capability_contract import validate_release, validate_instance
    if type(releases) is not list or not 1 <= len(releases) <= MAX_RELEASES or type(instances) is not list or len(instances) > MAX_RELEASES:
        raise SelectionError()
    validated = [validate_release(value, now=now) for value in releases]
    by_release = {r['release_id']: r for r in validated}
    if len(by_release) != len(validated):
        raise SelectionError()
    pairs = []
    identities = set()
    for value in instances:
        release = by_release.get(value.get('release_id')) if type(value) is dict else None
        if release is None:
            raise SelectionError()
        instance = validate_instance(value, release, now=now)
        if instance['instance_id'] in identities:
            raise SelectionError()
        identities.add(instance['instance_id'])
        if instance['park_id'] == request['park_id']:
            pairs.append((release, instance))
    return sorted(pairs, key=lambda pair: _identity(selection_ref(*pair)))


def _request(request):
    if type(request) is not dict or set(request) - {'park_id', 'required_goals', 'planning_constraints', 'mapping_states'}:
        raise SelectionError()
    goals = request.get('required_goals')
    if (type(request.get('park_id')) is not str or type(goals) is not list or not 1 <= len(goals) <= 16
            or any(type(g) is not str or not g for g in goals) or len(goals) != len(set(goals))):
        raise SelectionError()
    constraints = request.get('planning_constraints') or {'excluded_roles': [], 'additional_requirements': []}
    if (type(constraints) is not dict or set(constraints) != {'excluded_roles', 'additional_requirements'}
            or type(constraints['excluded_roles']) is not list or type(constraints['additional_requirements']) is not list
            or len(constraints['excluded_roles']) > 3 or len(constraints['additional_requirements']) > 4
            or any(type(r) is not str or r not in ('enterprise_operator', 'park_specialist', 'service_executor') for r in constraints['excluded_roles'])
            or len(set(constraints['excluded_roles'])) != len(constraints['excluded_roles'])
            or any(type(r) is not str or not r.strip() or len(r) > 160 for r in constraints['additional_requirements'])):
        raise SelectionError()
    states = request.get('mapping_states', {})
    if type(states) is not dict or set(states) - {'principals', 'resources', 'fields'}:
        raise SelectionError()
    for values in states.values():
        if type(values) is not dict or any(type(k) is not str or type(v) is not str or v not in ('TRUE', 'FALSE', 'UNKNOWN') for k, v in values.items()):
            raise SelectionError()
    return goals, constraints, states


def _set_state(pairs, constraints, states):
    """Oracle evaluates semantics without calling the plan reconstruction."""
    unknowns = set()
    nodes, maps = {}, {'roles': {}, 'resources': {}, 'fields': {}}
    for release, instance in pairs:
        if set(release['role_keys']).intersection(constraints['excluded_roles']):
            return 'FALSE', []
        for group in maps:
            for key, value in instance[group].items():
                if key in maps[group] and not _equal(maps[group][key], value):
                    return 'FALSE', []
                maps[group][key] = value
        for step in release['steps']:
            registered = ORACLE_ADAPTERS.get(step['id'])
            if (registered is None or step['adapter'] != registered[0]
                    or type(step['revision']) is not int or step['revision'] != 1
                    or step['depends_on'] != registered[1]):
                return 'FALSE', []
            if step['id'] in nodes and not _equal(nodes[step['id']], step):
                return 'FALSE', []
            nodes[step['id']] = step
        needed = [('principals', item) for item in instance['roles'].values()]
        needed += [('resources', instance['resources'][item['resource_key']]) for item in release['resource_requirements'] if item['required']]
        needed += [('fields', instance['fields'][item['field_key']]['input_field']) for item in release['material_requirements']]
        for group, key in needed:
            status = states.get(group, {}).get(key, 'UNKNOWN')
            if status == 'FALSE':
                return 'FALSE', []
            if status == 'UNKNOWN':
                unknowns.add(f'{group}:{key}')
    if any(ORACLE_GOAL_TARGETS.get(goal) not in nodes for release, _ in pairs for goal in release['supported_goals']):
        return 'FALSE', []
    completed = set()
    for _ in nodes:
        completed.update(key for key, value in nodes.items() if set(value['depends_on']) <= completed)
    if completed != set(nodes):
        return 'FALSE', []
    unknowns.update('additional_requirement:' + value for value in constraints['additional_requirements'])
    return ('UNKNOWN' if unknowns else 'TRUE'), sorted(unknowns)


def enumerate_solutions(releases, instances, request, *, now=None):
    """Enumerate every inclusion-minimal legal set; preserve unknown vs false.

    The catalog is bounded to 16 park instances: at most 65,535 subsets. UNKNOWN
    means a covering subset cannot yet be proven legal. A known legal alternative
    does not erase this uncertainty, and no invented second graph is produced.
    """
    goals, constraints, states = _request(request)
    pairs = _catalog(releases, instances, request, now)
    return _enumerate_pairs(pairs, request, releases)


def _enumerate_pairs(pairs, request, available_releases=None):
    """Shared finite oracle; callers separately validate their source contract."""
    goals, constraints, states = _request(request)
    available_releases = [r for r, _ in pairs] if available_releases is None else available_releases
    supported = set().union(*(set(r['supported_goals']) for r in available_releases))
    unsupported = [goal for goal in goals if goal not in supported]
    solutions, unknown_sets, unknowns = [], [], set()
    examined = 0
    for size in range(1, len(pairs) + 1):
        for indices in combinations(range(len(pairs)), size):
            examined += 1
            group = [pairs[index] for index in indices]
            coverage = set().union(*(set(r['supported_goals']) for r, _ in group))
            if not set(goals) <= coverage:
                continue
            state, missing = _set_state(group, constraints, states)
            if state == 'TRUE' and not any(set(prior) <= set(indices) for prior in solutions):
                solutions.append(indices)
            elif state == 'UNKNOWN' and not any(set(prior) <= set(indices) for prior in solutions + unknown_sets):
                unknown_sets.append(indices)
                unknowns.update(missing)
    state = 'UNSUPPORTED' if unsupported else 'UNKNOWN' if unknown_sets else 'UNIQUE' if len(solutions) == 1 else 'MULTIPLE' if solutions else 'UNSAT'
    # Distinct source/configuration bindings may reconstruct the same graph.
    # Count actual graph semantics separately instead of inventing two diagrams.
    graphs = set()
    for indices in solutions:
        graph_nodes = {}
        graph_maps = {'roles': {}, 'resources': {}, 'fields': {}}
        for index in indices:
            release, instance = pairs[index]
            graph_nodes.update({step['id']: step for step in release['steps']})
            for group in graph_maps:
                graph_maps[group].update(instance[group])
        graphs.add(json.dumps(dict(nodes=graph_nodes, mappings=graph_maps), sort_keys=True, ensure_ascii=False, separators=(',', ':')))
    return dict(state=state, selection_variant_count=len(solutions), distinct_execution_graphs=len(graphs), required_goals=deepcopy(goals), unsupported_goals=unsupported,
                minimal_solutions=[[selection_ref(*pairs[i]) for i in indices] for indices in solutions],
                unknown_solutions=[[selection_ref(*pairs[i]) for i in indices] for indices in unknown_sets],
                unknowns=sorted(unknowns), examined_subsets=examined,
                execution_enabled=False, new_grants=False)


def rebuild_selection(selection, releases, instances, request, expected_binding, *, now=None):
    """Rebuild only trusted registered contracts after independent satisfiability."""
    parsed = parse_selection(json.dumps(selection, ensure_ascii=False, allow_nan=False), expected_binding)
    oracle = enumerate_solutions(releases, instances, request, now=now)
    pairs = _catalog(releases, instances, request, now)
    return _rebuild_pairs(parsed, pairs, request, expected_binding, oracle)


def _rebuild_pairs(parsed, pairs, request, expected_binding, oracle, *, actions=None):
    """Original registered graph reconstruction after source validation."""
    chosen = sorted(parsed['selections'], key=_identity)
    actions = bp.ACTIONS if actions is None else actions
    if oracle['state'] not in ('UNIQUE', 'MULTIPLE') or not any(_equal(chosen, solution) for solution in oracle['minimal_solutions']):
        raise SelectionError()
    selected = [pair for pair in pairs if selection_ref(*pair) in chosen]
    by_node = {}
    for release, instance in selected:
        ref = selection_ref(release, instance)
        for raw in release['steps']:
            step = by_node.setdefault(raw['id'], dict(**deepcopy(raw), service_refs=[], instance_mappings=[]))
            step['service_refs'].append(ref)
            step['instance_mappings'].append(dict(instance_id=instance['instance_id'], roles=deepcopy(instance['roles']), resources=deepcopy(instance['resources']), fields=deepcopy(instance['fields'])))
    steps, done = [], set()
    while len(done) != len(by_node):
        ready = sorted(key for key, value in by_node.items() if key not in done and set(value['depends_on']) <= done)
        if not ready:
            raise SelectionError()
        for key in ready:
            step = by_node[key]
            step.update(adapter_ref=step['adapter'], adapter_revision=step['revision'], actions=deepcopy(actions[key]), executable=False)
            steps.append(step)
            done.add(key)
    coverage = [dict(goal=goal, status='SUPPORTED_PREVIEW', steps=sorted({step['id'] for release, _ in selected if goal in release['supported_goals'] for step in release['steps']})) for goal in request['required_goals']]
    return dict(binding=deepcopy(expected_binding), selections=chosen, required_goals=deepcopy(request['required_goals']),
                goal_coverage=coverage, steps=steps, constraints=deepcopy(request.get('planning_constraints')),
                oracle=oracle, executed=False, execution_enabled=False, new_grants=False)
