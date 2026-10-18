from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,sys
root=Path.cwd();r=root/'.runtime/ordinary-template-inputs-20261018';name=sys.argv[1];w=r/name
maps=[json.loads((w/n).read_text()) for n in ['shared-before.json','mirror-before.json','shared-after.json','mirror-after.json']];assert all(x==maps[0] for x in maps)
orig=json.loads((w/'module-origins.json').read_text());assert all(x['within_mirror'] for x in orig.values())
for item in orig.values():assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
collection=json.loads((w/'collection.json').read_text());tree=ET.parse(w/'results.xml');cases=tree.findall('.//testcase');assert len(collection)==len(set(collection))==len(cases)
assert not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
scenarios={}
for p in sorted((w/'process-artifacts').rglob('html.stdout')):
 x=json.loads(p.read_text().splitlines()[-1]);scenarios[x['mode']]=dict(checks=x['checks'],requests=len(x['calls']),posts=[dict(path=c['path'],key=c.get('request_key'),status=c['status']) for c in x['calls'] if c['method']=='POST'],all_calls=x['calls'])
assert set(scenarios)=={'success','lost','edit','token','aba','pin','denied','default'}
result=json.loads((w/'result.json').read_text());report=dict(tested_sha=result['head'],nodes=collection,unique_pass=len(collection),new_slice_nodes=len([x for x in collection if x.startswith('tests/test_ordinary_template_inputs.py')]),old_boundary_compatibility_nodes=6,pytest_seconds=float(tree.getroot().find('testsuite').get('time')),outer_seconds=result['outer_seconds'],input_maps_equal=True,input_count=len(maps[0]),module_origins=len(orig),all_source_modules_from_mirror=True,scenarios=scenarios,metadata_correction=dict(original_result_field='fixture_local_finish_selected=False',correct_scope='False applies to new actual-worker slice only; one selected old fingerprint/journal compatibility node uses original fixture finish and ADOPT. It supplies compatibility evidence, never ordinary formal success or full P1-P5.',original_raw_retained=True),ordinary_formal_success=False,real_browser=False,windows=False,historical_http_timeout='UNKNOWN_OPEN')
for p,h in maps[0].items():
 actual=hashlib.sha256(__import__('subprocess').check_output(['git','show',report['tested_sha']+':'+p],cwd=root)).hexdigest();assert actual==h
(r/('root-verification-'+name.removeprefix('frozen-')+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:report[k] for k in ('tested_sha','unique_pass','input_count','module_origins','outer_seconds','pytest_seconds')}))
