from pathlib import Path
import json,hashlib,sys,xml.etree.ElementTree as ET
root=Path.cwd();r=root/'.runtime/at28-resource-observation-20261018';w=r/sys.argv[1];sha=lambda b:hashlib.sha256(b).hexdigest()
maps=[json.loads((w/n).read_text()) for n in ['shared-before.json','mirror-before.json','shared-after.json','mirror-after.json']];assert all(x==maps[0] for x in maps)
for p,h in maps[0].items():assert sha((root/p).read_bytes())==h
orig=json.loads((w/'module-origins.json').read_text());assert all(x['within_mirror'] for x in orig.values())
for row in orig.values():assert sha(Path(row['path']).read_bytes())==row['sha256']
col=json.loads((w/'collection.json').read_text());tree=ET.parse(w/'results.xml');assert len(col)==len(set(col))==len(tree.findall('.//testcase'))==7
assert not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
scenarios={}
for p in (w/'process-artifacts').rglob('html.stdout'):
 x=json.loads(p.read_text().splitlines()[-1]);scenarios[x['mode']]=x
assert set(scenarios)=={'current-source','missing-source','invalid-observation-time'}
for mode,x in scenarios.items():
 business=[c for c in x['calls'] if c['path'].endswith(('/holds','/confirm'))]
 assert len(business)==(2 if mode=='current-source' else 0)
 assert x['preview']['source']['revision']=='2' and x['preview']['resource_revision']==2 and x['external_resource_availability']=='UNKNOWN'
spec=json.loads((root/'docs/验收规格.json').read_text());bindings=json.loads((root/'docs/F1/ATBindings.json').read_text());assert all(c['whole_status']=='NOT_RUN' for c in bindings['cases'])
result=json.loads((w/'result.json').read_text());out=dict(tested_sha=result['head'],unique_pass=7,new_nodes=4,necessary_compatibility_and_static_nodes=3,nodes=col,pytest_seconds=float(tree.getroot().find('testsuite').get('time')),outer_seconds=result['outer_seconds'],input_count=len(maps[0]),four_maps_equal=True,module_origins=len(orig),all_origins_in_frozen_mirror=True,scenarios=scenarios,whole_AT28='NOT_RUN',all42_whole_status='NOT_RUN',real_browser=False,windows=False,real_external_resource=False,template_risk_window_retried=False,historical_HTTP_timeout='UNKNOWN_OPEN')
p=r/('root-verification-'+sys.argv[1].removeprefix('frozen-')+'.json');p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({k:out[k] for k in ('tested_sha','unique_pass','pytest_seconds','outer_seconds','input_count','module_origins')}))
