"""Revalidate AT-01..36 source bindings without importing tests or changing acceptance."""
from pathlib import Path
import ast
import hashlib
import json
import argparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/product-closure-20261105'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(selector, previous=None):
    parts = selector.split('::')
    path = (ROOT / parts[0]).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('WORKSPACE_SOURCE_REQUIRED')
    row = dict(selector=selector, exists=path.is_file(), executed=False)
    if not path.is_file():
        return row
    row['sha256'] = sha(path)
    row['previous_sha256'] = previous
    row['previous_source_matches'] = row['sha256'] == previous if previous else None
    if path.suffix == '.py':
        nodes = ast.parse(path.read_text(encoding='utf-8-sig')).body
        found = True
        for name in parts[1:]:
            name = name.split('[', 1)[0]
            match = next((n for n in nodes if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
            if match is None:
                found = False
                break
            nodes = match.body
        row['ast_selector_found'] = found
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out.exists():
        raise ValueError('NEW_WORKSPACE_EVIDENCE_REQUIRED')
    audit = DOCS / 'at-audit.json'
    specs = ROOT / 'docs/验收规格.json'
    formal = {r['id']: r for r in json.loads(specs.read_bytes())['cases']}
    old = {r['id']: r for r in json.loads(audit.read_bytes())}
    supplemental = json.loads((DOCS / 'at-resource-clock-bindings.json').read_bytes())
    supplements = {r['id']: r for r in supplemental['cases']}
    reviewed = {
        'AT-07': [
            'tests/test_service_selection_full_chain.py::test_three_capability_selection_second_park_original_local_outputs',
            'tests/test_service_selection_full_chain.py::test_selection_api_scope_revocation_and_cancel_cannot_dispatch_model',
        ],
        'AT-08': [
            'tests/test_template_full_chain.py::test_template_new_input_full_original_local_chain_and_changed_source_rejections',
        ],
    }
    rows = []
    for number in range(1, 37):
        ident = f'AT-{number:02d}'
        requirement = formal[ident]
        original = old[ident]
        entries = [binding(r['selector'], r.get('source_sha256')) for r in original.get('selectors', [])]
        supplement = supplements.get(ident, {})
        for item in supplement.get('bindings', []):
            if not any(r['selector'] == item['selector'] for r in entries):
                entries.append(binding(item['selector']))
        for selector in reviewed.get(ident, []):
            entries.append(binding(selector))
        rows.append(dict(id=ident, scenario=requirement['scenario'], requirement=requirement,
                         formal_status=requirement['status'], audit_whole_status=original['whole_status'],
                         source_bindings=entries, source_review_only=bool(reviewed.get(ident)),
                         source_missing=any(not b['exists'] or b.get('ast_selector_found') is False for b in entries),
                         source_drift=any(b.get('previous_source_matches') is False for b in entries),
                         supplemental_scope=supplement.get('scope'),
                         actual_windows_business_execution='NOT_COMPLETED',
                         demo_evidence_is_acceptance=False))
    xml = DOCS / 'selection-planner-20261106.xml'
    suites = ET.parse(xml).getroot()
    tests = suites.findall('.//testcase')
    planner = dict(file=str(xml.relative_to(ROOT)), sha256=sha(xml), tests=len(tests),
                   failures=sum(t.find('failure') is not None or t.find('error') is not None for t in tests),
                   skipped=sum(t.find('skipped') is not None for t in tests),
                   scope='OFFLINE_MODEL_RESPONSE_BOUNDARY_ONLY_NOT_LIVE_OR_DATABASE',
                   source_sha256=sha(ROOT / 'tests/test_service_selection_planner.py'))
    result = dict(scope='CURRENT_SOURCE_REVALIDATION_NOT_ACCEPTANCE_EXECUTION',
                  input_sha256={str(f.relative_to(ROOT)): sha(f) for f in [audit, specs, DOCS / 'at-resource-clock-bindings.json']},
                  formal_statuses_unchanged=True, planner_unit_result=planner, cases=rows,
                  summary=dict(cases=len(rows), with_bindings=sum(bool(r['source_bindings']) for r in rows),
                               missing_binding=sum(not r['source_bindings'] for r in rows),
                               source_missing=sum(r['source_missing'] for r in rows),
                               source_drift=sum(r['source_drift'] for r in rows)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
