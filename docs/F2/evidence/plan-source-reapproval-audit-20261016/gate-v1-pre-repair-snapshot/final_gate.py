"""Read-only independent archive gate. Run only after explicit ARCHIVE_READY."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,ast,hashlib,json,re,subprocess,sys,traceback,uuid,xml.etree.ElementTree as ET
from independent_transform import Transform,selftest
ROOT=Path('/workspace/ParkWeave')
OWN=Path(__file__).resolve().parent
from inventory_rules import inventory,RAW_DIRS
import profile_gap,t07_retry
EXT={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md','.patch','.html'}
SKIP_NAMES={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','delivery-report-template.md','critical-path-draft.md','archive-readme-draft.md'}
SKIP_PARTS={'__pycache__','private-tree','worktree','source-v1','private-worktree','source-wip-v1','source-wip-v2','xdg-cache','tmp-smoke1','pytest-cache','.pytest_cache'}
HISTORY={'docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads((ROOT/path).read_text())
def relative(path):return str(path.relative_to(ROOT))
def command(*argv):return subprocess.check_output(argv,cwd=ROOT,timeout=45)
def save(out,name,value):(out/name).write_text(json.dumps(value,ensure_ascii=True,indent=2)+'\n')
def structure(raw,suffix):
    if suffix=='.json':json.loads(raw)
    elif suffix=='.jsonl':
        for line in raw.splitlines():
            if line.strip():json.loads(line)
    elif suffix=='.xml':ET.fromstring(raw)

def secrets():
    paths=[ROOT/'.runtime/template-migration-tests-20261014/redaction-values.private.json',ROOT/'.runtime/template-structure-tests-20261015/redaction-values.private.json']
    for name in RAW_DIRS:paths.extend((ROOT/'.runtime'/name).rglob('*redaction*.private.json'))
    values=[]
    for path in paths:
        if not path.is_file():continue
        value=json.loads(path.read_text())
        if isinstance(value,dict):
            assert set(value)<={'synthetic_private_values','provenance'} and 'synthetic_private_values' in value
            value=value['synthetic_private_values']
        assert isinstance(value,list) and all(isinstance(v,str) for v in value)
        values.extend(v for v in value if len(v)>=16)
    return values
def preserve(manifest,expected):
    assert len(manifest)==expected,(len(manifest),expected)
    drift=[p for p,h in manifest.items() if not (ROOT/p).is_file() or sha((ROOT/p).read_bytes())!=h]
    assert not drift,('prior raw changed',drift)
    return dict(count=len(manifest),drift=[])
def frozen_snapshot(freeze):
    tracked={p:sha((ROOT/p).read_bytes()) for p in freeze['all_tracked_sha256']}
    source={p:tracked[p] for p in freeze['source_paths']}
    runners={p:sha((ROOT/p).read_bytes()) for p in freeze['runner_paths']}
    assert source==freeze['source_paths'] and runners==freeze['runner_paths']
    assert len(source)==len(freeze['source_paths']) and len(tracked)==len(freeze['all_tracked_sha256']) and len(runners)==len(freeze['runner_paths'])
    changed=[p for p,h in freeze['all_tracked_sha256'].items() if tracked[p]!=h]
    assert set(changed)<=HISTORY,('unexpected original tracked changes',changed)
    prefix=[]
    for p in changed:
        original=command('git','show',freeze['source_sha']+':'+p)
        current=(ROOT/p).read_bytes()
        assert sha(original)==freeze['all_tracked_sha256'][p] and current.endswith(original) and len(current)>len(original)
        prefix.append(dict(path=p,original_bytes=len(original),prefix_bytes=len(current)-len(original),exact_original_suffix=True))
    head=command('git','rev-parse','HEAD').decode().strip()
    assert head==freeze['source_sha'],'audit precedes docs-only delivery commit'
    return dict(head=head,source=source,tracked=tracked,runners=runners,history_prefix=prefix)
def junit_id(case):
    parts=case.get('classname','').split('.')
    at=next((i for i,v in enumerate(parts) if v.startswith('test_')),None)
    assert at is not None,case.attrib
    return 'tests/'+parts[at]+'.py::'+'::'.join(parts[at+1:]+[case.get('name')])
def window(base,name,freeze):
    record=load(str(base/(name+'.json')))
    assert record['source_sha']==freeze['source_sha']
    assert record['source_drift']==record['all_tracked_drift']==record['runner_drift']==[]
    assert record['tracked_source_paths']==len(freeze['source_paths']) and record['all_tracked_paths']==len(freeze['all_tracked_sha256'])
    assert load(str(base/(name+'-before.json')))==load(str(base/(name+'-after.json')))==freeze['source_paths']
    assert load(str(base/(name+'-all-tracked-before.json')))==load(str(base/(name+'-all-tracked-after.json')))==freeze['all_tracked_sha256']
    collection=load(str(base/(name+'-collection.json')))
    assert collection==record['collected_nodes'] and len(collection)==len(set(collection))
    cases=list(ET.parse(ROOT/base/(name+'.xml')).getroot().iter('testcase'))
    nodes={}
    for case in cases:
        key=junit_id(case);assert key not in nodes
        status='ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        nodes[key]=status
    assert set(nodes)==set(collection) and len(nodes)==len(collection)
    assert record['collection_junit_exact_match'] is True and record['unique_junit_nodes'] is True
    assert Counter(nodes.values())==Counter({k:v for k,v in record['counts'].items() if v})
    provenance=load(str(base/(name+'-collection-plugin-provenance.json')))
    helper=ROOT/base/'shared_capture.py'
    assert provenance['actual_path']==provenance['expected_path']==str(helper)
    assert provenance['sha256']==sha(helper.read_bytes()) and provenance['product_logic_patched'] is False
    assert record['capture_plugin_provenance']==provenance
    return record,nodes
def regression(selection,ready,config,freeze):
    planned=[m for modules in selection['main_windows'].values() for m in modules]
    assert len(planned)==len(set(planned))==freeze['expected_main_modules']
    gap=profile_gap.check(config,ready,freeze,window) if config.get('profile_gap') else None
    expected_modules=set(planned)
    if gap:assert 'main_window_selection' in ready,'explicit whole-module selection required for profile gap'
    chosen=ready.get('main_window_selection',[dict(window=n,modules=m) for n,m in selection['main_windows'].items()])
    retry_audit=t07_retry.check(config,ready,freeze,window,chosen) if config.get('t07_retry') else None
    all_nodes={};modules=[];windows=[]
    for item in chosen:
        record,nodes=window(Path(config['formal_base']),item['window'],freeze)
        selected=item['modules'];assert len(selected)==len(set(selected)) and set(selected)<=set(record['modules'])
        if set(selected)!=set(record['modules']):assert item.get('reason'),'whole-module exclusion needs explicit reason'
        else:assert record['exit_code']==0
        selected_nodes={n:s for n,s in nodes.items() if n.split('::',1)[0] in selected}
        assert selected_nodes and {n.split('::',1)[0] for n in selected_nodes}==set(selected)
        assert set(selected_nodes.values())=={'PASS'}
        assert not set(all_nodes).intersection(selected_nodes),'duplicate selected test identity'
        all_nodes.update(selected_nodes);modules.extend(selected)
        windows.append(dict(window=item['window'],modules=selected,passes=len(selected_nodes),reason=item.get('reason')))
    assert len(modules)==len(set(modules))==len(expected_modules) and set(modules)==expected_modules
    if 'expected_main_tests' in freeze:assert len(all_nodes)==freeze['expected_main_tests']
    new_modules={m for m in planned if Path(m).name.startswith(('test_plan_source_reapproval','test_plan_reapproval_client'))};assert len(new_modules)==4
    new={n:s for n,s in all_nodes.items() if n.split('::',1)[0] in new_modules}
    assert len(new)==freeze['expected_new_tests']
    if 'expected_new_tests' in ready:assert ready['expected_new_tests']==len(new)
    return dict(status=profile_gap.STATUS if gap else 'PASS',profile_gap=gap,evidence_window_retry=retry_audit,initial_modules=gap['initial_modules'] if gap else len(planned),initial_items=gap['initial_items'] if gap else freeze.get('expected_main_tests'),modules=len(modules),passed=len(all_nodes),new_unique_passes=len(new),windows=windows,nodes=all_nodes)
def ci_metadata(selection,config,freeze,main_nodes):
    name=config.get('ci_window','ci-metadata-solo');record,nodes=window(Path(config['formal_base']),name,freeze)
    assert record['exit_code']==0 and set(record['modules'])==set(selection['separate_ci_window'])
    assert len(record['modules'])==len(set(record['modules']))==12
    assert not set(nodes).intersection(main_nodes)
    assert Counter(nodes.values())==Counter(PASS=433,SKIP=14)
    xml=ROOT/config['formal_base']/(name+'.xml')
    skips=[dict(identity=junit_id(case),reason=case.find('skipped').get('message','')) for case in ET.parse(xml).getroot().iter('testcase') if case.find('skipped') is not None]
    assert all(row['reason'] for row in skips)
    return dict(window=name,modules=len(record['modules']),counts=dict(Counter(nodes.values())),skip_reasons=skips,main_denominator_overlap=0)

def html_traces(base,classification):
    scope='FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG'
    found={}
    for path in (ROOT/base).rglob('*.stdout.jsonl'):
        values=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        hits=[v for v in values if v.get('scope')==scope]
        if not hits:continue
        assert len(hits)==1
        result=hits[0];mode=result['mode'];assert mode not in found
        assert result['real_browser']=='NOT_RUN' and result['fake_dto'] is False and result['checks']>0
        calls=result['calls'];posts=[c for c in calls if c['method']=='POST']
        assert all('headers' not in c and 'token' not in c for c in calls)
        row=dict(mode=mode,trace=relative(path),trace_sha256=sha(path.read_bytes()),native_fetches=len(calls),posts=len(posts),backend403=sum(c['status']==403 for c in calls))
        if mode in ('positive','lost_ack'):
            adopted=[c for c in posts if c['path'].endswith('/service-case-plan') and c['status']==201]
            proposals=[c for c in posts if c['path'].endswith('/plan-approval/proposals')]
            approvals=[c for c in posts if c['path'].endswith('/plan-approval/commands') and c.get('body',{}).get('action')=='APPROVE']
            commits=[c for c in posts if c['path'].endswith('/resource-delivery')]
            verify=[c for c in posts if c['path'].endswith('/service-case-plan/commands') and c.get('body',{}).get('action')=='VERIFY']
            assert len(adopted)==1 and adopted[0]['body'].get('local_revision') is True and adopted[0]['body'].get('opportunity_proof')
            assert len(proposals)==1 and proposals[0]['status']==201 and proposals[0]['body']['delivery']['expected_link_revision']>=1
            assert len(approvals)==1 and approvals[0]['status']==200
            assert len(commits)==1 and commits[0]['status']==201 and commits[0]['body']['expected_link_revision']==proposals[0]['body']['delivery']['expected_link_revision']
            assert len(verify)==5 and len({c['body']['step_id'] for c in verify})==5 and all(c['status']==200 for c in verify)
            assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
            assert any(c.get('worklist_items') for c in calls)
            if mode=='lost_ack':
                recovery=[c for c in calls if c['method']=='GET' and c['path'].endswith('/resource-delivery/recovery/'+commits[0]['request_key']) and c['status']==200]
                assert recovery,'actual original commit key must be recovered from original keyed URL'
                row['exact_get_key_raw_binding']='CAPTURED_ORIGINAL_KEY_IN_GET_PATH'
        else:assert not posts and any(c['status']==403 and c['path'].endswith('/plan-approval') for c in calls)
        found[mode]=row
    assert set(found)=={'positive','lost_ack','current_403','late_403'}
    assert len(classification['modes'])==4
    for expected in classification['modes']:
        actual=found[expected['mode']]
        assert expected['trace']==actual['trace'] and expected['trace_sha256']==actual['trace_sha256'] and expected['actual_nativefetch_calls']==actual['native_fetches']
        assert expected['method_counts']['POST']==actual['posts'] and expected['method_counts']['GET']==actual['native_fetches']-actual['posts'] and expected['actual_403_count']==actual['backend403']
        assert expected['resource_commit_count']==(1 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['verify_count']==(5 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['real_browser']=='NOT_RUN'
    assert classification['actual_nativefetch_total']==sum(v['native_fetches'] for v in found.values())
    assert classification['python_control_http_total']=='NOT_RECORDED'
    return dict(modes=list(found.values()),native_fetches=sum(v['native_fetches'] for v in found.values()),python_control_API_total='NOT_RECORDED',real_browser='NOT_RUN')

def coverage(mapping,all_nodes):
    oracle=load('docs/F2/PlanReapprovalOracle-20261016.json')
    assert mapping['oracle_sha256']==sha((ROOT/'docs/F2/PlanReapprovalOracle-20261016.json').read_bytes())
    assert len(mapping['rows'])==len(oracle['rows']) and oracle['status']=='DESIGN_ONLY_NOT_EXECUTED'
    assert mapping['design_status_unchanged']==oracle['status']
    assert {r['id'] for r in mapping['rows']}=={r['id'] for r in oracle['rows']}
    originals={r['id']:r for r in oracle['rows']};counts=Counter()
    for row in mapping['rows']:
        assert row['literal_expected']==originals[row['id']]
        if row['execution'] in ('PASS_WITH_SCOPE_LIMIT','PASS'):
            assert row['evidence'] and row['note']
            for evidence in row['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            for variant in row.get('variants',[]):
                assert variant['note'] and variant['evidence']
                for evidence in variant['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            if row.get('browser_variant'):
                variant=row['browser_variant'];assert variant['coverage_kind']=='CHROMIUM_ACTUAL_HTTP' and variant['evidence'] and variant['note']
                for evidence in variant['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            counts[row['coverage_kind']]+=1
        else:assert row['execution']=='NOT_RUN';counts['NOT_RUN']+=1
    assert dict(counts)==mapping['counts']
    for path,h in mapping['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h
    return dict(design_rows=len(oracle['rows']),classification=dict(counts),additional_pytest_count=0,all_design_rows_are_browser=False)

def validate_classification_manifest(value,source):
    assert value['source_sha']==source and value['raw_sha256']
    for path,h in value['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h

def closure_checks(config,ready,freeze):
    value=load(ready.get('closure',str(Path(ready['coverage_map']).with_name('closure.json'))))
    validate_classification_manifest(value,freeze['source_sha'])
    assert value['status']=='LIMITED_PASS' and value['record_counts_are_not_unique_cases'] is True
    art=ROOT/config['formal_base']/'artifacts/new-independent/test_plan_source_reapproval_independent'
    groups={prefix:[json.loads(line) for p in art.glob(prefix+'-*.jsonl') for line in p.read_text().splitlines() if line.strip()] for prefix in ('closures','closure','refusals','source-adopt','rollback','html-results')}
    assert {name:len(rows) for name,rows in groups.items()}==value['record_counts']
    assert len(groups['html-results'])==4 and len(groups['closure'])==2
    assert groups['closures'] and all(r['six_goals_current'] and r['worklist_complete'] and r['stable_ids_history'] and r['worklist_recorded_only'] for r in groups['closures'])
    assert all(r['old_occupancy_preserved'] and r['old_receipt_cold_get'] and r['six_goals'] for r in groups['closure'])
    assert all(r['no_business_writes'] for r in groups['refusals']+groups['rollback'])
    review_base=Path(config['review_root'])/('frozen-'+freeze['source_sha'][:12]);review=load(str(review_base/'review.json'));probes=load(str(review_base/'protocol-probes.json'))
    assert review['status']=='PASS' and review['source_sha']==freeze['source_sha'] and review['before_after_stable'] and review['pytest_collection_junit_exact'] and review['product_logic_patched'] is False
    assert review['pytest_counts']['FAIL']==review['pytest_counts']['ERROR']==review['pytest_counts']['SKIP']==0
    assert review['pure_protocol_probes']==len(probes['results']) and all(row['status']=='PASS' for row in probes['results'])
    value=dict(value,independent_client_pytest_passes=review['pytest_counts']['PASS'],independent_pure_protocol_probes=review['pure_protocol_probes'])
    return value

def browser_checks(ready,freeze,main_nodes):
    value=load(ready['browser_classification']);assert value['source_sha']==freeze['source_sha']
    assert value['status']=='LIMITED_ACTUAL_CHROMIUM_PASS' and value['included_in_new_union'] is True and value['formal_passes']==4
    assert value['raw_window_sha256']==sha((ROOT/ready['formal_base']/'new-chromium.json').read_bytes())
    assert len(value['modes'])==4 and {row['mode'] for row in value['modes']}=={'positive','lost_commit','lost_propose','lost_approve'}
    found=[]
    for row in value['modes']:
        path=ROOT/row['raw'];assert sha(path.read_bytes())==row['sha256'];actual=json.loads(path.read_bytes())
        assert actual['mode']==row['mode'] and actual['actual_browser']==row['actual_browser']=='INSTALLED_CHROMIUM'
        assert actual['executable']=='/usr/bin/chromium' and actual['browser_version']==row['browser_version'] and not actual['page_errors']
        assert actual['screenshots']=='NOT_TAKEN' and actual['negative_modes']=='NODE_ONLY' and actual['windows']==actual['formal_at']=='NOT_RUN'
        calls=actual['calls'];assert len(calls)==row['request_count'] and all('headers' not in c and 'token' not in c for c in calls)
        commits=[c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201]
        proposals=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/proposals')]
        approvals=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/commands')]
        assert len(commits)==row['resource_commits']==1 and len(proposals)==row['proposal_posts']==1 and len(approvals)==row['approval_posts']==1
        assert proposals[0]['status']==201 and approvals[0]['status']==200
        lost=[c for c in calls if c.get('committed_response_controlled_lost') or c.get('approval_response_controlled_lost')]
        assert lost==row['controlled_lost_replies']
        if row['mode']=='positive':assert not lost
        else:
            assert len(lost)==1 and lost[0].get('request_key')
            if row['mode']=='lost_commit':assert lost[0].get('committed_response_controlled_lost') is True
            else:assert lost[0].get('approval_response_controlled_lost')==('PROPOSE' if row['mode']=='lost_propose' else 'APPROVE')
            endpoint='/resource-delivery/recovery/' if row['mode']=='lost_commit' else '/plan-approval/recovery/'
            assert any(c['method']=='GET' and c['status']==200 and c['path'].endswith(endpoint+lost[0]['request_key']) for c in calls)
        identity='tests/test_plan_source_reapproval_chromium.py::test_actual_installed_chromium_explicit_source_reapproval_to_six_goals['+row['mode']+']'
        assert main_nodes.get(identity)=='PASS'
        found.append(row['raw'])
    actual_files={str(p.relative_to(ROOT)) for p in (ROOT/ready['formal_base']/'artifacts/new-chromium').rglob('*-calls.json')}
    assert set(found)==actual_files and len(found)==len(set(found))
    return value

def prior_pairs(config,baseline):
    path=config['prior_archive_index'];raw=(ROOT/path).read_bytes();assert sha(raw)==baseline['all_tracked_sha256'][path]
    index=json.loads(raw);assert len(index['entries'])==config['expected_prior_pairs']
    for e in index['entries']:
        before=(ROOT/e['raw_path']).read_bytes();after=(ROOT/e['export_path']).read_bytes()
        assert len(before)==e['raw_bytes'] and sha(before)==e['raw_sha256']
        assert len(after)==e['export_bytes'] and sha(after)==e['export_sha256']
        structure(before,Path(e['raw_path']).suffix);structure(after,Path(e['export_path']).suffix)
    return dict(entries=len(index['entries']),all_raw_export_pairs_preserved=True,index_sha256=sha(raw))

def gate(config,ready,out,ready_path,*,verification_mode='FULL_REMOTE_REQUIRED'):
    assert verification_mode in ('FULL_REMOTE_REQUIRED','LOCAL_INTEGRITY_ONLY')
    selftest()
    freeze=load(config['freeze']);assert freeze['source_sha']==ready['source_sha']
    assert ready['formal_base']==config['formal_base']
    assert re.fullmatch('[a-f0-9]{40}',freeze['source_sha'])
    assert ready['primary_producers_stopped'] is True
    ready_raw=(ROOT/ready_path).read_bytes();assert json.loads(ready_raw)==ready
    primary_seal_path=Path(config['primary_seal']);primary_seal_raw=(ROOT/primary_seal_path).read_bytes();primary_seal=json.loads(primary_seal_raw)
    assert primary_seal['status']=='SEALED_NO_FURTHER_PRIMARY_WRITES' and primary_seal['source_sha']==freeze['source_sha']
    assert re.fullmatch('[a-f0-9]{64}',ready['primary_seal_sha256']) and sha(primary_seal_raw)==ready['primary_seal_sha256']
    before=frozen_snapshot(freeze);save(out,'before.json',before)
    archive=ROOT/config['archive'];index_raw=(archive/'index.json').read_bytes();index=json.loads(index_raw);report_raw=(ROOT/config['report']).read_bytes()
    assert index['source_sha']==freeze['source_sha']
    assert re.fullmatch('[a-f0-9]{64}',ready['report_sha256']) and ready['report_sha256']==sha(report_raw)
    assert re.fullmatch('[a-f0-9]{64}',ready['archive_index_sha256']) and ready['archive_index_sha256']==sha(index_raw)
    execution=load(relative(out/'execution-input.json'));assert execution['ready_path']==ready_path and execution['ready_sha256']==sha(ready_raw)
    script_inputs={name:execution[key] for key,name in [('script_sha256','final_gate.py'),('transform_sha256','independent_transform.py'),('inventory_sha256','inventory_rules.py'),('profile_gap_sha256','profile_gap.py'),('t07_retry_sha256','t07_retry.py')]}
    if 'local_runner_sha256' in execution:script_inputs['run_local_integrity.py']=execution['local_runner_sha256']
    assert all(sha((OWN/name).read_bytes())==h for name,h in script_inputs.items()),'audit helper changed before local checks'
    save(out,'audit-script-bindings.json',dict(expected=script_inputs,before_exact=True))
    save(out,'ready-binding.json',dict(status='BOUND_TO_ACTUAL_READY_AND_SEALED_PRIMARY',source_sha=freeze['source_sha'],ready_path=ready_path,ready_sha256=sha(ready_raw),primary_seal_path=str(primary_seal_path),primary_seal_sha256=sha(primary_seal_raw),primary_seal_status=primary_seal['status'],primary_producers_stopped=True,report_sha256=sha(report_raw),archive_index_sha256=sha(index_raw)))
    entries=index['entries'];assert entries and len({e['raw_path'] for e in entries})==len(entries) and len({e['export_path'] for e in entries})==len(entries)
    assert sorted(e['raw_path'] for e in entries)==inventory(),'raw inventory must be exact, not a subset'
    transform=Transform(secrets());counts=Counter();total_raw=0;total_export=0;structured=Counter();raw_hashes={}
    export_paths=[]
    for entry in entries:
        raw_path=ROOT/entry['raw_path'];export_path=ROOT/entry['export_path']
        assert raw_path.is_relative_to(ROOT/'.runtime') and export_path.is_relative_to(archive)
        assert export_path.relative_to(archive)==raw_path.relative_to(ROOT/'.runtime')
        raw=raw_path.read_bytes();public=export_path.read_bytes();raw_hashes[entry['raw_path']]=sha(raw)
        assert len(raw)==entry['raw_bytes'] and sha(raw)==entry['raw_sha256']
        assert len(public)==entry['export_bytes'] and sha(public)==entry['export_sha256']
        expected,redactions=transform.export(raw,raw_path.suffix)
        assert expected==public and redactions==entry['redactions'],entry['export_path']
        structure(raw,raw_path.suffix);structure(public,export_path.suffix)
        if export_path.suffix in ('.json','.jsonl','.xml'):structured[export_path.suffix]+=1
        counts.update(redactions);total_raw+=len(raw);total_export+=len(public);export_paths.append(export_path)
    actual_files={p for p in archive.rglob('*') if p.is_file()}
    extras=actual_files-set(export_paths)-{archive/'index.json',archive/'.gitattributes',archive/'audit.json',archive/'README.md'}
    assert not extras,('unindexed extra archive files',sorted(map(str,extras)))
    assert (archive/'.gitattributes').read_bytes()==b'* -text -whitespace\n'
    baseline=load(config['baseline'])
    preservation=dict(prior_raw=preserve(baseline['prior_raw_sha256'],config['expected_legacy_raw']),prior_pairs=prior_pairs(config,baseline))
    selection=load(config['selection'])
    regression_result=regression(selection,ready,config,freeze)
    ci=ci_metadata(selection,config,freeze,regression_result['nodes'])
    html_class=load(ready['html_classification']);mapping=load(ready['coverage_map'])
    assert html_class['source_sha']==mapping['source_sha']==freeze['source_sha']
    assert html_class['raw_sha256']==mapping['raw_sha256']
    html=html_traces(Path(config['formal_base']),html_class)
    assert mapping['formal_new_passes']==regression_result['new_unique_passes']
    assert set(mapping['formal_windows'])=={'new-core','new-independent','new-chromium'}
    for name,row in mapping['formal_windows'].items():
        actual=load(str(Path(config['formal_base'])/(name+'.json')))
        assert row['passes']==actual['counts']['PASS'] and set(row['modules'])==set(actual['modules'])
    oracle=coverage(mapping,regression_result['nodes'])
    browser=browser_checks(ready,freeze,regression_result['nodes'])
    closure=closure_checks(config,ready,freeze)
    report=(ROOT/config['report']).read_text()
    for text in [freeze['source_sha'],str(regression_result['modules']),str(regression_result['passed']),str(regression_result['new_unique_passes'])]:assert text in report,('missing supported report identity/count',text)
    assert 'Windows' in report and ('浏览器' in report or 'browser' in report)
    assert len(baseline['refs'])==config['expected_baseline_refs']==81
    remote_verified=verification_mode=='FULL_REMOTE_REQUIRED'
    if remote_verified:
        remote=command('git','ls-remote','origin').decode()
        refs={line.split('\t',1)[1]:line.split('\t',1)[0] for line in remote.splitlines()}
        assert all(refs.get(name)==value for name,value in baseline['refs'].items()),'baseline remote reference changed'
        save(out,'remote-current.json',dict(status='VERIFIED',default_network=True,baseline_ref_count=81,baseline_refs_unchanged=True,actual_refs=refs))
    else:
        blocked_path=config['remote_auth_failure_log'];blocked_raw=(ROOT/blocked_path).read_bytes()
        assert b'could not read Username for' in blocked_raw and b'https://github.com' in blocked_raw
        execution=load(relative(out/'execution-input.json'))
        assert execution['verification_mode']==verification_mode and execution['remote_auth_failure_log']==blocked_path and execution['remote_auth_failure_sha256']==sha(blocked_raw)
        save(out,'remote-current.json',dict(status='NOT_VERIFIED',reason='EXISTING_GITHUB_CONNECTION_AUTHENTICATION_BLOCKED',baseline_ref_count=81,baseline_refs_unchanged=None,network_calls_attempted_by_this_runner=0,original_failure_path=blocked_path,original_failure_sha256=sha(blocked_raw)))
    assert all(sha((ROOT/p).read_bytes())==h for p,h in raw_hashes.items()),'raw file changed during audit'
    assert inventory()==sorted(raw_hashes),'raw inventory changed during audit'
    assert (ROOT/ready_path).read_bytes()==ready_raw and (ROOT/primary_seal_path).read_bytes()==primary_seal_raw,'ready or primary seal changed during audit'
    assert (archive/'index.json').read_bytes()==index_raw and (ROOT/config['report']).read_bytes()==report_raw,'report/index changed during audit'
    assert all(sha((ROOT/e['export_path']).read_bytes())==e['export_sha256'] for e in entries),'public archive file changed during audit'
    assert all(sha((OWN/name).read_bytes())==h for name,h in script_inputs.items()),'audit helper changed during checks'
    after=frozen_snapshot(freeze);save(out,'after.json',after);assert before==after
    save(out,'archive-transformation.json',dict(entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,redactions=dict(counts),structured_parse_counts=dict(structured),all_pair_hash_bytes_and_independent_transform_exact=True,known_private_residual=0))
    save(out,'regression.json',regression_result)
    save(out,'ci-metadata.json',ci)
    save(out,'html-classification.json',html)
    save(out,'oracle-classification.json',oracle)
    save(out,'preservation.json',preservation)
    save(out,'closure-classification.json',closure)
    save(out,'browser-classification.json',browser)
    return dict(status='PASS' if remote_verified else 'LOCAL_INTEGRITY_ONLY',archive_integrity_status='PASS' if remote_verified else 'LOCAL_INTEGRITY_ONLY',remote_status='VERIFIED' if remote_verified else 'NOT_VERIFIED_AUTH_BLOCKED',regression_status=regression_result['status'],initial_regression_modules=regression_result['initial_modules'],initial_regression_items=regression_result['initial_items'],profile_gap=regression_result['profile_gap'],evidence_window_retry=regression_result['evidence_window_retry'],source_sha=freeze['source_sha'],archive_entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,regression_modules=regression_result['modules'],unique_regression_passes=regression_result['passed'],new_passes=regression_result['new_unique_passes'],separate_ci=ci['counts'],native_HTTP_HTML_modes=len(html['modes']),native_fetches=html['native_fetches'],bounded_Chrome_modes=len(browser['modes']),design_rows=oracle['design_rows'],design_classification=oracle['classification'],source_paths=len(freeze['source_paths']),tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=len(freeze['runner_paths']),before_after_stable=True,baseline_remote_refs_unchanged=len(baseline['refs']) if remote_verified else None,baseline_remote_refs_requiring_verification=len(baseline['refs']),prior_raw_preserved=len(baseline['prior_raw_sha256']),prior_pairs_preserved=preservation['prior_pairs']['entries'],report_sha256=sha((ROOT/config['report']).read_bytes()),archive_index_sha256=sha((archive/'index.json').read_bytes()),boundaries=['Controlled client probes are not native HTTP or browser tests','Design rows classified by actual evidence; never summed as executed pytest','Historical/WIP failures preserved but not included in final regression denominator','Only explicitly recorded Chrome modes exercised; no all-browser or formal AT claim','Windows, formal AT, real models, production NOT_RUN','Final delivery commit/push and Git blob audit happen after this precommit gate'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ready',required=True);parser.add_argument('--run',default='gate-v1');args=parser.parse_args()
    ready_raw=(ROOT/args.ready).read_bytes();ready=json.loads(ready_raw);assert ready.get('status')=='ARCHIVE_READY','explicit ready signal required'
    config=load(str((OWN/'audit-config-prepared.json').relative_to(ROOT)))
    out=OWN/args.run;out.mkdir(exist_ok=False)
    save(out,'execution-input.json',dict(ready=ready,ready_path=args.ready,ready_sha256=sha(ready_raw),config=config,script_sha256=sha(Path(__file__).read_bytes()),transform_sha256=sha((OWN/'independent_transform.py').read_bytes()),inventory_sha256=sha((OWN/'inventory_rules.py').read_bytes()),profile_gap_sha256=sha((OWN/'profile_gap.py').read_bytes()),t07_retry_sha256=sha((OWN/'t07_retry.py').read_bytes())))
    try:result=gate(config,ready,out,args.ready)
    except Exception as error:
        result=dict(status='FAIL',error_type=type(error).__name__,reason=str(error),traceback=traceback.format_exc())
        save(out,'final-gate.json',result);raise
    result['utc']=datetime.now(timezone.utc).isoformat();save(out,'final-gate.json',result)
    print(json.dumps(result))
if __name__=='__main__':main()
