"""Independent post-run evidence checks, without rerunning product actions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
SOURCE=sys.argv[1]
assert re.fullmatch('[a-f0-9]{40}',SOURCE)
PREFIX='freeze-'+SOURCE[:7]+'-formal'


def read(name):return json.loads((OUT/(PREFIX+'-'+name+'.json')).read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,data):(OUT/(PREFIX+'-'+name+'.json')).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


result=read('result');before=read('before');after=read('after');collection=read('collection')
assert result['source_sha']==result['head_after']==before['head']==after['head']==SOURCE
assert result['exit_code']==result['failures']==result['errors']==result['skipped']==0
assert before['files']==after['files'] and not result['tracked_changed'] and not result['tracked_status_after']
xml=ET.parse(OUT/(PREFIX+'-junit.xml'))
expected=Counter((x['classname'],x['name']) for x in collection['items'])
actual=Counter((x.attrib['classname'],x.attrib['name']) for x in xml.iter('testcase'))
assert expected==actual and all(n==1 for n in expected.values())
inherited=read('inherited-traces')['records'];own=read('own-new-traces')['records']
assert len(inherited)==32 and len(own)==29
for row in inherited:
    assert row['source_sha']==SOURCE and '.private.' not in row['raw_path']
    assert digest(ROOT/row['raw_path'])==row['sha256']==digest(ROOT/row['copied_path'])
paths=[ROOT/x['copied_path'] for x in inherited]+[ROOT/x['path'] for x in own]
flows=[];oracles={}
for path in paths:
    if path.name.startswith('oracle-'):
        group=path.parent.name if 'inherited-traces' in str(path) else 'service-release-preflight-independent'
        rows=[json.loads(line) for line in path.read_text().splitlines() if line]
        assert {r['head'] for r in rows}=={SOURCE}
        oracles[group]=dict(records=len(rows),expected_pairs=sum(len(r['expected_affected']) for r in rows),actual_pairs=sum(len(r['actual_affected']) for r in rows),
            missed_count=sum(r['missed_count'] for r in rows),wrong_count=sum(r['wrong_count'] for r in rows),wrong_preserved_count=sum(r['wrong_preserved_count'] for r in rows),wrong_locked_count=sum(r.get('wrong_locked_count',0) for r in rows),
            expected_locked_pairs=sum(len(r.get('expected_locked',[])) for r in rows),actual_locked_pairs=sum(len(r.get('actual_locked',[])) for r in rows),
            intentional_unknown_records=sum(r.get('intentional_unknown',r.get('intentional_unknown_expansion',False)) for r in rows),
            all_unknown_scope_records=sum(r.get('unknown_scope') is not None for r in rows) if any('unknown_scope' in r for r in rows) else None)
    if not path.name.endswith('.stdout.jsonl'):continue
    rows=[json.loads(line) for line in path.read_text().splitlines() if line]
    results=[r for r in rows if 'scope' in r];assert len(results)==1
    item=results[0];calls=item['calls']
    flows.append(dict(scope=item['scope'],mode=item['mode'],checks=item['checks'],requests=len(calls),posts=sum(c['method']=='POST' for c in calls),
        negative_transport_fixture=item.get('negative_transport_fixture',False),trace=str(path.relative_to(ROOT)),trace_sha256=digest(path)))
assert len(flows)==29 and sum(x['scope']=='FULL_ORIGINAL_HTML_SERVICE_RELEASE_PREFLIGHT_REAL_HTTP_ASGI_OWNED_PG' for x in flows)==14
assert len(oracles)==3
for group,value in oracles.items():
    assert value['expected_pairs']==value['actual_pairs'] and not any(value[k] for k in ('missed_count','wrong_count','wrong_preserved_count','wrong_locked_count'))
assert oracles['typed-source-impact-independent']['records']==11 and oracles['typed-source-impact-independent']['expected_pairs']==38
assert oracles['shared-source-cases-independent']['records']==12 and oracles['shared-source-cases-independent']['expected_pairs']==24
assert oracles['service-release-preflight-independent']['records']==19 and oracles['service-release-preflight-independent']['expected_pairs']==82
save('html-summary',dict(source_sha=SOURCE,same_window=True,passed_flows=len(flows),failed_flows=0,flows=flows,real_browser='NOT_RUN'))
private=OUT/(PREFIX+'-redaction-values.private.json');assert private.stat().st_mode&0o777==0o600
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head==SOURCE
report=dict(source_sha=SOURCE,source_and_tracked_unchanged=True,all_tracked_paths=len(before['files']),collected=collection['count'],
    exact_collection_junit_match=True,duplicate_tests=0,inherited_copy_hashes_exact=True,inherited_trace_count=len(inherited),own_trace_count=len(own),
    actual_python_http_requests=read('http-traffic')['count'],actual_node_http_requests=sum(x['requests'] for x in flows),html_flow_count=len(flows),
    private_mode='0600',private_value_count=len(json.loads(private.read_text())),private_values_printed_or_exported=False,
    oracle_groups=oracles,known_initial_untracked_root_document='docs/F2/ServiceReleasePreflight-20261015.md',models=0,browser='NOT_RUN',Windows='NOT_RUN',formal_AT='NOT_RUN',production='NOT_RUN')
save('validation',report)
print(json.dumps(report,sort_keys=True))
