"""Read-only independent claim checks over already frozen execution artifacts."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json, re, traceback, xml.etree.ElementTree as ET
from audit_archive import ROOT, HERE, read_json, public_json, identity

SHA='f686adafe3cec9b2820c10fada51ef2f57a559a6'
NEGATIVE={('test_service_release_preflight_independent','pending'),('test_service_release_preflight_independent','unknown_dto'),('test_at24_27_change_batch_independent','late_json_reject'),('test_at24_27_change_batch_independent','late_transport_reject'),('test_at24_27_change_batch_independent','lost_note_bad_unknown')}
LOST={('test_typed_source_impact_independent','lost'),('test_shared_source_cases_independent','lost'),('test_service_release_preflight_independent','lost'),('test_service_release_preflight_independent','lost_withdrawn'),('test_at24_27_change_batch_independent','capacity_lost_adopt'),('test_at24_27_change_batch_independent','lost_note'),('test_at24_27_change_batch_independent','lost_note_unknown')}

def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def normalized_test(value):return re.sub(r' \((?:setup|call|teardown)\)$','',value)
def nodeids(path, modules):
    result=[]
    for c in ET.parse(path).iter('testcase'):
        pieces=c.get('classname','').split('.');pos=next(i for i,p in enumerate(pieces) if p.startswith('test_'))
        module=next(m for m in modules if Path(m).stem==pieces[pos])
        result.append(module+'::'+'::'.join(pieces[pos+1:]+[c.get('name')]))
    return result

def html_claims(attempt):
    backend=ROOT/'.runtime/note-template-carry-backend-formal-v2'
    independent=ROOT/'.runtime/note-template-carry-independent-formal-v2'
    summary=read_json(backend/'html-summary.json');assert summary['source_sha']==SHA
    records=[];categories=Counter();groups=Counter();all_paths=set()
    for item in summary['traces']:
        path=backend/item['path'];assert path.is_relative_to(backend)
        assert identity(path)==dict(bytes=item['size'],sha256=item['sha256'])
        data=rows(path);last=data[-1];assert last['mode']==item['mode'] and last['scope']==item['scope']
        assert len(last['calls'])==item['http_call_records'] and last['checks']==item['checks']
        key=(item['group'],item['mode'])
        category='CONTROLLED_CLIENT_NEGATIVE' if key in NEGATIVE else 'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if key in LOST else 'REAL_BACKEND_RESPONSE_SCENARIO'
        assert item['response_evidence']==category
        assert bool(last.get('negative_transport_fixture'))==(key in NEGATIVE)
        methods=dict(Counter(x['method'] for x in last['calls']));statuses=dict(Counter(str(x['status']) for x in last['calls']))
        assert methods==item['http_methods'] and statuses==item['http_statuses']
        assert str(path) not in all_paths;all_paths.add(str(path));groups[item['group']]+=1;categories[category]+=1
        records.append(dict(path=str(path.relative_to(ROOT)),mode=item['mode'],group=item['group'],category=category,calls=len(last['calls']),methods=methods,statuses=statuses,sha256=item['sha256']))
    assert len(records)==41 and groups==dict(test_typed_source_impact_independent=6,test_shared_source_cases_independent=9,test_service_release_preflight_independent=14,test_at24_27_change_batch_independent=12)
    assert categories==dict(REAL_BACKEND_RESPONSE_SCENARIO=29,REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS=7,CONTROLLED_CLIENT_NEGATIVE=5)
    assert sum(x['calls'] for x in records)==957
    extra=[]
    for prefix,count,request_count,lost_modes in [('prior-manual-v2',8,431,{'lost_choice','lost_adopt'}),('note-carry-v2',2,24,{'source_changed'})]:
        value=read_json(independent/(prefix+'-html-summary.json'));assert value['source_sha']==SHA and len(value['flows'])==count
        actual_calls=0
        for item in value['flows']:
            path=ROOT/item['trace'];assert path.is_relative_to(independent)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==item['trace_sha256']
            last=rows(path)[-1];assert last['mode']==item['mode'] and last['scope']==item['scope']
            assert last['checks']==item['checks'] and len(last['calls'])==item['requests']
            assert last['real_browser']=='NOT_RUN' and not last.get('negative_transport_fixture')
            if prefix=='note-carry-v2':
                assert last['controlled_committed_response_loss']==(item['mode'] in lost_modes)
                assert last['fake_dto'] is False and last['manual_preserved'] and last['six_goals_current'] and last['stable_plan_and_history']
            category='REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if item['mode'] in lost_modes else 'REAL_BACKEND_RESPONSE_SCENARIO'
            assert str(path) not in all_paths;all_paths.add(str(path));categories[category]+=1;actual_calls+=len(last['calls'])
            extra.append(dict(path=str(path.relative_to(ROOT)),mode=item['mode'],window=prefix,category=category,calls=len(last['calls']),sha256=item['trace_sha256']))
        assert actual_calls==request_count
    assert len(all_paths)==51 and sum(x['calls'] for x in records+extra)==1412
    assert categories==dict(REAL_BACKEND_RESPONSE_SCENARIO=36,REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS=10,CONTROLLED_CLIENT_NEGATIVE=5)
    public_json(attempt/'independent-HTML-unit-audit.json',dict(status='PASS_DESCRIBED_TRACE_SCOPE',source_sha=SHA,actual_full_original_HTML_traces=51,backend41_fetch_records=957,prior_manual8_fetch_records=431,new_carry2_fetch_records=24,total_page_driver_fetch_records=1412,categories=dict(categories),records=records+extra,
        unit='Whole-trace categories; fetch counts include ordinary real HTTP within controlled traces, never injected-response counts or fixture/setup HTTP',
        not_claimed=['real browser','51 untouched-backend refusal scenarios','new carry current/late403 HTML','fixture/setup HTTP count']))

def precision_claims(attempt):
    b=ROOT/'.runtime/note-template-carry-backend-formal-v2/artifacts/formal7';stats={};total=0
    for group in ['test_typed_source_impact_independent','test_shared_source_cases_independent','test_service_release_preflight_independent','test_at24_27_change_batch_independent']:
        bins=defaultdict(lambda:dict(records=0,expected_affected=0,expected_preserved=0,missed=0,wrongly_affected=0,wrongly_preserved=0,missing_preserved=0,lock_records=0,expected_locked=0,wrong_locked=0))
        for p in sorted((b/group).glob('*oracle*.jsonl')):
            for row in rows(p):
                assert row.get('source_sha',row.get('head'))==SHA
                unknown=row.get('intentional_unknown',row.get('intentional_unknown_expansion',False))
                kind='declared_UNKNOWN' if unknown else 'additional_graph_UNKNOWN' if row.get('unknown_scope') else 'structurally_comparable_partition'
                z=bins[kind];ea=set(row['expected_affected']);aa=set(row['actual_affected']);ep=set(row['expected_preserved']);ap=set(row['actual_preserved'])
                z['records']+=1;z['expected_affected']+=len(ea);z['expected_preserved']+=len(ep)
                z['missed']+=len(ea-aa);z['wrongly_affected']+=len(aa-ea);z['wrongly_preserved']+=len(ap-ep);z['missing_preserved']+=len(ep-ap)
                if 'expected_locked' in row:
                    z['lock_records']+=1;z['expected_locked']+=len(set(row['expected_locked']));z['wrong_locked']+=len(set(row['expected_locked'])^set(row['actual_locked']))
                total+=1
        assert all(all(v[k]==0 for k in ['missed','wrongly_affected','wrongly_preserved','missing_preserved','wrong_locked']) for v in bins.values())
        stats[group]=dict(bins)
    assert total==77
    independent=ROOT/'.runtime/note-template-carry-independent-formal-v2';recount={}
    for prefix,module,n,affect in [('prior-manual-v2','test_manual_content_continuation_independent',14,35),('note-carry-v2','test_note_template_carry_independent',2,5)]:
        base=independent/'artifacts'/prefix/module;baseline={}
        for p in base.glob('baseline*.jsonl'):
            for row in rows(p):baseline[(row['run_id'],normalized_test(row['test']))]=row
        count=0;affected=0;preserved=0
        for p in base.glob('oracle*.jsonl'):
            for row in rows(p):
                assert row['source_sha']==SHA and row['intentional_unknown'] is False
                first=baseline[(row['run_id'],normalized_test(row['test']))]
                if prefix=='note-carry-v2':
                    ids=set(first['step_ids'].values());expected=ids if row['scenario']=='NC02_TEMPLATE_SOURCE' else set()
                    assert row['scenario'] in ['NC00_TITLE_ONLY','NC02_TEMPLATE_SOURCE'] and len(first['required_goals'])==6
                else:
                    ids=set(first['cases'][row['case']]['step_ids'].values());expected=ids if row['case']=='A' else set()
                    assert row['scenario'] in ['THREE_WAY_MATERIAL','HTML_ACTUAL_MATERIAL'] and len(first['cases'][row['case']]['required_goals'])==6
                assert len(ids)==5 and set(row['expected_affected'])==set(row['actual_affected'])==expected
                assert set(row['expected_preserved'])==set(row['actual_preserved'])==ids-expected
                count+=1;affected+=len(expected);preserved+=len(ids-expected)
        assert (count,affected)==(n,affect)
        recount[prefix]=dict(known_records=count,expected_affected_pairs=affected,expected_preserved_pairs=preserved,missed=0,wrongly_affected=0,wrongly_preserved=0,UNKNOWN_impact_precision='NOT_MEASURED')
    public_json(attempt/'independent-impact-precision-audit.json',dict(status='PASS_RECORDED_PARTITIONS_ONLY',source_sha=SHA,original_backend77_rows=stats,manual_and_new_carry=recount,
        limits=['structurally comparable partition is not evidence that current source is available','UNKNOWN expansion rows separate from known source precision','absence of lock fields is NOT_RECORDED, never a zero-lock-test claim','new-carry and manual UNKNOWN eligibility refusals do not measure UNKNOWN impact precision']))

def design_claims(attempt):
    config=read_json(HERE/'audit-config.json');selected=set()
    for folder,prefix,mf in config['formal_windows']:
        base=ROOT/'.runtime'/folder;p=base/(prefix+'-collection.json');p=p if p.exists() else base/'collection.json'
        excluded=config.get('excluded_entire_modules',{}).get(folder+'/'+prefix,[])
        selected.update(n for n in read_json(p) if n.split('::',1)[0] not in excluded)
    assert len(selected)==2713
    independent=ROOT/'.runtime/note-template-carry-independent-formal-v2'
    d=read_json(independent/'note-carry-v2-design-coverage.json');design=ROOT/d['design_path']
    assert hashlib.sha256(design.read_bytes()).hexdigest()==d['design_sha256'] and d['design_count']==22
    counts=Counter(x['coverage_kind'] for x in d['mappings']);assert counts==dict(NAMED_SCENARIO=9,VARIANTS_ONLY=8,NOT_RUN_IN_THIS_MODULE=5)
    for row in d['mappings']:
        if row['test_nodes']:
            assert set(row['test_nodes'])<=selected and row['status']=='PASS_ONLY_FOR_DESCRIBED_SCOPE'
        else:assert row['status']=='NOT_RUN_IN_THIS_MODULE'
    trace=read_json(ROOT/'.runtime/note-template-carry-review-formal-v2/literal-38-actual-trace.json')
    assert hashlib.sha256((ROOT/trace['oracle']).read_bytes()).hexdigest()==trace['oracle_sha256'] and trace['design_count']==38
    review_counts=Counter(x['coverage_kind'] for x in trace['scenarios']);assert review_counts==dict(NAMED_SCENARIO=11,VARIANTS_ONLY=19,NOT_RUN=6,STATIC_ONLY=2)
    for row in trace['scenarios']:
        for e in row['evidence']:
            cases=list(ET.parse(ROOT/e['JUnit']).iter('testcase'));matches=[c for c in cases if c.get('name')==e['test_name']]
            assert matches and all(all(c.find(k) is None for k in ['failure','error','skipped']) for c in matches)
    public_json(attempt/'independent-design-unit-audit.json',dict(status='PASS_SCOPED_TRACE_NOT_ALL_DESIGN_ACCEPTANCE',source_sha=SHA,independent_design22=dict(counts),review_design38=dict(review_counts),design_counts_added_to_pytest=False,designs_claimed_all_executed=False,design22_hash=d['design_sha256'],design38_hash=trace['oracle_sha256'],review_NOT_RUN=[x['id'] for x in trace['scenarios'] if x['coverage_kind']=='NOT_RUN'],review_STATIC_ONLY=[x['id'] for x in trace['scenarios'] if x['coverage_kind']=='STATIC_ONLY']))

def report_and_failures(attempt):
    config=read_json(HERE/'audit-config.json');report=ROOT/config['report'];data=report.read_bytes();text=data.decode()
    assert hashlib.sha256(data).hexdigest()=='4d5fccaf23805915653fed581b9cd3cd2d561e71c47be4bf2833939498902745'
    old=(HERE/'report-before-count-wording-correction.md').read_bytes()
    assert old.decode().count('原完整44模块唯一低负载复跑全过')==1
    assert old.decode().replace('原完整44模块唯一低负载复跑全过','原失败模块完整44项唯一低负载复跑全过')==text
    for token in ['95 个完整相关模块','2713','八个实际执行窗口','788PASS/1FAIL','422PASS/1FAIL','20个纯历史变异','五目标兼容夹具','真实浏览器未执行','UNKNOWN影响精度未测','未统签38','Windows','B0–B2','生产','本分支CI']:
        assert token in text,token
    assert '原完整44模块唯一低负载复跑全过' not in text
    source_tests={'fact':('tests/test_case_fact_bundle.py',172,175,1),'goal':('tests/test_case_goal_results.py',148,149,2)}
    windows={'fact':ROOT/'.runtime/note-template-carry-review-formal-v2/freeze-f686ada-extra-v1.xml','goal':ROOT/'.runtime/note-template-carry-final/root-2-v2.xml'}
    failures=[]
    for key,(module,line,target,seconds) in source_tests.items():
        cases=list(ET.parse(windows[key]).iter('testcase'));failed=[c for c in cases if c.find('failure') is not None];assert len(failed)==1
        failure=failed[0].find('failure').text or '';assert module+':'+str(line) in failure
        source=(ROOT/module).read_bytes()
        import subprocess
        baseline=subprocess.check_output(['git','show','ed5d32b6bbcf261d802fe579a2daab16330a5879:'+module],cwd=ROOT)
        assert source==baseline
        failures.append(dict(raw_XML=str(windows[key].relative_to(ROOT)),node_name=failed[0].get('name'),actual_failed_precondition_line=line,intended_target_section_begins_line=target,target_section_reached=False,actual_fixture_expiry_seconds=seconds,unchanged_test_baseline_bytes=True,raw_failure_preserved=True,interpretation='short actual source validity expired before target seam; same-source original assertion bounded complete retry separately selected, no clock/assertion/product change'))
    public_json(attempt/'public-report-and-failure-review.json',dict(status='PASS_CURRENT_REPORT_SCOPE',report=dict(path=config['report'],**identity(report)),report_single_wording_correction=dict(before=identity(HERE/'report-before-count-wording-correction.md'),after=identity(report),only_exact_one_phrase_replaced=True),raw_failed_preconditions=failures,NOT_RUN=['Windows','real browser including original blocked Playwright module','formal business AT','real model/B0-B2','formal governance and real performance','production','branch CI without existing trigger'],future_scope_preserved_delivered=['two shared-source reverse kinds','finite synthetic Release/ParkInstance','second park cold input','finite template strengthening'],claims_not_made=['all original raw windows PASS','whole repository tested','all38 and22 designs executed','five-goal supplement is six-goal acceptance','new carry late/current403 HTML dynamically tested','semantic fact/permission/fulfillment from MANUAL text']))

def main():
    config=read_json(HERE/'audit-config.json');assert config['archive_ready']
    attempt=HERE/'attempt-v1';assert read_json(attempt/'mechanical-gate.json')['status']=='PASS_MECHANICAL_ONLY_SCOPE_GATE_STILL_REQUIRED'
    assert read_json(attempt/'independent-window-union.json')['unique_testcases']==2713
    try:
        html_claims(attempt);precision_claims(attempt);design_claims(attempt);report_and_failures(attempt)
        public_json(attempt/'claim-scope-gate.json',dict(status='PASS_MECHANICAL_EXECUTION_AND_CLAIM_SCOPE',source_sha=SHA,whole_repository=False,formal_AT=False,real_browser=False,no_business_execution_in_audit=True))
    except BaseException as error:
        public_json(attempt/'claim-scope-failure.json',dict(status='FAIL_NO_FINAL_GATE',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),source_or_primary_modified=False));raise

if __name__=='__main__':main()
