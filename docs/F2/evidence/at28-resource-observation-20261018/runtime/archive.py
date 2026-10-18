from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET
root=Path.cwd();raw=root/'.runtime/at28-resource-observation-20261018';review=raw/'independent';public=root/'docs/F2/evidence/at28-resource-observation-20261018'
sha=lambda b:hashlib.sha256(b).hexdigest()
inputs=[]
for p in sorted(raw.iterdir()):
    if p.is_file() and 'private' not in p.name and p.suffix in ('.py','.json','.txt','.log','.stdout','.stderr','.xml') and p.name not in ('archive.stdout','archive.stderr','delivery-and-remote-verification.json','status-for-parent.json'):
        inputs.append((p,Path('runtime')/p.name,None))
for folder in ['development-artifacts','frozen-555edeac']:
    for p in sorted((raw/folder).rglob('*')):
        if p.is_file() and 'private' not in p.name and p.suffix in ('.json','.jsonl','.xml','.py','.patch','.txt','.log','.stdout','.stderr'):
            inputs.append((p,Path('runtime')/p.relative_to(raw),None))
# Historical first green window remains a separate SHA; full private inputs stay retained.
for name in ['result.json','collection.json','calls.jsonl','results.xml','stdout.txt','stderr.txt']:
    p=raw/'frozen-b379a61f'/name
    inputs.append((p,Path('runtime/frozen-b379a61f')/name,None))
listed=json.loads((review/sys.argv[1]).read_text());mapping=json.loads((review/sys.argv[2]).read_text());upstream={r['public']:r for r in mapping['entries']}
for relative in listed:
    p=review/relative
    assert p.is_file() and p.resolve().is_relative_to(review.resolve()) and 'private' not in p.name
    assert not any(v in ('mirror','data') for v in Path(relative).parts)
    inputs.append((p,Path('independent')/relative,upstream.get(relative)))
assert len(inputs)==len(set(str(rel) for p,rel,row in inputs))
secrets=set();fragments=set()
def collect(v):
    if isinstance(v,str) and re.fullmatch('[A-Za-z0-9_-]{43}',v):secrets.add(v)
    elif isinstance(v,dict):
        for x in v.values():collect(x)
    elif isinstance(v,list):
        for x in v:collect(x)
for pattern in ('*tokens*.private.json','*token*values*.json','private-synthetic-tokens.json','private-development-tokens.json'):
    for p in raw.rglob(pattern):
        if p.is_file():collect(json.loads(p.read_text()))
# The uninstrumented development failure repr retained two clipped session tails.
# Bind exactly those visible tails, redact them everywhere, keep raw files private.
fragment_pattern=re.compile(r"(?<=\.\.\.)[A-Za-z0-9_-]{12,64}(?=')")
for p,rel,up in inputs:
    if up:continue
    for m in fragment_pattern.finditer(p.read_text()):fragments.add(m.group())

def redact(data,path):
    value=data.decode();count=0
    # A truncated pytest fixture tuple can expose only part of one session dict.
    # Scrub that dictionary only in the known two development failure originals.
    if path.name in ('development.stdout','development-results.xml'):
        value,n=re.subn(r"\{'fixture-a': [^}\n]*\}","{'synthetic_sessions': 'SYNTHETIC_SESSION_VALUES_REDACTED'}",value);count+=n
    for secret in sorted(secrets|fragments,key=len,reverse=True):
        count+=value.count(secret);value=value.replace(secret,'SYNTHETIC_SESSION_REDACTED')
    return value.encode(),count
public.mkdir(exist_ok=False);pairs=[]
for prepared,relative,up in inputs:
    original=prepared;data=prepared.read_bytes()
    if up:
        original=review/up['raw'];original_data=original.read_bytes();assert sha(original_data)==up['raw_sha256'] and sha(data)==up['public_sha256'];result=data;count=up['replacement_count'];data=original_data
    elif relative.parts[0]=='independent':result,count=data,0
    else:result,count=redact(data,prepared)
    target=public/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    pairs.append(dict(raw=str(original.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(data),public_sha256=sha(result),public_bytes=len(result),replacement_count=count,canonical_upstream=relative.parts[0]=='independent'))
xmls=[]
for row in pairs:
    p=root/row['public'];data=p.read_bytes();assert sha((root/row['raw']).read_bytes())==row['raw_sha256'] and sha(data)==row['public_sha256']
    if p.suffix=='.json':json.loads(data)
    elif p.suffix=='.jsonl':
        for line in data.decode().splitlines():json.loads(line)
    elif p.suffix=='.xml':
        original=ET.parse(root/row['raw']);shadow=ET.fromstring(data)
        cases=lambda x:[(v.get('classname'),v.get('name'),len(v.findall('failure')),len(v.findall('error')),len(v.findall('skipped'))) for v in x.findall('.//testcase')]
        assert cases(original)==cases(shadow);xmls.append(dict(path=row['public'],cases=len(cases(shadow))))
    assert not any(s.encode() in data or s[:16].encode() in data for s in secrets)
    assert not any(s.encode() in data for s in fragments)
manifest=dict(files=pairs,known_owned_synthetic_tokens=len(secrets),development_repr_fragments=len(fragments),xml_case_outcomes_preserved=xmls)
(public/'raw-public-redaction-map.json').write_text(json.dumps(manifest,indent=2)+'\n')
verification=dict(pairs=len(pairs),unchanged=sum(r['raw_sha256']==r['public_sha256'] for r in pairs),redacted=sum(r['raw_sha256']!=r['public_sha256'] for r in pairs),replacements=sum(r['replacement_count'] for r in pairs),all_pairs_hash_match=True,all_structured_files_parsed=True,all_xml_outcomes_preserved=True,known_owned_synthetic_tokens=len(secrets),development_repr_fragments=len(fragments),registered_full_and_16_prefix_scan_hits=0,fragment_scan_hits=0,total_public_files=len(pairs)+3,raw_configuration_and_token_inputs_kept_private=True)
(public/'archive-validation.json').write_text(json.dumps(verification,indent=2)+'\n')
names=sorted([str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()]+['publication-files.json']);(public/'publication-files.json').write_text(json.dumps(names,indent=2)+'\n');assert names==sorted(str(p.relative_to(public)) for p in public.rglob('*') if p.is_file());print(json.dumps(verification))
