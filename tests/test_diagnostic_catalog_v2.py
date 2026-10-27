"""Approved global catalog: exact AST, aggregate limits, one fresh operation."""
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import pytest
from catalog_test_support import owned_catalog,mutate,install,catalog_ids
from test_windows_ci_preparation import module,ROOT
from test_summary_publication import publication,console_json


def test_4096_is_complete_streamed_and_4097_refuses(tmp_path,monkeypatch):
    text=''.join(f'def test_{i:04d}(): pass\n' for i in reversed(range(4096)))
    root,cv=owned_catalog(tmp_path,monkeypatch,{'tests/test_a.py':text})
    first='tests/test_a.py::test_0000';last='tests/test_a.py::test_4095'
    proof=cv.scan(root,[first,last,'tests/test_a.py::test_absent'],retained_references=3)
    assert first in proof and last in proof and 'tests/test_a.py::test_absent' not in proof
    assert proof.stats['ids']==4096 and proof.stats['files']==1 and proof.stats['catalog_scans']==1
    assert proof.stats['retained_reference_bound']<3000
    (root/'tests/test_a.py').write_text(text+'def test_4096(): pass\n')
    with pytest.raises(cv.Refused,match='CAPACITY_EXCEEDED'):cv.generate(root)
    with pytest.raises(cv.Refused):cv.scan(root,[first])


@pytest.mark.parametrize('count',[512,513])
def test_source_file_global_limit(tmp_path,monkeypatch,count):
    sources={f'tests/test_{i:03d}.py':('def test_one(): pass\n' if i==0 else '# empty trusted source\n') for i in range(count)}
    if count==512:
        root,cv=owned_catalog(tmp_path,monkeypatch,sources)
        assert cv.scan(root).stats['files']==512
    else:
        cv=module('diagnostic_catalog').cv;root=tmp_path/'repo';(root/'tests').mkdir(parents=True)
        for name,text in sources.items():(root/name).write_text(text)
        monkeypatch.setattr(cv,'FILE_DOMAINS',{name:'FOUNDATION_HOST' for name in sources})
        with pytest.raises(cv.Refused,match='SOURCE_REFUSED'):cv.generate(root)


@pytest.mark.parametrize('fault',['invalid_json','duplicate_key','duplicate_id','omitted_id','wrong_file','wrong_domain','extra_field','reversed_ids','hash_only_source_change'])
def test_unselected_domain_full_semantics_and_AST_before_membership(tmp_path,monkeypatch,fault):
    sources={'tests/test_a.py':'def test_alpha(): pass\n',
             'tests/test_b.py':'def test_beta(): pass\ndef test_gamma(): pass\n'}
    root,cv=owned_catalog(tmp_path,monkeypatch,sources)
    domain='MATERIAL';delta=0
    if fault=='invalid_json':change=lambda raw:raw.replace(b'{"id":',b'{broken:')
    elif fault=='duplicate_key':change=lambda raw:raw.replace(b'{"id":',b'{"id":"private","id":')
    elif fault=='duplicate_id':
        change=lambda raw:raw+raw.splitlines(keepends=True)[-1];delta=1
    elif fault=='omitted_id':change=lambda raw:b''.join(raw.splitlines(keepends=True)[:-1]);delta=-1
    elif fault=='wrong_file':change=lambda raw:raw.replace(b'tests/test_b.py',b'tests/test_a.py')
    elif fault=='wrong_domain':
        domain='FOUNDATION_HOST';change=lambda raw:raw.replace(b'tests/test_a.py',b'tests/test_b.py')
    elif fault=='extra_field':change=lambda raw:raw.replace(b'{"id":',b'{"private":0,"id":')
    elif fault=='reversed_ids':change=lambda raw:raw.splitlines(keepends=True)[0]+b''.join(reversed(raw.splitlines(keepends=True)[1:]))
    else:
        source=root/'tests/test_b.py';old=hashlib.sha256(source.read_bytes()).hexdigest()
        source.write_text(source.read_text()+'def test_new(): pass\n')
        new=hashlib.sha256(source.read_bytes()).hexdigest()
        change=lambda raw:raw.replace(old.encode(),new.encode())
    # Recompute byte hashes/index generation too. A hash-only validator would
    # miss the semantic/AST damage in a domain that this request never selects.
    mutate(root,cv,domain,change,id_delta=delta)
    with pytest.raises(cv.Refused):cv.scan(root,['tests/test_a.py::test_alpha'])


def test_source_snapshot_and_unknown_source_change_refuse(tmp_path,monkeypatch):
    root,cv=owned_catalog(tmp_path,monkeypatch)
    original=cv.source_ids
    changed=[]
    def source(*args):
        result=original(*args)
        if not changed:
            path=root/'tests/test_a.py';path.write_text(path.read_text()+'# drift\n');changed.append(True)
        return result
    monkeypatch.setattr(cv,'source_ids',source)
    with pytest.raises(cv.Refused,match='INPUT_CHANGED'):cv.scan(root,['tests/test_a.py::test_alpha'])
    monkeypatch.setattr(cv,'source_ids',original)
    (root/'tests/test_unknown.py').write_text('def test_private(): pass\n')
    with pytest.raises(cv.Refused,match='SOURCE_SET_MISMATCH'):cv.scan(root)


def test_index_line_and_aggregate_byte_boundaries(tmp_path,monkeypatch):
    text=''.join(f'def test_{i:04d}(): pass\n' for i in range(1100))
    root,cv=owned_catalog(tmp_path,monkeypatch,{'tests/test_a.py':text})
    index=cv.decode((root/cv.CATALOG).read_bytes());folder=root/cv.DIRECTORY/index['generation']
    payloads={d:(folder/(d+'.jsonl')).read_bytes() for d in cv.DOMAINS}
    rows=payloads['FOUNDATION_HOST'].splitlines(keepends=True)
    # Whitespace remains valid JSON; every independently bounded row <=512.
    target=cv.MAX_BYTES-len(cv.encode(index))
    extra=target-sum(map(len,payloads.values()))
    for i,line in enumerate(rows):
        add=min(extra,512-len(line));rows[i]=line[:-1]+b' '*add+b'\n';extra-=add
        if not extra:break
    assert extra==0
    payloads['FOUNDATION_HOST']=b''.join(rows)
    install(root,cv,index,payloads)
    # The bytes field may gain a decimal digit; adjust only harmless padding.
    size=len((root/cv.CATALOG).read_bytes())+sum(map(len,payloads.values()))
    if size>cv.MAX_BYTES:
        payloads['FOUNDATION_HOST']=payloads['FOUNDATION_HOST'].replace(b'  ',b' ',size-cv.MAX_BYTES)
        install(root,cv,index,payloads)
    assert cv.scan(root).stats['raw_bytes']==524288
    index_path=root/cv.CATALOG
    with index_path.open('ab') as stream:stream.write(b' ')
    with pytest.raises(cv.Refused,match='CATALOG_LIMIT'):cv.scan(root)
    index_path.write_bytes(cv.encode(index))
    # Separately test index and row limits using a small catalog again.
    monkeypatch.setattr(cv,'MAX_BYTES',2*524288)
    raw=index_path.read_bytes();index_path.write_bytes(b' '*(8192-len(raw))+raw)
    assert cv.scan(root).stats['ids']==1100
    with index_path.open('ab') as stream:stream.write(b' ')
    with pytest.raises(cv.Refused,match='INDEX_LIMIT'):cv.scan(root)
    index_path.write_bytes(cv.encode(index))
    mutate(root,cv,'FOUNDATION_HOST',lambda raw:raw.split(b'\n',1)[0]+b' '*(512-len(raw.split(b'\n',1)[0]))+b'\n'+raw.split(b'\n',1)[1])
    with pytest.raises(cv.Refused,match='LINE_LIMIT'):cv.scan(root)


def test_832_request_and_3000_reference_ledgers_do_not_reset(tmp_path,monkeypatch):
    text=''.join(f'def test_{i:04d}(): pass\n' for i in range(832))
    root,cv=owned_catalog(tmp_path,monkeypatch,{'tests/test_a.py':text})
    ids=[f'tests/test_a.py::test_{i:04d}' for i in range(832)]
    proof=cv.scan(root,ids,retained_references=1904)
    assert proof.stats['requests']==832 and proof.stats['retained_reference_bound']==3000
    assert all(identity in proof for identity in ids)
    with pytest.raises(cv.Refused,match='REFERENCE_LIMIT'):cv.scan(root,ids,retained_references=1905)
    with pytest.raises(cv.Refused,match='REQUEST_LIMIT'):cv.scan(root,[ids[0]]*833)


def test_real_publisher_one_global_scan_before_any_output(publication,monkeypatch,capsys):
    source,_,_=publication;publisher=module('publish_summary');cv=module('diagnostic_catalog').cv
    original=cv.scan;calls=[]
    def scan(*args,**kwargs):calls.append(True);return original(*args,**kwargs)
    monkeypatch.setattr(cv,'scan',scan)
    assert publisher.main(source)==0
    assert len(calls)==1 and console_json(capsys.readouterr().out)['publication_state']=='SUMMARY_AVAILABLE'


def test_publisher_counts_keys_and_projection_reference_budget(monkeypatch):
    publisher=module('publish_summary')
    ids=catalog_ids()[:800]
    public=publisher.base('SUMMARY_AVAILABLE');public.update(report_state='COMPLETED',active_phase='UNKNOWN',cases=[])
    for n in range(32):
        chosen=ids[n*25:(n+1)*25]
        public['cases'].append({'case':'full_engineering_regression','status':'FAIL','failure_diagnostics':{
            'state':'AVAILABLE','failed_test_ids':chosen,'failed_test_counts':dict.fromkeys(chosen,1),
            'mapped_failed_cases':25,'mapped_cases_omitted':0,'failed_cases':25,'unknown_failed_cases':0}})
    assert publisher.identity_references(public)==1600
    commands,ok=publisher.annotation_commands(public)
    assert not ok and len(commands)==1 and 'ANNOTATIONS_UNAVAILABLE' in commands[0]


def test_async_checkpoint_coalesces_without_scan_cache_and_keeps_observation_clock(tmp_path,monkeypatch):
    from scripts.windows_ci import regression_plugin as plugin
    calls=[];entered=threading.Event();release=threading.Event()
    def sink(path,phase,node,**kw):
        calls.append((phase,kw));entered.set();assert release.wait(3)
    monkeypatch.setattr(plugin,'write',sink)
    path=tmp_path/'server-regression-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.progress.json'
    progress=plugin.Progress(SimpleNamespace(getoption=lambda _:path),async_checkpoint=True)
    progress.values.update(collected=2,ordinal=1)
    try:
        before=time.monotonic_ns();progress.mark('pytest_setup','tests/test_a.py::test_alpha')
        assert entered.wait(2)
        for _ in range(20):progress.mark('pytest_call','tests/test_a.py::test_alpha')
        assert isinstance(progress.checkpoint_pending,bytes) and len(progress.checkpoint_pending)<=1024
        assert len(calls)==1 and calls[0][1]['observed_clock_ns']>=before
        # Close during the injected scan: cancellation is passed to the actual
        # writer and prevents replace, even if that scan returns after close.
        release.set();assert progress.close_checkpoint()
        assert progress.checkpoint_pending is None and progress.checkpoint_closed.is_set()
        assert calls[0][1]['_cancel'].is_set() and not progress.checkpoint_thread.is_alive()
    finally:release.set();progress.close_checkpoint()


def test_progress_cancelled_mid_scan_cannot_replace_and_age_includes_scan(tmp_path,monkeypatch):
    progress=module('regression_progress');path=tmp_path/'server-regression-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.progress.json'
    cancelled=threading.Event();lock=threading.Lock();called=[]
    class Proof:
        def __contains__(self,key):return True
        def assert_current(self):cancelled.set()
    monkeypatch.setattr(progress,'trusted_tests',lambda ids:called.append(ids) or Proof())
    path.write_text('preserved')
    progress.write(path,'pytest_call','tests/test_a.py::test_alpha',_cancel=cancelled,_commit_lock=lock)
    assert len(called)==1 and path.read_text()=='preserved'
    assert not list(tmp_path.glob('.progress-*.tmp'))
    proof=Proof();monkeypatch.setattr(proof,'assert_current',lambda:None)
    monkeypatch.setattr(progress,'trusted_tests',lambda ids:proof)
    obs={**{k:0 for k in progress.TIMINGS},'completed':0,'collected':1,'ordinal':1,'fixture_stage':'NONE','sample_attempts':0,'sample_state':'NOT_SAMPLED'}
    observed=time.monotonic_ns()-2_000_000_000
    progress.write(path,'pytest_call','tests/test_a.py::test_alpha',telemetry=obs,observed_clock_ns=observed)
    assert json.loads(path.read_bytes())['clock_ns']==observed
    assert progress.read_snapshot(path)['regression_observation']['checkpoint_age_ms']>=2000


def test_junit_streaming_discards_private_attributes_and_refuses_large_tag(tmp_path,monkeypatch):
    from test_ci_diagnostics import junit
    diagnostics=module('diagnostics');path,reference=junit(tmp_path,[]);calls=[]
    class Proof:
        def __contains__(self,key):return False
        def assert_current(self):pass
    monkeypatch.setattr(diagnostics,'_allowed_tests',lambda ids=(),**kw:calls.append(kw) or Proof())
    identity='tests/test_a.py::test_alpha'
    path.write_text('<testsuite>'+('<testcase private="'+identity+'"/>' )*3101+'</testsuite>')
    assert diagnostics.failure_tests(tmp_path,reference)['state']=='AVAILABLE'
    assert calls==[{'retained_references':0}]
    # A single start tag must be refused before Expat allocates attributes.
    path.write_text('<testsuite '+''.join(f'a{i}="{identity}" ' for i in range(1500))+'/>')
    assert diagnostics.failure_tests(tmp_path,reference)['state']=='ALLOWLIST_UNAVAILABLE'
    assert len(calls)==1
    path.write_text('<'*100000)
    assert diagnostics.failure_tests(tmp_path,reference)['state']=='JUNIT_INVALID'
    class Changed(Proof):
        def assert_current(self):raise ValueError('INPUT_CHANGED')
    monkeypatch.setattr(diagnostics,'_allowed_tests',lambda *a,**kw:Changed())
    path.write_text('<testsuite/>')
    assert diagnostics.failure_tests(tmp_path,reference)=={'state':'ALLOWLIST_UNAVAILABLE','failed_test_ids':[],'test_cases_seen':0,'failed_cases':0,'unknown_failed_cases':0,'ids_truncated':False}


def test_legacy_reference_scratch_is_reserved_before_materializing(tmp_path,monkeypatch):
    maintenance=module('diagnostic_catalog')
    root=tmp_path/'repo';path=root/maintenance.CATALOG;path.parent.mkdir(parents=True)
    ids=[f'tests/test_a.py::test_{n:04d}' for n in range(3000)]
    path.write_text(json.dumps({'schema':1,'test_ids':ids}));before=path.read_bytes()
    assert maintenance.inspect(root,write=True)['status']=='REFERENCE_LIMIT'
    assert path.read_bytes()==before
    path.write_text(json.dumps({'schema':1,'test_ids':ids[:2954]}))
    assert maintenance._current(root)[-1]==2954
    # A nested legacy value is refused before recursively decoding its IDs.
    path.write_text(json.dumps({'schema':1,'test_ids':[ids]}))
    assert maintenance.inspect(root,write=True)['status']=='CATALOG_REFUSED'


def test_empty_progress_checkpoint_still_refuses_unavailable_catalog(tmp_path,monkeypatch):
    progress=module('regression_progress');path=tmp_path/'server-regression-cccccccccccccccccccccccccccccccc.progress.json'
    path.write_text('preserved');calls=[]
    def refused(ids):calls.append(ids);raise ValueError('CATALOG_REFUSED')
    monkeypatch.setattr(progress,'trusted_tests',refused)
    progress.write(path,'pytest_collect',None)
    assert calls==[[]] and path.read_text()=='preserved'


def test_checkpoint_close_deadline_includes_commit_lock(tmp_path):
    from scripts.windows_ci import regression_plugin as plugin
    progress=plugin.Progress(SimpleNamespace(getoption=lambda _:tmp_path/'unused'),async_checkpoint=True)
    progress.checkpoint_commit_lock.acquire()
    try:
        start=time.monotonic();assert not progress.close_checkpoint()
        assert 3.0<=time.monotonic()-start<4.5
        assert progress.checkpoint_closed.is_set()
    finally:progress.checkpoint_commit_lock.release();progress.close_checkpoint()



def test_publisher_checks_JSON_hook_peak_before_decoding_full_tree(publication,monkeypatch):
    publisher=module('publish_summary');source,path,_=publication
    # Every key and value is an exact diagnostic identity. Escaping must not
    # bypass the token ledger; pairs plus dict would exceed 3000 references.
    items={f'tests/test_a.py::test_{n}':'tests/test_a.py::test_value' for n in range(900)}
    text=json.dumps(items).replace('tests/',r'\u0074ests/')
    assert len(text.encode())<65536
    path.write_text(text)
    monkeypatch.setattr(publisher,'strict_object',lambda pairs:pytest.fail('must refuse before object hook'))
    assert publisher.read_summary(source)['publication_state']=='SUMMARY_INVALID'
    with pytest.raises(ValueError):publisher.preflight_json_references('"'+'\\'*10000)
    # Nested business arrays do not duplicate every contained string at each
    # object hook. Only direct full-ID key/value references need a second slot.
    publisher.preflight_json_references(json.dumps({'ids':['tests/test_a.py::test_value']*1600}))



@pytest.mark.parametrize('shape',['key','value','escaped_key','escaped_value','nested_array'])
def test_index_identity_strings_refuse_before_object_decode_at_reference_limit(tmp_path,monkeypatch,shape):
    root,cv=owned_catalog(tmp_path,monkeypatch);identity='tests/test_a.py::test_alpha'
    index=json.loads((root/cv.CATALOG).read_bytes())
    if shape.endswith('key'):index[identity]=0
    elif shape=='nested_array':index['private']=[[identity]]
    else:index['private']=identity
    raw=json.dumps(index).encode()
    if shape.startswith('escaped'):raw=raw.replace(b'tests/',b'\\u0074ests/')
    path=root/cv.CATALOG;path.write_bytes(raw)
    monkeypatch.setattr(cv,'unique',lambda pairs:pytest.fail('index identities must refuse before object materialization'))
    # 2735 caller refs + one query key + 264 reserved scratch == 3000.
    with pytest.raises(cv.Refused,match='INDEX_REFUSED'):
        cv.scan(root,[identity],retained_references=2735)
    with pytest.raises(cv.Refused,match='INDEX_REFUSED'):
        cv.scan(root,[identity],retained_references=2735,_index_input=(raw,cv.fingerprint(path)))
    with pytest.raises(cv.Refused,match='INDEX_REFUSED'):
        module('diagnostic_catalog')._current(root)
