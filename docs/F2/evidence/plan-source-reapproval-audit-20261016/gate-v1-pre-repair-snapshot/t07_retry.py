"""Finite full-window T07 artifact-path retry, preserving the original ten errors."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave')
OWN=Path(__file__).resolve().parent
ENV='PARKWEAVE_T07_EVIDENCE_DIR'
MODULE='tests/test_f2_t07_full_chain.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def verify_original(config,freeze,window):
    spec=config['t07_retry'];base=Path(config['formal_base'])
    record,nodes=window(base,'related-08',freeze)
    assert len(record['modules'])==len(set(record['modules']))==12 and len(nodes)==508
    assert record['exit_code']==1 and record['counts']==dict(PASS=498,FAIL=0,ERROR=10,SKIP=0)
    for p,h in spec['original_evidence_sha256'].items():assert sha(ROOT/p)==h
    manifest=read(ROOT/spec['preserved_manifest'])
    assert manifest['status']=='DISCOVERED_UNCAPTURED_V1_OUTPUTS_PRESERVED' and manifest['no_original_overwrite'] is True
    assert manifest['raw_json_embeds_source_sha'] is False and manifest['window_source_sha']=='929d4f7a13c0b074e8340dad21f4460c7ddacd23'
    v1path=ROOT/manifest['original_window'];assert sha(v1path)==manifest['original_window_sha256']
    v1=read(v1path);assert v1['source_sha']==manifest['window_source_sha']
    start=datetime.fromisoformat(v1['started_utc']);end=datetime.fromisoformat(v1['finished_utc'])
    saved=read(OWN/'t07-evidence-preflight/static-preflight.json')
    original={row['node']:row for row in saved['current_files']}
    rows=manifest['entries'];assert len(rows)==len(original)==10
    seen=set()
    for row in rows:
        node=row['test_id'];assert node not in seen and node in original and node in v1['collected_nodes'];seen.add(node)
        old=ROOT/row['original_path'];copy=ROOT/row['copy_path'];raw=old.read_bytes()
        assert copy.read_bytes()==raw and len(raw)==row['bytes'] and sha(old)==row['sha256']==sha(copy)==original[node]['sha256']
        assert read(old)['test_id']==node and old.stem==hashlib.sha256(node.encode()).hexdigest()[:12]
        stamp=datetime.fromtimestamp(old.stat().st_mtime,timezone.utc)
        assert stamp.isoformat()==row['observed_mtime_utc']==original[node]['mtime_utc'] and start<=stamp<=end
    assert {n for n,s in nodes.items() if s=='ERROR'}==seen and all(n.startswith(MODULE+'::') for n in seen)
    xml=ROOT/base/'related-08.xml';errors=[c for c in ET.parse(xml).iter('testcase') if c.find('error') is not None]
    assert len(errors)==10
    names={n.split('::',1)[1]:n for n in seen}
    for c in errors:
        node=names[c.get('name')];row=original[node];error=c.find('error');text=''.join(error.itertext())
        assert error.get('message','').startswith('failed on teardown with "AssertionError: actual evidence window may not overwrite a previous run')
        assert row['path'] in text and 'tests/test_f2_t07_full_chain.py:431: AssertionError' in text
        assert 'assert not target.exists()' in text
    return dict(original_window='related-08',source_sha=freeze['source_sha'],original_counts=record['counts'],modules=record['modules'],collected_nodes=list(nodes),error_nodes=sorted(seen),legacy_originals_and_exact_copies=10,legacy_artifact_source_sha_embedded=False,all_original_mtimes_within_v1_window=True)

def check(config,ready,freeze,window,chosen):
    original=verify_original(config,freeze,window)
    replacements=[item for item in chosen if item.get('replaces')]
    assert len(replacements)==1,'only the explicit full related-08 retry is supported'
    item=replacements[0];assert item['reason'] and item['window']!='related-08'
    assert item['replaces']==[dict(window='related-08',modules=original['modules'])]
    assert item['modules']==original['modules'] and not any(row['window']=='related-08' for row in chosen)
    retry,nodes=window(Path(config['formal_base']),item['window'],freeze)
    assert retry['exit_code']==0 and retry['counts']==dict(PASS=508,FAIL=0,ERROR=0,SKIP=0)
    assert retry['modules']==original['modules'] and set(nodes)==set(original['collected_nodes'])
    context=read(ROOT/item['retry_context'])
    assert context['source_sha']==freeze['source_sha'] and context['original_window']=='related-08' and context['retry_window']==item['window']
    assert context['modules']==original['modules'] and context['status']=='PREPARED_NOT_EXECUTED'
    assert context['source_or_runner_edits'] is False
    assert set(context['environment_override'])=={ENV}
    destination=Path(context['environment_override'][ENV]);assert destination.is_absolute()
    assert destination.is_relative_to(ROOT/config['formal_base']/item['window'])
    assert not destination.is_relative_to(ROOT/'.runtime/f2-t07-full-chain')
    def normalize(argv):return [v for v in argv if not v.startswith(('--basetemp=','--junitxml='))]
    first=read(ROOT/config['formal_base']/'related-08.json')
    assert normalize(first['argv'])==normalize(retry['argv'])
    spec=config['t07_retry']
    for p,h in spec['predeclared_sha256'].items():assert sha(ROOT/p)==h
    assert item['retry_context']==spec['context']
    assert chosen==read(ROOT/spec['effective_selection'])
    for field,suffix in (('original_receipt_sha256','.json'),('original_xml_sha256','.xml'),('original_log_sha256','.log')):
        assert context[field]==sha(ROOT/config['formal_base']/('related-08'+suffix))
    assert context['original_directory_manifest']==spec['preserved_manifest'] and context['original_directory_manifest_sha256']==sha(ROOT/spec['preserved_manifest'])
    expected_errors={}
    for c in ET.parse(ROOT/config['formal_base']/'related-08.xml').iter('testcase'):
        if c.find('error') is not None:expected_errors[MODULE+'::'+c.get('name')]=c.find('error').get('message')
    assert context['exact_teardown_error_messages']==expected_errors
    controller=ast.parse((ROOT/spec['controller']).read_text())
    expected_absent=ast.dump(ast.parse("assert not Path(override['PARKWEAVE_T07_EVIDENCE_DIR']).exists()").body[0],include_attributes=False)
    matches=[i for i,n in enumerate(controller.body) if isinstance(n,ast.Assert) and ast.dump(n,include_attributes=False)==expected_absent]
    before_write=[i for i,n in enumerate(controller.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text' and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='before']
    retry_run=[i for i,n in enumerate(controller.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='results' for t in n.targets)]
    assert len(matches)==len(before_write)==len(retry_run)==1 and matches[0]<before_write[0]<retry_run[0]
    before=read(ROOT/spec['execution_before']);after=read(ROOT/spec['execution_after'])
    assert before['status']=='STARTING_PREDECLARED_COMPLETE_RETRY' and after['status']=='COMPLETE'
    assert before['source_sha']==after['source_sha']==freeze['source_sha']
    assert before['context_path']==spec['context'] and before['context_sha256']==after['context_sha256']==sha(ROOT/spec['context'])
    assert before['controller_sha256']==after['controller_sha256']==sha(ROOT/spec['controller'])
    assert before['environment_override']==context['environment_override']
    assert before['original_ci_started'] is False and before['original_recovery_started'] is False
    progress=before['all_parallel_finished'];selection=read(ROOT/config['selection'])
    assert not progress['active'] and not progress['pending'] and set(progress['finished'])==set(selection['main_windows'])-{'recovery-solo'}
    assert after['results']=={item['window']:0,'ci-metadata-solo':0,'recovery-solo':0} and after['original10_and_exact_copies_unchanged'] is True
    at=datetime.fromisoformat(before['utc']);assert datetime.fromisoformat(retry['started_utc'])>=at
    for name in progress['finished']:
        receipt=read(ROOT/config['formal_base']/(name+'.json'));assert datetime.fromisoformat(receipt['finished_utc'])<=at
    ci=read(ROOT/config['formal_base']/'ci-metadata-solo.json');recovery=read(ROOT/config['formal_base']/'recovery-solo.json')
    assert datetime.fromisoformat(ci['started_utc'])>=datetime.fromisoformat(retry['finished_utc'])
    assert datetime.fromisoformat(recovery['started_utc'])>=datetime.fromisoformat(ci['finished_utc'])
    assert datetime.fromisoformat(after['finished_utc'])>=datetime.fromisoformat(recovery['finished_utc'])
    paths=list(destination.glob('*.json'));assert len(paths)==10
    start=datetime.fromisoformat(retry['started_utc']);end=datetime.fromisoformat(retry['finished_utc'])
    new_nodes=set()
    for p in paths:
        value=read(p);node=value['test_id'];assert node not in new_nodes;new_nodes.add(node)
        assert p.stem==hashlib.sha256(node.encode()).hexdigest()[:12]
        assert start<=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc)<=end
    assert new_nodes==set(original['error_nodes'])
    return dict(original=original,retry_window=item['window'],retry_counts=retry['counts'],retry_context=item['retry_context'],retry_context_sha256=sha(ROOT/item['retry_context']),environment=context['environment_override'],fresh_artifacts=10,complete_window_replaced=True,original_errors_preserved=True,additional_pytest_count=0)
