from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET

root=Path('/workspace/ParkWeave');raw=root/'.runtime/fixed-acceptance-closeout-20261018'
public=root/'docs/F2/evidence/fixed-acceptance-closeout-20261018'
sha=lambda b:hashlib.sha256(b).hexdigest()
allowed={'.py','.json','.jsonl','.xml','.txt','.log','.stdout','.stderr','.md','.diff'}
exclude={'archive.stdout','archive.stderr','delivery-and-remote-verification.json'}
inputs=[]
for p in sorted(raw.iterdir()):
    if p.is_file() and p.suffix in allowed and 'private' not in p.name and p.name not in exclude:
        inputs.append((p,Path('runtime')/p.name,False))
for folder in ['frozen-7f02fe3f','supplement-7f02fe3f','frozen-7f02fe3f-preparation-failure1','frozen-7f02fe3f-preparation-failure2','frozen-7f02fe3f-preparation-failure3']:
    for p in sorted((raw/folder).rglob('*')):
        if p.is_file() and p.suffix in allowed and 'private' not in p.name:
            inputs.append((p,Path('runtime')/p.relative_to(raw),False))
review=raw/'independent';listed=json.loads((review/'publication-files.json').read_text())
for name in sorted(set(listed)|{'publication-files.json','commentary-review.json'}):
    p=review/name;assert p.is_file() and p.resolve().is_relative_to(review.resolve())
    inputs.append((p,Path('independent')/name,True))
assert len(inputs)==len({str(relative) for _,relative,_ in inputs})
public.mkdir(exist_ok=False);pairs=[];xmls=[]
for source,relative,independent in inputs:
    data=source.read_bytes();target=public/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if source.suffix=='.json':json.loads(data)
    elif source.suffix=='.jsonl':
        for line in data.decode().splitlines():json.loads(line)
    elif source.suffix=='.xml':
        tree=ET.fromstring(data);cases=tree.findall('.//testcase')
        xmls.append(dict(path=str(target.relative_to(root)),testcases=len(cases),failures=sum(c.find('failure') is not None for c in cases),errors=sum(c.find('error') is not None for c in cases)))
    pairs.append(dict(raw=str(source.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(data),public_sha256=sha(data),public_bytes=len(data),replacement_count=0,independent_canonical=independent))
for row in pairs:
    assert sha((root/row['raw']).read_bytes())==row['raw_sha256']
    assert sha((root/row['public']).read_bytes())==row['public_sha256']
manifest=dict(files=pairs,xml_outcomes_preserved=xmls,actual_session_values_collected=False)
(public/'raw-public-redaction-map.json').write_text(json.dumps(manifest,indent=2)+'\n')
validation=dict(pairs=len(pairs),unchanged=len(pairs),redacted=0,replacements=0,independent_canonical_files=sum(row['independent_canonical'] for row in pairs),all_pairs_hash_match=True,all_structured_files_parsed=True,all_xml_outcomes_preserved=True,actual_session_values_collected=False,not_a_known_session_value_scan=True,raw_sessions_credentials_PGdata_not_included=True,total_public_files=len(pairs)+3)
(public/'archive-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
files=sorted([str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()]+['publication-files.json'])
(public/'publication-files.json').write_text(json.dumps(files,indent=2)+'\n');assert files==sorted(str(p.relative_to(public)) for p in public.rglob('*') if p.is_file())
print(json.dumps(validation))
