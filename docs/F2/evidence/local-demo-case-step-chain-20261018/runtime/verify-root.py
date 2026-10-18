from pathlib import Path
import json,hashlib,sys,xml.etree.ElementTree as ET
root=Path.cwd();run=root/'.runtime/local-demo-case-step-chain-20261018';w=run/sys.argv[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
maps=[json.loads((w/n).read_text()) for n in ['shared-before.json','mirror-before.json','shared-after.json','mirror-after.json']]
assert all(m==maps[0] for m in maps)
for name,digest in maps[0].items():assert sha((root/name).read_bytes())==digest
report=json.loads((w/'result.json').read_text());assert report['exit_code']==0
nodes=json.loads((w/'collection.json').read_text());assert len(nodes)==13 and len(set(nodes))==13
xml=ET.parse(w/'results.xml');cases=xml.findall('.//testcase');assert len(cases)==13
assert not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases)
calls=[json.loads(l) for l in (w/'calls.jsonl').read_text().splitlines()];actual=[v for v in calls if v['when']=='call'];assert len(actual)==13 and all(v['outcome']=='passed' for v in calls)
origins=json.loads((w/'module-origins.json').read_text());assert origins and all(x['within_mirror'] for x in origins.values())
for item in origins.values():assert sha(Path(item['path']).read_bytes())==item['sha256']
artifacts=list((w/'process-artifacts').glob('test_existing*/actual-chain.json'));assert len(artifacts)==1
chain=json.loads(artifacts[0].read_text());assert chain['run_assignments']==0 and chain['authority_unchanged'] and chain['ordinary_worker'] and chain['cold_plan_results_equal'] and chain['cold_txt_equal'] and chain['deadline_unchanged']
folder=artifacts[0].parent
warm=(folder/'first-pack/download.txt').read_bytes();cold=(folder/'cold-pack/download.txt').read_bytes();assert warm==cold
for stage in ['first-start','cold-start']:
 ready=[json.loads(l) for l in (folder/stage/'serve.stdout').read_text().splitlines() if l.startswith('{')][-1]
 assert ready['mode']=='LOCAL_DEMO_CURRENT_PREPARATION' and ready['models']=='DISABLED'
 if stage=='first-start':initial=ready
 else:assert all(ready[k]!=initial[k] for k in ['postgres_pid','api_pid','worker_pid'])
cold_http=[json.loads(l) for l in (folder/'cold-start/http-metadata.jsonl').read_text().splitlines()];assert all(x['method']=='GET' for x in cold_http)
selected=json.loads((folder/'selection-html/html.stdout').read_text().splitlines()[-1]);assert selected['completeOriginalHTML'] and selected['real_browser'] is False
posts=[c for c in selected['calls'] if c['method']=='POST'];assert len(posts)==2 and posts[0]['path'].endswith('/service-selections') and posts[1]['path'].endswith('/service-case-plan')
result=dict(tested_sha=report['head'],pass_count=13,fail=0,error=0,skip=0,junit_seconds=float(xml.find('testsuite').get('time')),outer_seconds=report['outer_seconds'],four_equal_input_maps=len(maps[0]),module_origins=len(origins),all_origins_within_exact_mirror=True,actual_chain=chain,txt_bytes=len(warm),txt_sha256=sha(warm),cold_requests_get_only=True,selected_original_html_posts=2,full_chain_manual_finish=False,legacy_fixture_finish_only_in_guard_tests=True,independent_dynamic=0,previous_risk_marked_window_not_retried=True,historical_HTTP_timeout='UNKNOWN_OPEN')
(run/('root-verification-'+report['head'][:8]+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
