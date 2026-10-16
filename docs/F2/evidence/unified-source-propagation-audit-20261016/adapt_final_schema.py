from pathlib import Path
p=Path('.runtime/unified-propagation-archive-audit/final_gate.py');s=p.read_text()
a=s.index("    assert len(classification['rows'])==4");b=s.index('\ndef coverage(',a)
s=s[:a]+"""    assert len(classification['modes'])==4
    for expected in classification['modes']:
        actual=found[expected['mode']]
        assert expected['trace']==actual['trace'] and expected['trace_sha256']==actual['trace_sha256'] and expected['actual_native_fetch_count']==actual['native_fetches']
        assert expected['methods']['POST']==actual['posts'] and expected['methods']['GET']==actual['native_fetches']-actual['posts'] and expected['actual_403_reads']==actual['backend403']
        assert expected['adopt_commits']==(1 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['verify_events']==expected['unique_verified_step_ids']==(5 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['real_browser']=='NOT_RUN'
    assert classification['actual_native_fetch_total']==sum(v['native_fetches'] for v in found.values())
    assert classification['python_control_http_total']=='NOT_RECORDED' and classification['real_browser']=='NOT_RUN'
    return dict(modes=list(found.values()),native_fetches=sum(v['native_fetches'] for v in found.values()),python_control_API_total='NOT_RECORDED',real_browser='NOT_RUN')
"""+s[b:]
a=s.index('def coverage(');b=s.index('\ndef gate(',a)
s=s[:a]+"""def coverage(mapping,all_nodes):
    oracle=load('docs/F2/UnifiedSourcePropagationOracle-20261016.json')
    assert mapping['oracle_sha256']==sha((ROOT/'docs/F2/UnifiedSourcePropagationOracle-20261016.json').read_bytes())
    assert len(mapping['rows'])==len(oracle['rows'])==36 and oracle['status']=='DESIGN_ONLY_NOT_EXECUTED'
    assert mapping['design_status_unchanged']==oracle['status'] and mapping['formal_new_passes']==88
    assert {r['id'] for r in mapping['rows']}=={r['id'] for r in oracle['rows']}
    byid={r['id']:r for r in oracle['rows']};counts=Counter()
    for row in mapping['rows']:
        assert row['literal_expected']==byid[row['id']]
        if row['execution']=='PASS_WITH_SCOPE_LIMIT':
            assert row['evidence'] and row['note']
            for evidence in row['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            for variant in row.get('variants',[]):
                assert variant['coverage_kind']=='HTTP_BEHAVIOR_VARIANT' and variant['note'] and variant['evidence']
                for evidence in variant['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            counts[row['coverage_kind']]+=1
        else:
            assert row['execution']=='NOT_RUN'
            counts['NOT_RUN']+=1
    assert dict(counts)==mapping['counts']==dict(PURE_LITERAL=24,HTTP_LITERAL=7,HTML_ACTUAL_HTTP=2,HTTP_BEHAVIOR_VARIANT=3)
    for path,h in mapping['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h
    return dict(design_rows=36,classification=dict(counts),additional_pytest_count=0,all_design_rows_are_HTTP=False)

def closure_checks(config,ready,freeze):
    path=ready.get('closure',str(Path(ready['coverage_map']).with_name('closure.json')))
    result=load(path);assert result['status']=='LIMITED_PASS' and result['source_sha']==freeze['source_sha'] and result['formal_new_passes']==88
    assert result['records_are_not_unique_cases'] is True
    assert result['python_control_http_total']=='NOT_RECORDED' and result['real_browser']==result['windows']==result['formal_AT']=='NOT_RUN'
    for path,h in result['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h
    art=ROOT/config['formal_base']/'artifacts/new/test_unified_dependency_propagation_independent'
    groups={}
    for prefix in ('oracle','closures','adoptions','mixed-source-changes','catalog-rule-refusal','html-results'):
        rows=[json.loads(line) for p in art.glob(prefix+'-*.jsonl') for line in p.read_text().splitlines() if line.strip()];groups[prefix]=rows
    assert {k:len(v) for k,v in groups.items()}==result['record_counts']
    assert len(groups['html-results'])==4
    assert groups['closures'] and all(r['six_goals_current'] and r['worklist_complete'] and r['stable_ids_history'] and r['worklist_recorded_only'] for r in groups['closures'])
    assert len(groups['catalog-rule-refusal'])==1 and groups['catalog-rule-refusal'][0]['no_business_writes'] is True
    reviewed=load('.runtime/unified-propagation-review/frozen-'+freeze['source_sha'][:12]+'/review.json')
    assert reviewed['source_sha']==freeze['source_sha'] and reviewed['status']=='PASS' and reviewed['counts']==dict(PASS=66,FAIL=0,SKIP=0,ERROR=0)
    assert reviewed['collection_junit_exact'] and reviewed['unique_nodes'] and reviewed['before_after_stable'] and reviewed['product_logic_patched'] is False
    return dict(status='LIMITED_PASS',record_counts=result['record_counts'],records_are_not_unique_cases=True,independent_pure_review_passes=66)
"""+s[b:]
s=s.replace("html=html_traces(Path(config['formal_base']),load(ready['html_classification']))", "html_class=load(ready['html_classification']);mapping=load(ready['coverage_map'])\n    assert html_class['source_sha']==mapping['source_sha']==freeze['source_sha']\n    html=html_traces(Path(config['formal_base']),html_class)")
s=s.replace("oracle=coverage(load(ready['coverage_map']),regression_result['nodes'])", "oracle=coverage(mapping,regression_result['nodes'])\n    closure=closure_checks(config,ready,freeze)")
s=s.replace("save(out,'preservation.json',preservation)", "save(out,'preservation.json',preservation)\n    save(out,'closure-classification.json',closure)")
p.write_text(s)
