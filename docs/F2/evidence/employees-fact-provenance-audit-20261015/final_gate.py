"""Read-only independent archive gate. Run only after explicit ARCHIVE_READY."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,hashlib,json,re,subprocess,sys,traceback,xml.etree.ElementTree as ET
from independent_transform import Transform,selftest
ROOT=Path('/workspace/ParkWeave')
OWN=Path(__file__).resolve().parent
RAW_DIRS=['fact-assertion-provenance-root','fact-provenance-backend','fact-provenance-independent','fact-provenance-review','fact-provenance-final','fact-provenance-final-v2']
EXT={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md','.patch','.html'}
SKIP_NAMES={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','delivery-report-template.md','critical-path-draft.md','archive-readme-draft.md'}
SKIP_PARTS={'__pycache__','private-tree','candidate-v2','candidate','worktree','source-v1','private-worktree','source-wip-v1','source-wip-v2','xdg-cache','tmp-smoke1','pytest-cache','.pytest_cache'}
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
def inventory():
    result=[]
    for directory in RAW_DIRS:
        for p in (ROOT/'.runtime'/directory).rglob('*'):
            if not p.is_file() or p.suffix not in EXT or p.name in SKIP_NAMES or '.private.' in p.name:continue
            if SKIP_PARTS.intersection(p.parts):continue
            if any(s.startswith('pytest-') for s in p.parts) and 'unredirected-legacy-artifacts' not in p.parts:continue
            result.append(relative(p))
    return sorted(result)
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
    assert len(source)==624 and len(tracked)==16505 and len(runners)==4
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
    assert record['tracked_source_paths']==624 and record['all_tracked_paths']==16505
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
    assert len(planned)==len(set(planned))==config['expected_modules']==103
    chosen=ready.get('main_window_selection',[dict(window=n,modules=m) for n,m in selection['main_windows'].items()])
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
    assert len(modules)==len(set(modules))==103 and set(modules)==set(planned)
    new_modules={'tests/test_employees_fact_provenance.py','tests/test_employees_fact_provenance_review.py','tests/test_employees_fact_client_probes.py','tests/test_employees_fact_provenance_independent.py'}
    new={n:s for n,s in all_nodes.items() if n.split('::',1)[0] in new_modules}
    assert len(new)==config['expected_new_tests']==61
    return dict(modules=103,passed=len(all_nodes),new_unique_passes=61,windows=windows,nodes=all_nodes)
def ci_metadata(selection,config,freeze,main_nodes):
    record,nodes=window(Path(config['formal_base']),'ci-metadata',freeze)
    assert record['exit_code']==0 and set(record['modules'])==set(selection['separate_ci_window'])
    assert len(record['modules'])==len(set(record['modules']))==12
    assert not set(nodes).intersection(main_nodes)
    assert all(status in ('PASS','SKIP') for status in nodes.values())
    xml=ROOT/config['formal_base']/'ci-metadata.xml'
    skips=[dict(identity=junit_id(case),reason=case.find('skipped').get('message','')) for case in ET.parse(xml).getroot().iter('testcase') if case.find('skipped') is not None]
    assert all(row['reason'] for row in skips)
    return dict(modules=12,counts=dict(Counter(nodes.values())),skip_reasons=skips,main103_denominator_overlap=0)
def html_traces(base,classification):
    scope='FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG'
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
            adopts=[c for c in posts if c['path'].endswith('/service-case-plan')]
            verify=[c for c in posts if c['path'].endswith('/service-case-plan/commands') and c['body']['action']=='VERIFY']
            assert len(adopts)==1 and adopts[0]['status']==201 and adopts[0]['body']['fact_provenance_scope']=='EMPLOYEES_USER_ASSERTION_V1' and adopts[0]['body']['local_revision'] is True
            assert len(verify)==5 and len({c['body']['step_id'] for c in verify})==5 and all(c['status']==200 for c in verify)
            assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
            assert any('/api/cases/worklist' in c['path'] and c['status']==200 for c in calls)
            if mode=='lost_ack':
                recovery=[c for c in calls if c['method']=='GET' and c['path'].endswith('/service-case-plan/command-recovery') and c['status']==200]
                assert recovery,'original command-recovery endpoint was not read'
                captured=[c for c in recovery if c.get('request_key')]
                if captured:
                    assert any(c['request_key']==adopts[0]['request_key'] for c in captured)
                    row['exact_get_key_raw_binding']='CAPTURED_IDEMPOTENCY_KEY_MATCH'
                else:
                    row['exact_get_key_raw_binding']='NOT_RECORDED_GET_IDEMPOTENCY_HEADER'
                    row['key_support']='Original frozen recovery handler and driver closure only; no raw header claim'
        else:assert not posts and any(c['status']==403 and '/employees-fact-impact' in c['path'] for c in calls)
        found[mode]=row
    assert set(found)=={'positive','lost_ack','current_403','late_403'}
    assert len(classification['rows'])==4
    for expected in classification['rows']:
        actual=found[expected['mode']]
        assert expected['trace_sha256']==actual['trace_sha256'] and expected['actual_native_fetches']==actual['native_fetches']
        assert expected['post_count']==actual['posts'] and expected['backend403_count']==actual['backend403']
    assert classification['actual_native_fetches']==sum(v['native_fetches'] for v in found.values())
    return dict(modes=list(found.values()),native_fetches=sum(v['native_fetches'] for v in found.values()),python_control_API_total='NOT_RECORDED',real_browser='NOT_RUN')
def coverage(mapping,all_nodes):
    oracle=load('docs/F2/EmployeesFactProvenanceOracle-20261015.json')
    assert mapping['oracle_sha256']==sha((ROOT/'docs/F2/EmployeesFactProvenanceOracle-20261015.json').read_bytes())
    assert len(mapping['rows'])==len(oracle['rows'])==40
    assert {r['id'] for r in mapping['rows']}=={r['id'] for r in oracle['rows']}
    byid={r['id']:r for r in oracle['rows']};counts=Counter()
    for row in mapping['rows']:
        assert row['literal_expected']==byid[row['id']]['expected']
        if row['execution']=='PASS':
            assert row['evidence']
            for evidence in row['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            assert row['exact_literal_http_pass']==(row['coverage_kind']=='BOUNDED_HTTP_LITERAL')
            counts[row['coverage_kind']]+=1
        else:
            assert row['execution']=='NOT_RUN' and row['exact_literal_http_pass'] is False
            counts['NOT_RUN']+=1
    assert dict(counts)==mapping['counts']
    return dict(design_rows=40,classification=dict(counts),additional_pytest_count=0)
def gate(config,ready,out):
    selftest()
    freeze=load(config['freeze']);assert freeze['source_sha']==config['source_sha']==ready['source_sha']
    before=frozen_snapshot(freeze);save(out,'before.json',before)
    archive=ROOT/config['archive'];index=json.loads((archive/'index.json').read_text())
    assert index['source_sha']==freeze['source_sha']
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
    preservation=dict(previous_raw=preserve(baseline['previous_raw_sha256'],config['expected_legacy_raw']),prior_audit_raw=preserve(baseline['prior_audit_raw_sha256'],config['expected_prior_audit_raw']),additional_audit_raw=preserve(load(config['legacy_audit_preservation']),config['expected_additional_audit_raw']))
    selection=load(config['selection'])
    regression_result=regression(selection,ready,config,freeze)
    ci=ci_metadata(selection,config,freeze,regression_result['nodes'])
    html=html_traces(Path(config['formal_base']),load(ready['html_classification']))
    oracle=coverage(load(ready['coverage_map']),regression_result['nodes'])
    report=(ROOT/config['report']).read_text()
    for text in [freeze['source_sha'],'103',str(regression_result['passed']),'61']:assert text in report,('missing supported report identity/count',text)
    assert 'Windows' in report and ('浏览器' in report or 'browser' in report)
    remote=command('git','ls-remote','origin').decode()
    refs={line.split('\t',1)[1]:line.split('\t',1)[0] for line in remote.splitlines()}
    assert len(baseline['refs'])==config['expected_baseline_refs']==79
    assert all(refs.get(name)==value for name,value in baseline['refs'].items()),'baseline remote reference changed'
    save(out,'remote-current.json',dict(default_network=True,baseline_ref_count=79,baseline_refs_unchanged=True,actual_refs=refs))
    assert all(sha((ROOT/p).read_bytes())==h for p,h in raw_hashes.items()),'raw file changed during audit'
    after=frozen_snapshot(freeze);save(out,'after.json',after);assert before==after
    save(out,'archive-transformation.json',dict(entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,redactions=dict(counts),structured_parse_counts=dict(structured),all_pair_hash_bytes_and_independent_transform_exact=True,known_private_residual=0))
    save(out,'regression.json',regression_result)
    save(out,'ci-metadata.json',ci)
    save(out,'html-classification.json',html)
    save(out,'oracle-classification.json',oracle)
    save(out,'preservation.json',preservation)
    return dict(status='PASS',source_sha=freeze['source_sha'],archive_entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,regression_modules=103,unique_regression_passes=regression_result['passed'],new_passes=61,native_HTTP_HTML_modes=4,native_fetches=html['native_fetches'],design_rows=40,design_classification=oracle['classification'],source_paths=624,tracked_paths=16505,runner_paths=4,before_after_stable=True,baseline_remote_refs_unchanged=79,prior_raw_preserved=4107,prior_audit_raw_preserved=79,additional_audit_raw_preserved=121,report_sha256=sha((ROOT/config['report']).read_bytes()),archive_index_sha256=sha((archive/'index.json').read_bytes()),boundaries=['Controlled client 6 probes are not native HTTP/browser tests','40 design rows classified; never summed as executed pytest','Old181 formal58PASS3FAIL and interrupted partial windows are historical raw only','Historical/WIP failures preserved but not included in final regression denominator','Real browser, Windows, formal AT, semantic judgment, real models, production NOT_RUN','Final delivery commit/push and Git blob audit happen after this precommit gate'])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ready',required=True);parser.add_argument('--run',default='gate-v1');args=parser.parse_args()
    ready=load(args.ready);assert ready.get('status')=='ARCHIVE_READY','explicit ready signal required'
    config=load(str((OWN/'audit-config-prepared.json').relative_to(ROOT)))
    out=OWN/args.run;out.mkdir(exist_ok=False)
    save(out,'execution-input.json',dict(ready=ready,config=config,script_sha256=sha(Path(__file__).read_bytes()),transform_sha256=sha((OWN/'independent_transform.py').read_bytes())))
    try:result=gate(config,ready,out)
    except Exception as error:
        result=dict(status='FAIL',error_type=type(error).__name__,reason=str(error),traceback=traceback.format_exc())
        save(out,'final-gate.json',result);raise
    result['utc']=datetime.now(timezone.utc).isoformat();save(out,'final-gate.json',result)
    print(json.dumps(result))
if __name__=='__main__':main()
