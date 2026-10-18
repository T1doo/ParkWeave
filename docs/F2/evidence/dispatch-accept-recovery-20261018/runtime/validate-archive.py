from pathlib import Path
import hashlib,json,struct,zlib,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');dest=root/'docs/F2/evidence/dispatch-accept-recovery-20261018'
manifest=json.loads((dest/'manifest.json').read_text());counts=dict(pairs=0,json=0,jsonl=0,xml=0,png=0,intentional_invalid_json_inputs=0)
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate JSON key '+k)
        d[k]=v
    return d
for record in manifest['records']:
    raw=Path(record['raw_path']).read_bytes();public=dest/record['public_path'];data=public.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==record['raw_sha256'],record['raw_path']
    assert hashlib.sha256(data).hexdigest()==record['public_sha256'],str(public)
    assert len(raw)==record['raw_bytes'] and len(data)==record['public_bytes']
    counts['pairs']+=1
    if record.get('artifact_kind')=='INTENTIONAL_INVALID_OVERSIZE_JSON_INPUT':
        assert record['public_path'] in ['runtime/retained-tmp/'+label+'/test_bounded_files_mode_and_ex0/demo-pack.json' for label in ['final-A','final-v2-A']]
        assert record['origin_test']=='tests/test_local_synthetic_demo.py::test_bounded_files_mode_and_existing_catalog_required[oversize]'
        assert raw==data==b'x'*65537
        assert record['raw_sha256']=='1abe08ebecf1c18cab71f6fe28aaddf20268f85bad78bb9a72f88ca47c874662'
        counts['intentional_invalid_json_inputs']+=1
    elif public.suffix=='.json':json.loads(data,object_pairs_hook=unique);counts['json']+=1
    elif public.suffix=='.jsonl':
        for line in data.splitlines():json.loads(line,object_pairs_hook=unique)
        counts['jsonl']+=1
    elif public.suffix=='.xml':E.fromstring(data);counts['xml']+=1
    elif public.suffix=='.png':
        assert data[:8]==b'\x89PNG\r\n\x1a\n';offset=8;compressed=b'';end=False
        while offset<len(data):
            size=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];body=data[offset+8:offset+8+size];crc=struct.unpack('>I',data[offset+8+size:offset+12+size])[0]
            assert zlib.crc32(kind+body)&0xffffffff==crc
            if kind==b'IDAT':compressed+=body
            offset+=size+12
            if kind==b'IEND':end=True;break
        assert end and offset==len(data);assert zlib.decompress(compressed);counts['png']+=1
focused_xml=[x for x in manifest['records'] if x['public_path']=='runtime/final-focused-pytest.xml']
assert len(focused_xml)==1
record=focused_xml[0]
def nodes(data):return [(c.get('classname'),c.get('name')) for c in E.fromstring(data).findall('.//testcase')]
raw_ids=nodes(Path(record['raw_path']).read_bytes());public_ids=nodes((dest/record['public_path']).read_bytes())
assert raw_ids==public_ids and len(raw_ids)==len(set(raw_ids))==161
result=dict(counts=counts,all_raw_public_hashes_valid=True,structured_artifacts_valid=True,source_sha=manifest['source_sha'],raw_unchanged=True,focused_raw_public_test_identifiers_equal=True,focused_unique_test_identifiers=161)
(dest/'archive-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
