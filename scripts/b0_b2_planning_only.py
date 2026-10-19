"""One fixed synthetic V4 planning replay; no application/provider or model IO."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re
import sys
from time import perf_counter
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parkweave import controlled_plans as cp, registered_dependencies as dependencies
from parkweave import service_selection as selection
from parkweave.service_selection_planner import compact_context
from parkweave.intern_adapter import strict_json

SERVICES = ('synthetic-material-preparation', 'synthetic-resource-coordination',
            'synthetic-local-record-recheck')
NODE_KEYS = ('id', 'adapter', 'revision', 'depends_on', 'responsibility',
             'preconditions', 'output', 'acceptance', 'service_refs',
             'instance_mappings', 'actions')
BUDGET = dict(rebuild_selection=1, dependency_inspect=1,
              rebuild_returned_nodes=5, candidate_rows_constructed=5)


def digest(value):
    return cp._hash(value)


def fixed_selection(context, choices):
    """Resolve three explicit form choices, never choose an oracle solution."""
    context, _ = compact_context(context)
    if (type(choices) is not list or len(choices) != 3 or
            [x.get('service_id') for x in choices] != list(SERVICES)):
        raise ValueError('fixed explicit three-service choices required')
    refs = []
    for choice in choices:
        if set(choice) != {'service_id', 'ref'}:
            raise ValueError('exact fixed choice required')
        matches = [x for x in context['available_services']
                   if x['service_id'] == choice['service_id']]
        if len(matches) != 1 or matches[0]['ref'] != choice['ref']:
            raise ValueError('unique exact current fixed choice required')
        refs.append(deepcopy(choice['ref']))
    return selection.parse_selection(json.dumps(dict(schema_version=1,
        binding=context['binding'], selections=refs)), context['binding'])


def project(steps, collections, *, previous=None, changed=None):
    """Fixed observation: original contracts, direct roots, upstream witnesses.

    This format is not an execution proof. Constructing a row is distinct from
    a semantic difference, internal algorithm work, and a business mutation.
    """
    nodes = deepcopy(previous) if previous is not None else {}
    constructed = 0
    for step in steps:
        key = step['id']
        if changed is not None and key not in changed:
            if key not in nodes:
                raise ValueError('unaffected original candidate row missing')
            continue
        if any(upstream not in nodes for upstream in step['depends_on']):
            raise ValueError('original topological order required')
        nodes[key] = dict(contract={k: deepcopy(step[k]) for k in NODE_KEYS},
            source_witness={name: deepcopy(collections[name])
                            for name, root in dependencies.COLLECTION_ROOTS.items()
                            if root == key and name in collections},
            upstream_witness={upstream: digest(nodes[upstream])
                              for upstream in step['depends_on']})
        constructed += 1
    return nodes, constructed


def _input(value):
    if value['kind'] != 'OWNED_SYNTHETIC_V4_PLANNING_REPLAY':
        raise ValueError('explicit synthetic replay only')
    if value['order'] != ['FULL', 'LOCAL'] or value['budget_per_arm'] != BUDGET:
        raise ValueError('identical fixed order and budgets required')
    plan = value['existing_plan']
    if plan['manual_locks'] or plan['owner_amendments']:
        raise ValueError('fixed sample must actually have no manual records')
    steps = plan['steps']
    if ([s['adapter_id'] for s in steps] != ['P1', 'P2', 'P3', 'P4', 'P5'] or
            len({s['id'] for s in steps}) != 5 or
            {s['adapter_id']: s['id'] for s in steps} != value['identity_map']['steps'] or
            plan['id'] != value['identity_map']['plan']):
        raise ValueError('one original plan and exact step identity map required')
    context = value['context']
    anchor = plan['identity_anchor']
    if set(anchor) != {'plan_id', 'original_binding', 'step_ids', 'owner_id', 'event'} or digest(anchor) != plan['identity_anchor_sha256']:
        raise ValueError('original stored adoption identity anchor required')
    binding_keys = {'preparation_id', 'case_id', 'run_id', 'preparation_revision',
                    'request_revision', 'source_sha256', 'catalog_sha256',
                    'registry_sha256', 'capability_catalog_sha256'}
    for bound in (context['binding'], anchor['original_binding']):
        if set(bound) != binding_keys:
            raise ValueError('exact original V4 binding keys required')
        for key in ('preparation_id', 'case_id', 'run_id'):
            if type(bound[key]) is not str or str(UUID(bound[key])) != bound[key]:
                raise ValueError('canonical original UUID binding required')
        for key in ('preparation_revision', 'request_revision'):
            if type(bound[key]) is not int or not 1 <= bound[key] <= 64:
                raise ValueError('exact original revision required')
        for key in binding_keys-{'preparation_id', 'case_id', 'run_id', 'preparation_revision', 'request_revision'}:
            if type(bound[key]) is not str or not re.fullmatch('[0-9a-f]{64}', bound[key]):
                raise ValueError('exact original binding digest required')
    if (anchor['plan_id'] != plan['id'] or anchor['step_ids'] != value['identity_map']['steps'] or
            any(context['binding'][k] != anchor['original_binding'][k]
                for k in binding_keys-{'source_sha256'}) or
            set(anchor['event']) != {'id', 'actor_id', 'fingerprint'} or
            anchor['event']['actor_id'] != anchor['owner_id'] or
            not re.fullmatch('[0-9a-f]{64}', anchor['event']['fingerprint'])):
        raise ValueError('current object must match original stored ADOPT anchor')
    for id in [anchor['plan_id'], anchor['event']['id'], *anchor['step_ids'].values()]:
        if type(id) is not str or str(UUID(id)) != id:
            raise ValueError('original plan/event/step UUID anchor required')
    for key in ('preparation', 'case', 'run'):
        if context['binding'][key + '_id'] != value['identity_map'][key]:
            raise ValueError('original object identity binding required')
    catalog = value['catalog']
    if catalog['unknowns'] or digest(cp._normal(catalog)) != context['binding']['capability_catalog_sha256']:
        raise ValueError('known exact original catalog required')
    if (context['required_goals'] != value['request']['required_goals'] or
            context['required_goals'] != plan['required_goals'] or
            context['planning_constraints'] != value['request']['planning_constraints']):
        raise ValueError('identical explicit goals required')
    saved = plan['dependency_manifest']
    current = dependencies.manifest(steps, value['current_collections'])
    dependencies.validate(saved)
    dependencies.validate(current)
    if any(not v['known'] for v in saved['collections'].values()) or any(
            not v['known'] for v in current['collections'].values()):
        raise ValueError('UNKNOWN source cannot become a fixed successful pair')
    if set(saved['collections']) != set(current['collections']) or any(
            saved['collections'][name] != current['collections'][name]
            for name in saved['collections'] if name != 'resources'):
        raise ValueError('undeclared nonresource source change')
    before, after = value['resource_rows_before'], value['resource_rows_after']
    if len(before) != 2 or len(after) != 2 or before == after:
        raise ValueError('two exact selected-resource changes required')
    chosen_instances = {x['ref']['instance_id'] for x in value['fixed_choices']}
    selected = {resource for instance in catalog['instances']
                if instance['instance_id'] in chosen_instances
                for resource in instance['resources'].values()}
    if (len(selected) != 2 or {r['id'] for r in before} != selected or
            {r['id'] for r in after} != selected or
            any(r['park_id'] != value['request']['park_id'] for r in before+after)):
        raise ValueError('two distinct exact selected resources in original park required')
    for old, new in zip(before, after):
        if (old['revision'], old['buffer_seconds'], old['capacity']) != (1, 300, 2) or new != {
                **old, 'revision': 2, 'buffer_seconds': 360}:
            raise ValueError('only declared resource revision/buffer changes allowed')
    query_keys = {'id', 'revision', 'source', 'capacity', 'buffer_seconds',
                  'open_from', 'open_until', 'enabled', 'capability', 'active'}
    for suffix, resources, manifest in (
            ('before', before, saved), ('after', after, current)):
        rows = value['resource_query_rows_'+suffix]
        pairs = {(row['id'], row['capability']) for row in rows}
        if (len(rows) != 4 or pairs != {(id, cap) for id in selected for cap in ('READ', 'HOLD')} or
                any(set(row) != query_keys or row['active'] is not True for row in rows) or
                manifest['collections']['resources'] != dict(known=True, count=4, sha256=digest(rows))):
            raise ValueError('original resource query rows/count/hash binding required')
        by_id = {row['id']: row for row in resources}
        if any(any(row[key] != by_id[row['id']][key]
                   for key in query_keys-{'capability', 'active'}) for row in rows):
            raise ValueError('selected resource rows must match exact original query witness')
    if saved['collections']['resources'] == current['collections']['resources']:
        raise ValueError('actual changed resource collection required')
    now = datetime.fromisoformat(value['as_of'])
    if now.tzinfo is None:
        raise ValueError('one frozen aware time required')
    slot = value['requested_slot']
    if (set(slot) != {'starts_at', 'ends_at', 'quantity'} or slot['quantity'] != 2 or
            datetime.fromisoformat(slot['starts_at']) != now+timedelta(hours=5) or
            datetime.fromisoformat(slot['ends_at']) != now+timedelta(hours=6)):
        raise ValueError('one identical fixed quantity/timeslot required')
    return now


def compare(value):
    """Both arms consume identical copies; no oracle is read by either arm."""
    original = digest(value)
    now = _input(value)
    common_start = perf_counter()
    chosen = fixed_selection(value['context'], value['fixed_choices'])
    old_nodes, old_rows = project([s['contract'] for s in value['existing_plan']['steps']],
                                 value['existing_plan']['dependency_manifest']['collections'])
    common_seconds = perf_counter() - common_start
    arms = {}
    for arm in value['order']:
        frozen = deepcopy(value)
        start = perf_counter()
        calls = dict(rebuild_selection=0, dependency_inspect=0)
        calls['rebuild_selection'] += 1
        rebuilt = selection.rebuild_selection(chosen, frozen['catalog']['releases'],
            frozen['catalog']['instances'], frozen['request'],
            frozen['context']['binding'], now=now)
        changed = None
        if arm == 'LOCAL':
            calls['dependency_inspect'] += 1
            _, changed, unknown = dependencies.inspect(frozen['existing_plan'],
                                                       frozen['current_collections'])
            if unknown:
                raise ValueError('UNKNOWN impact cannot be forced into literal answer')
        nodes, rows = project(rebuilt['steps'], frozen['current_collections'],
                             previous=old_nodes if arm == 'LOCAL' else None,
                             changed=changed)
        elapsed = perf_counter() - start
        if (len(rebuilt['steps']) > BUDGET['rebuild_returned_nodes'] or
                rows > BUDGET['candidate_rows_constructed'] or any(
                    calls[key] > BUDGET[key] for key in calls)):
            raise ValueError('fixed equal per-arm budget exceeded')
        contract_diff = [key for key in nodes if nodes[key]['contract'] != old_nodes[key]['contract']]
        witness_diff = [key for key in nodes if {k: v for k, v in nodes[key].items() if k != 'contract'} !=
                        {k: v for k, v in old_nodes[key].items() if k != 'contract'}]
        arms[arm] = dict(input_sha256=original, as_of=frozen['as_of'],
            requested_slot=frozen['requested_slot'], binding=deepcopy(chosen['binding']),
            selected_refs=deepcopy(chosen['selections']), required_goals=rebuilt['required_goals'],
            identity_map=frozen['identity_map'], candidate=nodes, candidate_sha256=digest(nodes),
            contract_diff=contract_diff, witness_diff=witness_diff,
            changed=[key for key in nodes if nodes[key] != old_nodes[key]],
            component_calls=calls, rebuild_returned_nodes=len(rebuilt['steps']),
            candidate_rows_constructed=rows, candidate_rows_reused=5-rows,
            final_candidate_nodes=len(nodes), automation_seconds=elapsed,
            business_writes=0, actual_model_calls=0, human_active_seconds=None)
        if digest(frozen) != original or digest(value) != original:
            raise ValueError('arm mutated shared input')
    return dict(scope='ONE_FIXED_SYNTHETIC_PLANNING_ONLY_PAIR', input_sha256=original,
        input_capture_source_commit=value['source_commit'], order=value['order'],
        fixed_choice_mode='FIXED_SCRIPT_NOT_HUMAN_NOT_AI',
        common=dict(fixed_selection_calls=1, old_projection_rows=old_rows,
                    automation_seconds=common_seconds), arms=arms,
        candidates_equal=arms['FULL']['candidate'] == arms['LOCAL']['candidate'],
        full_business_application='NOT_RUN', local_business_application='NOT_RUN',
        actual_model_calls=0, human_active_seconds=None, monetary_cost=None,
        conclusion='technical candidate/witness consistency only; no AI, human-time or cost superiority')


def judge(result, oracle, value):
    """Judge actual payload against the frozen input, never producer summaries."""
    base = dict(scope='FIXED_SYNTHETIC_SOURCE_WITNESS_ORACLE', formal_AT31='NOT_RUN',
                real_qualification='NOT_EVALUATED')
    if type(result.get('arms')) is not dict or set(result['arms']) != {'FULL', 'LOCAL'}:
        return dict(**base, result='INCOMPLETE', reason='EXACT_TWO_ARMS_REQUIRED', arms={})
    original, validator_rows = project([s['contract'] for s in value['existing_plan']['steps']],
                                      value['existing_plan']['dependency_manifest']['collections'])
    wanted, kept = set(oracle['should_update']), set(oracle['should_preserve'])
    rows = {}
    consistent = True
    for arm, observed in result['arms'].items():
        required = {'candidate', 'required_goals', 'changed', 'contract_diff', 'witness_diff',
                    'input_sha256', 'as_of', 'identity_map', 'binding', 'requested_slot', 'selected_refs'}
        if not required <= set(observed) or type(observed['candidate']) is not dict or set(observed['candidate']) != set(original):
            return dict(**base, result='INCOMPLETE', reason='CANDIDATE_PAYLOAD_REQUIRED', arms={})
        candidate = observed['candidate']
        if any(type(n) is not dict or set(n) != {'contract', 'source_witness', 'upstream_witness'} or
               type(n['contract']) is not dict or set(n['contract']) != set(NODE_KEYS) or
               type(n['source_witness']) is not dict or type(n['upstream_witness']) is not dict
               for n in candidate.values()):
            return dict(**base, result='INCOMPLETE', reason='COMPLETE_NODE_PAYLOAD_REQUIRED', arms={})
        contract_diff = [k for k in candidate if candidate[k]['contract'] != original[k]['contract']]
        witness_diff = [k for k in candidate if {p: v for p, v in candidate[k].items() if p != 'contract'} !=
                        {p: v for p, v in original[k].items() if p != 'contract'}]
        actual = [k for k in candidate if candidate[k] != original[k]]
        changed = set(actual)
        consistent &= (observed['changed'] == actual and observed['contract_diff'] == contract_diff and
            observed['witness_diff'] == witness_diff and observed['input_sha256'] == digest(value) and
            observed['as_of'] == value['as_of'] and observed['identity_map'] == value['identity_map'] and
            observed['binding'] == value['context']['binding'] and observed['requested_slot'] == value['requested_slot'] and
            observed['selected_refs'] == [x['ref'] for x in value['fixed_choices']])
        for key, node in candidate.items():
            consistent &= (node['source_witness'] == {
                name: value['current_collections'][name]
                for name, root in dependencies.COLLECTION_ROOTS.items()
                if root == key and name in value['current_collections']})
            consistent &= (node['upstream_witness'] == {
                upstream: digest(candidate[upstream])
                for upstream in original[key]['contract']['depends_on']})
        rows[arm] = dict(missed_update_count=len(wanted-changed), missed_update_denominator=len(wanted),
            wrong_modification_count=len(kept & changed), wrong_modification_denominator=len(kept),
            contract_diff=contract_diff, witness_diff=witness_diff)
    equal = result['arms']['FULL']['candidate'] == result['arms']['LOCAL']['candidate']
    consistent &= result.get('candidates_equal') is equal
    shape = all(row['required_goals'] == oracle['required_goals'] and
        list(row['candidate']) == oracle['adapters'] and
        [n['contract']['adapter'] for n in row['candidate'].values()] == oracle['adapter_names'] and
        [n['contract']['depends_on'] for n in row['candidate'].values()] == oracle['depends_on']
        for row in result['arms'].values())
    passed = (shape and consistent and equal and all(
        not row['missed_update_count'] and not row['wrong_modification_count'] and
        not row['contract_diff'] and set(row['witness_diff']) == wanted for row in rows.values()))
    return dict(**base, result='PASS' if passed else 'FAIL', arms=rows,
                payload_and_summaries_consistent=bool(consistent),
                candidates_equal_recomputed=equal, validator_old_projection_rows=validator_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise ValueError('pinned exact snapshot bytes required')
    value = strict_json(raw.decode('utf-8'))
    result = compare(value)
    result['execution_script_sha256'] = sha256(Path(__file__).read_bytes()).hexdigest()
    oracle_raw = (ROOT/'tests/fixtures/b0_b2_planning_only_oracle.json').read_bytes()
    result['oracle_sha256'] = sha256(oracle_raw).hexdigest()
    result['input_file_sha256'] = args.sha256
    result['judgement'] = judge(result, strict_json(oracle_raw.decode('utf-8')), value)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(scope=result['scope'], judgement=result['judgement']['result'],
                         formal_AT31='NOT_RUN', actual_model_calls=0)))
    return 0 if result['judgement']['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
