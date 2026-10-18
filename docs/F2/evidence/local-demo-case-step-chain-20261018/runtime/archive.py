from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET

root=Path.cwd();raw=root/'.runtime/local-demo-case-step-chain-20261018'
public=root/'docs/F2/evidence/local-demo-case-step-chain-20261018'
sha=lambda b:hashlib.sha256(b).hexdigest()
allowed={'.py','.json','.jsonl','.xml','.txt','.log','.stdout','.stderr','.md','.diff'}
excluded={'executor-recovery-audit.json','archive.stdout','archive.stderr','delivery-and-remote-verification.json'}
inputs=[]
for p in sorted(raw.iterdir()):
    if p.is_file() and p.suffix in allowed and 'private' not in p.name and p.name not in excluded:
        inputs.append((p,Path('runtime')/p.name,False))
for name in ['development-artifacts','development2-artifacts','frozen-3f5fd029']:
    for p in sorted((raw/name).rglob('*')):
        if p.is_file() and p.suffix in allowed and 'private' not in p.name:
            inputs.append((p,Path('runtime')/p.relative_to(raw),False))
# Retain earlier green SHA as history, not final verification.
for name in ['result.json','collection.json','calls.jsonl','results.xml','stdout.txt','stderr.txt']:
    p=raw/'frozen-3b559f93'/name;inputs.append((p,Path('runtime')/p.relative_to(raw),False))
review=raw/'independent'
for p in sorted(review.rglob('*')):
    relative=p.relative_to(review)
    if p.is_file() and p.suffix in allowed and 'private' not in p.name and not any(x in ('mirror','data','__pycache__') for x in relative.parts):
        inputs.append((p,Path('independent')/relative,True))
assert len(inputs)==len({str(r) for _,r,_ in inputs})
secrets=set()
for p in raw.rglob('*tokens*.json'):
    if not p.is_file():continue
    values=json.loads(p.read_text())
    def collect(value):
        if isinstance(value,str) and re.fullmatch('[A-Za-z0-9_-]{43}',value):secrets.add(value)
        elif isinstance(value,list):
            for item in value:collect(item)
        elif isinstance(value,dict):
            for item in value.values():collect(item)
    collect(values)
public.mkdir(exist_ok=False);pairs=[];xmls=[]
for source,relative,independent in inputs:
    original=source.read_bytes();text=original.decode();replacements=0
    if not independent:
        # Pytest abbreviates fixture arguments and can retain a clipped session.
        text,n=re.subn(r"(?m)^demo_inputs = .*\{'fixture-a':.*$",'demo_inputs = <private synthetic fixture arguments redacted>',text);replacements+=n
        for secret in sorted(secrets,key=len,reverse=True):
            replacements+=text.count(secret);text=text.replace(secret,'SYNTHETIC_SESSION_REDACTED')
    data=text.encode();target=public/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    assert not any(s in text or s[:16] in text for s in secrets)
    if source.suffix=='.json':json.loads(data)
    elif source.suffix=='.jsonl':
        for line in text.splitlines():json.loads(line)
    elif source.suffix=='.xml':
        before=ET.fromstring(original);after=ET.fromstring(data)
        cases=lambda tree:[(c.get('classname'),c.get('name'),len(c.findall('failure')),len(c.findall('error')),len(c.findall('skipped'))) for c in tree.findall('.//testcase')]
        assert cases(before)==cases(after);xmls.append(dict(path=str(target.relative_to(root)),testcases=len(cases(after))))
    if independent:assert original==data
    pairs.append(dict(raw=str(source.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(original),public_sha256=sha(data),public_bytes=len(data),replacement_count=replacements,independent_canonical=independent))
for pair in pairs:
    assert sha((root/pair['raw']).read_bytes())==pair['raw_sha256']
    assert sha((root/pair['public']).read_bytes())==pair['public_sha256']
manifest=dict(files=pairs,known_owned_synthetic_tokens=len(secrets),xml_case_outcomes_preserved=xmls)
(public/'raw-public-redaction-map.json').write_text(json.dumps(manifest,indent=2)+'\n')
verification=dict(pairs=len(pairs),unchanged=sum(p['raw_sha256']==p['public_sha256'] for p in pairs),redacted=sum(p['raw_sha256']!=p['public_sha256'] for p in pairs),replacements=sum(p['replacement_count'] for p in pairs),independent_canonical_files=sum(p['independent_canonical'] for p in pairs),all_pairs_hash_match=True,all_structured_files_parse=True,all_xml_outcomes_preserved=True,known_owned_synthetic_tokens=len(secrets),registered_full_and_16_prefix_scan_hits=0,total_public_files=len(pairs)+3,raw_sessions_and_credentials_not_published=True,synthetic_demo_input_json_included=True)
(public/'archive-validation.json').write_text(json.dumps(verification,indent=2)+'\n')
files=sorted([str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()]+['publication-files.json'])
(public/'publication-files.json').write_text(json.dumps(files,indent=2)+'\n')
assert files==sorted(str(p.relative_to(public)) for p in public.rglob('*') if p.is_file())
print(json.dumps(verification))
