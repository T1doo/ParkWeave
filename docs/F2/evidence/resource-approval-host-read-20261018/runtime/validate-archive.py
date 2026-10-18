from pathlib import Path
import hashlib,json,struct,zlib,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');dest=root/'docs/F2/evidence/resource-approval-host-read-20261018';manifest=json.loads((dest/'manifest.json').read_text());counts=dict(pairs=0,json=0,jsonl=0,xml=0,png=0,intentional_invalid_inputs=0)
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate key '+k)
  d[k]=v
 return d
def ids(raw):return [c.get('classname').replace('.','/')+'.py::'+c.get('name') for c in E.fromstring(raw).findall('.//testcase')]
seen=set()
for record in manifest['records']:
 raw=Path(record['raw_path']).read_bytes();public=dest/record['public_path'];data=public.read_bytes();assert record['public_path'] not in seen;seen.add(record['public_path'])
 assert hashlib.sha256(raw).hexdigest()==record['raw_sha256'] and hashlib.sha256(data).hexdigest()==record['public_sha256'];assert len(raw)==record['raw_bytes'] and len(data)==record['public_bytes'];counts['pairs']+=1
 assert 'fixture-private' not in record['public_path']
 if record.get('artifact_kind')=='INTENTIONAL_DUPLICATE_KEY_SOURCE_INPUT':
  assert record['public_path']=='runtime/retained-tmp/final/test_unverified_missing_or_wro1/SYNTHETIC-existing-approval.json'
  assert record['origin_test']=='tests/test_resource_plan_approval_read.py::test_unverified_missing_or_wrong_contract_source_never_approves[duplicate-key]'
  assert raw==data and data.count(b'"state":')==2
  try:json.loads(data,object_pairs_hook=unique)
  except ValueError as exc:assert str(exc)=='duplicate key state'
  else:raise AssertionError('intentional duplicate source no longer duplicates')
  counts['intentional_invalid_inputs']+=1
 elif public.suffix=='.json':json.loads(data,object_pairs_hook=unique);counts['json']+=1
 elif public.suffix=='.jsonl':
  for line in data.splitlines():json.loads(line,object_pairs_hook=unique)
  counts['jsonl']+=1
 elif public.suffix=='.xml':
  E.fromstring(data);assert ids(raw)==ids(data);counts['xml']+=1
 elif public.suffix=='.png':
  assert data[:8]==b'\x89PNG\r\n\x1a\n';offset=8;compressed=b'';end=False
  while offset<len(data):
   size=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];body=data[offset+8:offset+8+size];crc=struct.unpack('>I',data[offset+8+size:offset+12+size])[0];assert zlib.crc32(kind+body)&0xffffffff==crc
   if kind==b'IDAT':compressed+=body
   offset+=size+12
   if kind==b'IEND':end=True;break
  assert end and offset==len(data) and zlib.decompress(compressed);counts['png']+=1
final_record=next(x for x in manifest['records'] if x['public_path']=='runtime/final.xml');nodes=ids((dest/final_record['public_path']).read_bytes());assert len(nodes)==len(set(nodes))==190
assert counts['intentional_invalid_inputs']==1
result=dict(source_sha=manifest['source_sha'],counts=counts,all_raw_public_hashes_valid=True,all_structured_outputs_valid=True,raw_unchanged=True,all_xml_test_identifiers_unchanged=True,final_unique=190,limits='One exact intentional duplicate-key source INPUT is preserved and classified; not called valid structured output. Private synthetic key bootstrap and PG data not exported.')
(dest/'archive-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
