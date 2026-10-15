"""Independent precollection exception and actual HTTP trace arithmetic.

No root producer, verifier or coverage script is imported/executed.
Only local designated synthetic evidence is read; token/header values are not read
from trace objects or printed. This is evidence verification, not a test rerun.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib,json,re,subprocess

R=Path('/workspace/ParkWeave')
O=R/'.runtime/service-release-preflight-audit'
S='0de44714499ff3ead538dd8dc1436e783ab8f944'
F='.runtime/service-release-preflight-independent/freeze-0de4471-formal'
def read(p):return json.loads((R/p).read_text())
def save(p,v):(O/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def digest(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()

def precollection():
    planned=read('.runtime/service-release-preflight/planned-collection.json')
    actual=[]
    for p in ['.runtime/service-release-preflight/root-1-v1-collection.json','.runtime/service-release-preflight/root-2-v1-collection.json','.runtime/service-release-preflight-review/extra-v2-0de44714-collection.json',F+'-collection.json']:
        c=read(p);actual.extend(c if isinstance(c,list) else [x['nodeid'] for x in c['items']])
    assert len(planned)==len(actual)==2187 and len(set(planned))==len(set(actual))==2187
    planned_only=sorted(set(planned)-set(actual));actual_only=sorted(set(actual)-set(planned))
    assert len(planned_only)==len(actual_only)==1
    prefix='tests/test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden[case_id-'
    pattern=re.compile(re.escape(prefix)+r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\]')
    assert all(pattern.fullmatch(n) for n in planned_only+actual_only)
    def normalize(n):return prefix+'<IMPORT_TIME_UUID>]' if pattern.fullmatch(n) else n
    assert Counter(map(normalize,planned))==Counter(map(normalize,actual))
    assert sum(bool(pattern.fullmatch(n)) for n in actual)==sum(bool(pattern.fullmatch(n)) for n in planned)==1
    source=subprocess.check_output(['git','show',S+':tests/test_template_candidate.py'],cwd=R,text=True)
    assert "('case_id', str(uuid.uuid4()))" in source
    original=subprocess.check_output(['git','show','b2690b4316e2ca4e98c0b83ee2675db74239ccae:tests/test_template_candidate.py'],cwd=R,text=True)
    assert source==original
    fail=read('.runtime/service-release-preflight/coverage-first-failure.json')
    assert fail['status']=='POSTCHECK_FAILED_NOT_TEST_FAILURE' and fail['preplanned_only']==planned_only and fail['actual_collection_only']==actual_only
    receipt=read('.runtime/service-release-preflight/precollection-identity-normalization.json')
    assert receipt['planned_raw']==planned_only and receipt['actual_raw']==actual_only and receipt['same_invocation_collection_junit_remains_raw_and_exact']
    old=R/'.runtime/service-release-preflight/final_coverage.pre-random-case-id-fix.py'
    assert old.is_file() and "sorted(allnodes)==sorted(load(B/'planned-collection.json'))" in old.read_text()
    out={'status':'PASS','source_sha':S,'planned_and_actual_items':2187,'raw_difference':{'planned_only':planned_only,'actual_only':actual_only},'exception_count':1,'source':'tests/test_template_candidate.py:136','source_unchanged_from_baseline':True,'only_exact_function_case_id_canonical_UUID_normalized':True,'other_2186_nodeids_byte_identical':True,'raw_same_invocation_collection_junit_normalized':False,'same_invocation_raw_exactness_checked_separately_in_mechanical_gate':True,'first_failure_and_original_script_preserved':True,'first_failure_sha256':digest('.runtime/service-release-preflight/coverage-first-failure.json'),'original_script_sha256':digest('.runtime/service-release-preflight/final_coverage.pre-random-case-id-fix.py')}
    save('precollection-identity-independent.json',out)
    return out

def traffic():
    own=read(F+'-own-new-traces.json')['records'];inherited=read(F+'-inherited-traces.json')['records']
    paths=[('preflight',x['path']) for x in own]
    paths += [('typed' if '/typed-source-impact-independent/' in x['raw_path'] else 'shared',x['copied_path']) for x in inherited]
    groups=defaultdict(Counter);modes=[];statuses=Counter();total=Counter()
    for group,path in paths:
        if not path.endswith('.stdout.jsonl'):continue
        rows=[json.loads(x) for x in (R/path).read_text().splitlines() if x.strip()]
        summaries=[x for x in rows if 'scope' in x];assert len(summaries)==1
        x=summaries[0];calls=x['calls'];methods=Counter(c['method'] for c in calls)
        assert all(c['method'] in ('GET','POST') and c['path'].startswith('/api/') and isinstance(c['status'],int) and 100<=c['status']<600 for c in calls)
        assert all(set(c)<={'method','path','status','body','request_key','graph_sha256'} for c in calls)
        forbidden={'token','authorization','headers','cookie','csrf_token','access_token','session_token'}
        def forbidden_keys(v):
            if isinstance(v,dict):return any(k.lower() in forbidden or forbidden_keys(z) for k,z in v.items())
            if isinstance(v,list):return any(forbidden_keys(z) for z in v)
            return False
        assert not forbidden_keys(calls)
        groups[group].update(methods);total.update(methods);statuses.update(c['status'] for c in calls)
        record={'group':group,'mode':x['mode'],'requests':len(calls),'methods':dict(methods),'negative_transport_fixture':x.get('negative_transport_fixture',False),'scope':x['scope'],'trace_sha256':digest(path),'source_path':path}
        if group=='preflight':
            assert x['negative_transport_fixture']==(x['mode'] in ('pending','unknown_dto'))
            expected_posts={'repeat':2,'record':1,'lost':1,'lost_withdrawn':1,'tampered':1}.get(x['mode'],0)
            assert methods['POST']==expected_posts
            assert all(c['method']!='POST' or re.fullmatch(r'/api/preparations/[a-f0-9-]{36}/service-release-preflight',c['path']) for c in calls)
        modes.append(record)
    assert len(modes)==29 and sum(x['negative_transport_fixture'] for x in modes)==2
    assert dict(total)=={'GET':300,'POST':34}
    assert {k:dict(v) for k,v in groups.items()}=={'preflight':{'GET':80,'POST':6},'typed':{'GET':111,'POST':14},'shared':{'GET':109,'POST':14}}
    python=read(F+'-http-traffic.json');requests=python['requests'];py_methods=Counter(x['method'] for x in requests)
    assert python['count']==len(requests)==5704 and not python['headers_or_tokens_saved']
    assert all(x['transport']=='ACTUAL_LOOPBACK_HTTP' and set(x)=={'method','path','test','transport'} and x['test'].startswith('tests/') for x in requests)
    assert dict(py_methods)=={'POST':4159,'GET':1545}
    out={'status':'PASS','source_sha':S,'node_actual_fetch_requests':334,'node_methods':dict(total),'node_by_group':{k:dict(v) for k,v in groups.items()},'node_statuses':dict(statuses),'python_actual_loopback_requests':5704,'python_methods':dict(py_methods),'http_traffic_sha256':digest(F+'-http-traffic.json'),'all_actual_trace_headers_or_tokens_absent':True,'new_preflight_POSTs':6,'new_preflight_POST_scope':'Separate private preflight evidence endpoint only; no original business command POST on wire in these14 new modes','actual_service_modes_excluding_designated_negative_transport':27,'designated_DOM_transport_negative_modes':['pending','unknown_dto'],'mode_details':modes,'limitations':['5704 and334 are separate instrumentation surfaces, not asserted disjoint or to be added','Pending intercepts original command before wire; it is not a real backend original-command rejection','unknown_dto changes an actual200 response to future DTO schema to test UI refusal; not backend UNKNOWN output','Lost/late/tampered flows use controlled synthetic faults','NodeVM DOM is not a real browser and request counts do not prove real-world business fulfillment']}
    save('actual-http-mode-independent.json',out)
    return out

if __name__=='__main__':
    a=precollection();b=traffic();print(json.dumps({'status':'PASS','precollection_exception':a['exception_count'],'node_actual_requests':b['node_actual_fetch_requests'],'python_actual_requests':b['python_actual_loopback_requests'],'modes':len(b['mode_details'])}))
