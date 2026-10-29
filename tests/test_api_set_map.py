"""v6 byte boundaries/selection only; no target OS or native trust invented."""
from hashlib import sha256
import copy
import struct

import pytest

from scripts.windows_portable import api_set_map as a
from scripts.windows_portable.payload import PayloadRefused
from scripts.windows_portable.test_payload import pe


def namespace(rows):
    n=len(rows);entries=28;hashes=entries+n*24;values=hashes+n*8
    raw=bytearray(values+sum(len(v) for _,v in rows)*20)
    hashes_to_write=[];value_at=values
    def string(text):
        if not text:return 0,0
        encoded=text.encode('utf-16-le');offset=len(raw);raw.extend(encoded);return offset,len(encoded)
    for i,(name,targets) in enumerate(rows):
        offset,length=string(name)
        struct.pack_into('<6I',raw,entries+i*24,0,offset,length,length,value_at,len(targets))
        # Factor one has an independent simple sum oracle; corrupted hashes
        # and index permutations below must not become a successful lookup.
        hashes_to_write.append((sum(map(ord,name.lower())),i))
        for alias,host in targets:
            alias_offset,alias_length=string(alias);host_offset,host_length=string(host)
            struct.pack_into('<5I',raw,value_at,0,alias_offset,alias_length,host_offset,host_length);value_at+=20
    for i,row in enumerate(sorted(hashes_to_write)):struct.pack_into('<2I',raw,hashes+i*8,*row)
    struct.pack_into('<7I',raw,0,6,len(raw),0,n,entries,hashes,1)
    return bytes(raw)


def test_target_contract_exact_importer_default_absent_and_unmapped_are_distinct():
    raw=namespace([('api-ms-test-l1-1-0',[('', 'default.dll'),('client.exe','special.dll')]),
                   ('ext-ms-test-l1-1-0',[])])
    mapping=a.parse_v6(raw)
    assert a.resolve_metadata(mapping,'api-ms-test-l1-1-0.dll','client.exe')['host']=='special.dll'
    result=a.resolve_metadata(mapping,'api-ms-test-l1-1-0','other.dll')
    assert result['host']=='default.dll' and not result['response_is_native_witness'] and not result['activation_allowed']
    assert a.resolve_metadata(mapping,'ext-ms-test-l1-1-0.dll','client.exe')['status']=='UNMAPPED'
    assert a.resolve_metadata(mapping,'api-ms-absent-l1-1-0','client.exe')['status']=='ABSENT'
    mapping=a.parse_v6(namespace([('api-ms-test-l1-1-0',[('client','other.dll'),('','default.dll')])]))
    assert a.resolve_metadata(mapping,'api-ms-test-l1-1-0','client.exe')['status']=='ALIAS_STYLE_NOT_ACCEPTED'
    mapping=a.parse_v6(namespace([('api-ms-test-l1-1-0',[('client.cp312.pyd','host.dll')])]))
    assert a.resolve_metadata(mapping,'api-ms-test-l1-1-0','client.cp312.pyd')['host']=='host.dll'


def test_offsets_lengths_version_hash_indices_and_duplicate_aliases_refuse():
    raw=namespace([('api-ms-test-l1-1-0',[('','default.dll')]),('ext-ms-test-l1-1-0',[])])
    for offset,value in ((0,7),(4,len(raw)+1),(16,0xffffffff),(20,0xffffffff),(28+8,3)):
        bad=bytearray(raw);struct.pack_into('<I',bad,offset,value)
        with pytest.raises(PayloadRefused):a.parse_v6(bytes(bad))
    hashes=struct.unpack_from('<I',raw,20)[0]
    for offset,value in ((hashes,0),(hashes+4,2),(hashes+8+4,struct.unpack_from('<I',raw,hashes+4)[0])):
        bad=bytearray(raw);struct.pack_into('<I',bad,offset,value)
        with pytest.raises(PayloadRefused):a.parse_v6(bytes(bad))
    with pytest.raises(PayloadRefused):a.parse_v6(namespace([('api-ms-test-l1-1-0',[('','a.dll'),('','b.dll')])]))
    with pytest.raises(PayloadRefused):a.parse_v6(namespace([('api-ms-test-l1-1-0',[('','../a.dll')])]))


def test_same_hash_bound_amd64_apiset_section_required_before_metadata_resolution():
    raw=bytearray(pe());section=0x98+240;raw[section:section+8]=b'.apiset\0'
    data=namespace([('api-ms-test-l1-1-0',[('','host.dll')])]);raw[512:512+len(data)]=data
    image=bytes(raw);mapping=a.extract_image(image,sha256(image).hexdigest())
    assert mapping['machine']=='AMD64' and mapping['namespace_count']==1
    with pytest.raises(PayloadRefused):a.extract_image(image,'0'*64)
    bad=bytearray(raw);struct.pack_into('<H',bad,0x84,0xaa64)
    with pytest.raises(PayloadRefused):a.extract_image(bytes(bad),sha256(bad).hexdigest())
    raw[section:section+8]=b'.other\0\0'
    with pytest.raises(PayloadRefused):a.extract_image(bytes(raw),sha256(raw).hexdigest())


def test_selected_response_cannot_turn_uncollected_or_wrong_hash_into_absence_or_trust():
    value=dict(schema='parkweave-api-set-selected-v6/1',response_is_native_witness=False,
        activation_allowed=False,usable_product=False,hash_index_validated=True,
        file=dict(sha256='a'*64,machine='AMD64',size=4096,identity='NOT_COLLECTED',signature='NOT_COLLECTED'),
        namespace=dict(version=6,size=2048,flags=0,count=100,hash_factor=31),
        requested=['api-ms-test-l1-1-0.dll','ext-ms-test-l1-1-0.dll'],
        entries=[dict(contract='api-ms-test-l1-1-0.dll',flags=0,hashed_length=20,
            values=[dict(flags=0,alias='',host='host.dll')])],missing_contracts=['ext-ms-test-l1-1-0.dll'])
    mapping=a.selected_metadata(value,'a'*64)
    assert a.resolve_metadata(mapping,'api-ms-test-l1-1-0','client.exe')['host']=='host.dll'
    assert a.resolve_metadata(mapping,'ext-ms-test-l1-1-0','client.exe')['status']=='ABSENT'
    assert a.resolve_metadata(mapping,'api-ms-other-l1-1-0','client.exe')['status']=='NOT_COLLECTED'
    assert not mapping['response_is_native_witness'] and not mapping['activation_allowed']
    with pytest.raises(PayloadRefused):a.selected_metadata(value,'b'*64)
    for field in ('response_is_native_witness','activation_allowed','usable_product'):
        bad=copy.deepcopy(value);bad[field]=True
        with pytest.raises(PayloadRefused):a.selected_metadata(bad,'a'*64)
    bad=copy.deepcopy(value);bad['missing_contracts']=[]
    with pytest.raises(PayloadRefused):a.selected_metadata(bad,'a'*64)
    bad=copy.deepcopy(value);bad['entries']*=2
    with pytest.raises(PayloadRefused):a.selected_metadata(bad,'a'*64)
    bad=copy.deepcopy(value);bad['entries'][0]['values'][0]['host']='..\\host.dll'
    with pytest.raises(PayloadRefused):a.selected_metadata(bad,'a'*64)


def test_mapping_builds_exact_host_export_request_without_expanding_system_policy():
    mapping=a.parse_v6(namespace([('api-ms-test-l1-1-0',[('','custom.dll')])]))
    request=dict(schema='parkweave-static-loader-symbols/1',activation_allowed=False,usable_product=False,
        external_imports=[dict(dependency='api-ms-test-l1-1-0.dll',importer_basename='client.cp312.pyd',symbols=['ReadFile','#7'])])
    result=a.apply_requirements(mapping,request)
    assert result['target_hosts']==[dict(name='custom.dll',symbols=['#7','ReadFile'],
        policy='UNDECLARED_HOST_REQUIRES_POLICY_REVIEW')]
    assert result['hash_index_validation']=='VALIDATED_FROM_BYTES' and not result['activation_allowed']
