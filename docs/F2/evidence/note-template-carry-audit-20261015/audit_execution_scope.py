"""Independently count raw current windows; no business/source execution."""
from collections import Counter
from pathlib import Path
import argparse
import json
import re
import xml.etree.ElementTree as ET

from audit_archive import ROOT, HERE, read_json, relpath, public_json, identity, digest


def node(case, modules):
    parts = case.get('classname', '').split('.')
    position = next(i for i, part in enumerate(parts) if part.startswith('test_'))
    module = next(path for path in modules if Path(path).stem == parts[position])
    return module + '::' + '::'.join(parts[position + 1:] + [case.get('name')])


def window(folder, prefix, modules, source_sha, excluded=()):
    base = ROOT / '.runtime' / folder
    collection = base / (prefix + '-collection.json')
    if not collection.exists():
        collection = base / 'collection.json'
    raw_nodes = read_json(collection)
    cases = list(ET.parse(base / (prefix + '.xml')).iter('testcase'))
    actual = [node(case, modules) for case in cases]
    assert len(raw_nodes) == len(set(raw_nodes)) == len(actual) == len(set(actual))
    assert set(actual) == set(raw_nodes)
    assert {item.split('::', 1)[0] for item in actual} == set(modules)
    outcomes = {item: ('ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS') for item, case in zip(actual, cases)}
    raw_counts = {key: list(outcomes.values()).count(key) for key in ['PASS', 'FAIL', 'ERROR', 'SKIP']}
    record = base / (prefix + '.json')
    if not record.exists() and folder == 'note-template-carry-backend-formal-v2':
        record = base / 'result.json'
    data = read_json(record)
    assert data['source_sha'] == source_sha
    assert data['counts'] == raw_counts
    if excluded:
        expected_module = 'tests/test_case_goal_results.py'
        expected_failure = expected_module + '::test_resource_window_expiry_during_actual_last_source_row_lock_wait'
        assert (folder, prefix) == ('note-template-carry-final', 'root-2-v2')
        assert list(excluded) == [expected_module]
        assert raw_counts == dict(PASS=788, FAIL=1, ERROR=0, SKIP=0) and data['exit_code'] == 1
        assert [item for item, status in outcomes.items() if status != 'PASS'] == [expected_failure]
        assert sum(item.split('::', 1)[0] == expected_module for item in raw_nodes) == 44
    else:
        assert raw_counts == dict(PASS=len(actual), FAIL=0, ERROR=0, SKIP=0) and data['exit_code'] == 0
    selected_modules = [module for module in modules if module not in excluded]
    selected = [item for item in raw_nodes if item.split('::', 1)[0] in selected_modules]
    assert all(outcomes[item] == 'PASS' for item in selected)
    assert {item.split('::', 1)[0] for item in selected} == set(selected_modules)
    if excluded:
        assert len(selected_modules) == 24 and len(selected) == 745
    return selected, dict(directory=folder, prefix=prefix, raw_module_count=len(modules),
        module_count=len(selected_modules), selected_complete_modules=selected_modules,
        raw_counts=raw_counts, excluded_entire_modules=list(excluded),
        excluded_all_nodes=[item for item in raw_nodes if item.split('::', 1)[0] in excluded],
        actual_PASS=len(selected), raw_collection_JUnit_exact=True, unique_nodes=True,
        collection=identity(collection), JUnit=identity(base / (prefix + '.xml')))


def manifest_checks(config, folder, prefix):
    base = ROOT / '.runtime' / folder
    freeze = read_json(relpath(config['freeze']))
    observed = {}
    for side in ['before', 'after']:
        files = [base / (prefix + '-' + side + '.json'), base / ('source-' + side + '.json'),
                 base / (prefix + '-all-tracked-' + side + '.json'), base / ('all-tracked-' + side + '.json')]
        source = False
        full = False
        checks = []
        for path in files:
            if not path.exists():
                continue
            record = read_json(path)
            values = record.get('hashes', record)
            if values == freeze['all_tracked_sha256']:
                source = full = True
                checks.append(dict(path=str(path.relative_to(ROOT)), scope='ALL_14392_TRACKED', **identity(path)))
            elif values == freeze['source_paths']:
                source = True
                checks.append(dict(path=str(path.relative_to(ROOT)), scope='613_SOURCE', **identity(path)))
            else:
                raise AssertionError('window manifest differs from current freeze: ' + str(path.relative_to(ROOT)))
        assert source and full, 'required source/full-after manifest absent'
        observed[side] = dict(source613_equal=True, standalone_all14392_manifest=full, records=checks)
    return observed


def perform(config, attempt):
    assert read_json(attempt/'mechanical-gate.json')['status']=='PASS_MECHANICAL_ONLY_SCOPE_GATE_STILL_REQUIRED'
    planned=read_json(relpath(config['planned']))
    wanted=[m for group in planned['windows'].values() for m in group]
    assert len(wanted)==len(set(wanted))==config['complete_modules']==95
    assert planned['source_freeze']==config['source_sha']
    assert [v['module'] for v in planned['excluded_external']]==['tests/test_template_upgrade_browser.py']
    all_nodes=[];all_modules=[];records=[]
    for folder,prefix,modules_file in config['formal_windows']:
        modules=read_json(ROOT/'.runtime'/folder/modules_file)
        excluded=config.get('excluded_entire_modules',{}).get(folder+'/'+prefix,[])
        nodes,result=window(folder,prefix,modules,config['source_sha'],excluded)
        result['manifests']=manifest_checks(config,folder,prefix)
        all_nodes+=nodes;all_modules+=result['selected_complete_modules'];records.append(result)
    assert len(all_modules)==len(set(all_modules))==95 and set(all_modules)==set(wanted)
    assert len(all_nodes)==len(set(all_nodes))
    root=read_json(relpath(config['coverage']))
    assert root['status']=='PASS' and root['source_sha']==config['source_sha']
    assert root['complete_modules']==95 and root['unique_testcases']==len(all_nodes)
    assert root['counts']==dict(PASS=len(all_nodes),FAIL=0,ERROR=0,SKIP=0)
    supplemental=[];extra=[]
    for folder,prefix,count in config['supplemental_windows']:
        record=read_json(ROOT/'.runtime'/folder/(prefix+'.json'));assert record['source_sha']==config['source_sha']
        nodes,result=window(folder,prefix,record['modules'],config['source_sha']);assert len(nodes)==count
        result['manifests']=manifest_checks(config,folder,prefix);supplemental.append(result);extra+=nodes
    assert len(extra)==len(set(extra))==8 and not set(extra).intersection(all_nodes)
    review=ROOT/'.runtime/note-template-carry-review-formal-v2/probes'
    matrix=read_json(review/'freeze-f686ada-history-v1-historical-20-mutation-matrix.json')
    assert len(matrix['pure_mutation_checks'])==20 and all(v['actual_rejected'] for v in matrix['pure_mutation_checks'])
    assert matrix['no_PG_tampering'] and matrix['fixture_required_goal_count']==5
    chain=read_json(review/'freeze-f686ada-history-v1-v2-material-carry-chain.json')
    for key in ['proof_version2','original_local_ADOPT','original_P1_P5_VERIFY','first_carry','post_carry_edit','original_reconfirmation','next_hop','first_key_cold_GET','each_carry_immediate_business_snapshot_equal']:
        assert chain[key] is True
    assert chain['fixture_required_goal_count']==5
    budget=[json.loads(line) for line in (review/'freeze-f686ada-budget-v1-budget-observed.jsonl').read_text().splitlines()]
    regular=[v for v in budget if 'source' in v]
    actual={(v['source'],v['revision_before'],v['locked'],v['allowed']) for v in regular}
    assert actual=={('2',58,False,True),('2',59,False,False),('1',63,False,True),('1',62,True,True),('1',63,True,False)}
    assert all(v['business_rows_unchanged'] and v['note_and_original_history_preserved'] for v in regular)
    last=[v for v in budget if v.get('scenario')=='carry_at_existing_128_event_ledger'];assert len(last)==1
    assert last[0]['ledger_before_after_equal'] and last[0]['carry_added_opportunity_events']==0
    public_json(attempt/'independent-window-union.json',dict(status='PASS_SCOPED_EXECUTION_UNION',source_sha=config['source_sha'],
        complete_modules=95,unique_testcases=len(all_nodes),counts=dict(PASS=len(all_nodes),FAIL=0,ERROR=0,SKIP=0),windows=records,
        supplemental_windows=supplemental,supplemental_pytest_items=8,pure_history_checks=20,
        history_fixture_pytest=1,v2_chain_pytest=1,budget_pytest=6,fixture_required_goals=5,
        supplementals_transport='ASGI_TESTCLIENT_OWNED_PG_NOT_NEW_SIX_GOAL_HTML',
        external_browser_module='BLOCKED_EXTERNAL_NOT_RUN',browser_installed_or_launched=False,
        selection_scope='95 complete modules explicitly selected from eight execution windows; original root2 raw failure and entire44-item module preserved and excluded, replaced by one complete module retry; not all original raw windows PASS',
        root_raw_union_independently_recounted=True,old_scores_reused=False,whole_repository_run=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
    config=read_json(HERE/'audit-config.json');assert config['archive_ready'] is True,'NOT_RUN: await explicit archive-ready'
    attempt=HERE/args.label;assert attempt.is_dir()
    perform(config,attempt)


if __name__=='__main__':main()
