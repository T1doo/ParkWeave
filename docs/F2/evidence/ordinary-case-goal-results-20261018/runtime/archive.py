from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET

root=Path('/workspace/ParkWeave')
raw=root/'.runtime/ordinary-case-goal-results-20261018'
review=raw/'independent'
public=root/'docs/F2/evidence/ordinary-case-goal-results-20261018'
sha=lambda data:hashlib.sha256(data).hexdigest()

# Only known text evidence; never fixture PG data or token registries.
inputs=[]
for p in sorted(raw.iterdir()):
    if p.is_file() and p.suffix in ('.py','.json','.txt','.log') and p.name not in ('archive.stdout','archive.stderr','delivery-and-remote-verification.json'):
        inputs.append((p,Path('runtime')/p.name,None))
for folder in ('development-artifacts','frozen-163e1f79','frozen-8e7e5b6e','frozen-33aef7ab'):
    for p in sorted((raw/folder).rglob('*')):
        if p.is_file() and 'private' not in p.name and p.suffix in ('.json','.jsonl','.xml','.py','.txt','.log','.stdout','.stderr'):
            inputs.append((p,Path('runtime')/p.relative_to(raw),None))
for p in sorted((raw/'development').iterdir()):
    if p.is_file() and p.suffix in ('.log','.xml'):
        inputs.append((p,Path('runtime')/p.relative_to(raw),None))

listed=json.loads((review/'publication-files-v3.json').read_text())
mapping=json.loads((review/'raw-public-redaction-map-v3.json').read_text())
upstream={r['public']:r for r in mapping['files']}
for relative in listed:
    p=review/relative
    assert p.is_file() and p.resolve().is_relative_to(review.resolve()) and 'private' not in p.name
    assert not any(v in ('mirror','data') for v in Path(relative).parts)
    inputs.append((p,Path('independent')/relative,upstream.get(relative)))

assert len(inputs)==len(set(str(rel) for p,rel,row in inputs))
secrets=set()
def collect_tokens(value):
    if isinstance(value,str) and re.fullmatch('[A-Za-z0-9_-]{43}',value):secrets.add(value)
    elif isinstance(value,dict):
        for child in value.values():collect_tokens(child)
    elif isinstance(value,list):
        for child in value:collect_tokens(child)
for folder,pattern in ((raw,'private-synthetic-tokens.json'),(review,'fixture-token-values.private.json')):
    for p in folder.rglob(pattern):
        collect_tokens(json.loads(p.read_text()))
token_pattern=re.compile(r"(?:prep-specialist-fixture-[abc]|fixture-[abc]|executor-[abc]|unassigned)'\s*:\s*'([^']*)'")
fragments=set()
known_fixture_identifiers={'prep-specialist-fixture-'+v for v in 'abc'}|{'ep-specialist-fixture-'+v for v in 'abc'}
for p,rel,row in inputs:
    if row:continue
    for match in token_pattern.finditer(p.read_text()):
        value=match[1]
        if re.fullmatch('[A-Za-z0-9_-]{43}',value):secrets.add(value)
        if '...' in value or len(value)>=16:
            fragments.update(v for v in re.split('[^A-Za-z0-9_-]+',value) if len(v)>=16 and not v.startswith('SYNTHETIC_') and v not in known_fixture_identifiers)

def redact(data):
    value=data.decode();count=0
    for secret in sorted(secrets,key=len,reverse=True):
        count+=value.count(secret);value=value.replace(secret,'SYNTHETIC_SESSION_REDACTED')
    spans={(m.start(1),m.end(1)) for m in token_pattern.finditer(value) if not m[1].startswith('SYNTHETIC_') and ('...' in m[1] or re.fullmatch('[A-Za-z0-9_-]{30,}',m[1]))}
    for start,end in sorted(spans,reverse=True):
        value=value[:start]+'SYNTHETIC_SESSION_REDACTED'+value[end:];count+=1
    return value.encode(),count

public.mkdir(exist_ok=False)
pairs=[]
for prepared,relative,upstream_row in inputs:
    original=prepared;data=prepared.read_bytes()
    if upstream_row:
        original=review/upstream_row['raw'];original_data=original.read_bytes()
        assert sha(original_data)==upstream_row['raw_sha256'] and sha(data)==upstream_row['public_sha256']
        result=data;count=upstream_row['replacement_count'];data=original_data
    else:result,count=redact(data)
    target=public/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    pairs.append(dict(raw=str(original.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(data),
        public_sha256=sha(result),public_bytes=len(result),replacement_count=count,canonical_upstream=bool(upstream_row)))

parsed_xml=[]
for row in pairs:
    p=root/row['public'];data=p.read_bytes()
    assert sha((root/row['raw']).read_bytes())==row['raw_sha256'] and sha(data)==row['public_sha256']
    if p.suffix=='.json':json.loads(data)
    elif p.suffix=='.jsonl':
        for line in data.decode().splitlines():json.loads(line)
    elif p.suffix=='.xml':
        original=ET.parse(root/row['raw']);shadow=ET.fromstring(data)
        cases=lambda x:[(v.get('classname'),v.get('name'),len(v.findall('failure')),len(v.findall('error')),len(v.findall('skipped'))) for v in x.findall('.//testcase')]
        assert cases(original)==cases(shadow);parsed_xml.append(dict(path=row['public'],cases=len(cases(shadow))))
    assert not any(secret.encode() in data or secret[:16].encode() in data for secret in secrets)
    assert not any(fragment.encode() in data for fragment in fragments)

manifest=dict(files=pairs,known_owned_synthetic_tokens=len(secrets),xml_case_outcomes_preserved=parsed_xml)
(public/'raw-public-redaction-map.json').write_text(json.dumps(manifest,indent=2)+'\n')
names=[str(p.relative_to(public)) for p in sorted(public.rglob('*')) if p.is_file()]
(public/'publication-files.json').write_text(json.dumps(names,indent=2)+'\n')
verification=dict(pairs=len(pairs),unchanged=sum(r['raw_sha256']==r['public_sha256'] for r in pairs),
    redacted=sum(r['raw_sha256']!=r['public_sha256'] for r in pairs),replacements=sum(r['replacement_count'] for r in pairs),
    all_pairs_hash_match=True,all_structured_files_parsed=True,all_xml_outcomes_preserved=True,
    known_owned_synthetic_tokens=len(secrets),full_and_16_prefix_scan_hits=0,fragment_scan_hits=0,
    archive_files_before_three_controls=len(pairs),total_public_files=len(pairs)+3)
(public/'archive-validation.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification))
