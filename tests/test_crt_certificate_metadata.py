"""Synthetic DER/PE bytes and borrowed memory: no native/certificate acceptance."""
import ctypes as C
import json
import struct
import pytest
from scripts.windows_ci import crt_certificate_metadata as metadata


def tlv(tag,value):
    length=len(value)
    size=bytes([length]) if length<128 else bytes([128+(length.bit_length()+7)//8])+length.to_bytes((length.bit_length()+7)//8,'big')
    return bytes([tag])+size+value

def sequence(*values):return tlv(48,b''.join(values))
def oid(value):
    parts=[int(x) for x in value.split('.')];out=[]
    for v in [parts[0]*40+parts[1],*parts[2:]]:
        row=[v&127];v>>=7
        while v:row.append((v&127)|128);v>>=7
        out.extend(reversed(row))
    return tlv(6,bytes(out))
def name(value):return sequence(tlv(49,sequence(oid('2.5.4.3'),tlv(12,value.encode()))))
def ext(key,value):return sequence(oid(key),tlv(4,value))
ALG=sequence(oid('1.2.840.113549.1.1.11'),tlv(5,b''))
ISSUER=name('Synthetic public CA');SERIAL=tlv(2,b'\x01\x23')


def certificate():
    point=sequence(tlv(160,tlv(160,tlv(134,b'http://example.invalid/leaf.crl'))))
    extensions=sequence(
        ext('2.5.29.31',sequence(point)),
        ext('1.3.6.1.5.5.7.1.1',sequence(
            sequence(oid('1.3.6.1.5.5.7.48.1'),tlv(134,b'http://example.invalid/ocsp')),
            sequence(oid('1.3.6.1.5.5.7.48.2'),tlv(134,b'http://example.invalid/issuer.crt')))),
        ext('2.5.29.14',tlv(4,b'\x11'*20)),ext('2.5.29.35',sequence(tlv(128,b'\x22'*20))))
    tbs=sequence(tlv(160,tlv(2,b'\x02')),SERIAL,ALG,ISSUER,
        sequence(tlv(23,b'491231235959Z'),tlv(24,b'20510101000000Z')),
        name('Synthetic public signer'),sequence(ALG,tlv(3,b'\0\x01')),tlv(163,extensions))
    return sequence(tbs,ALG,tlv(3,b'\0\x01'))


def attr(key,*values):return sequence(oid(key),tlv(49,b''.join(values)))
def cms(content,signer):
    return sequence(oid('1.2.840.113549.1.7.2'),tlv(160,sequence(tlv(2,b'\x01'),tlv(49,ALG),content,tlv(49,signer))))
def signer(auth=b'',unauth=b''):
    return sequence(tlv(2,b'\x01'),sequence(ISSUER,SERIAL),ALG,*([tlv(160,auth)] if auth else []),ALG,tlv(4,b'not-a-real-signature'),*([tlv(161,unauth)] if unauth else []))
def pe(blob):
    image=bytearray(512);image[:2]=b'MZ';struct.pack_into('<I',image,60,64);image[64:68]=b'PE\0\0'
    struct.pack_into('<H',image,84,240);struct.pack_into('<H',image,88,0x20b)
    struct.pack_into('<I',image,88+108,16)
    cert=struct.pack('<IHH',len(blob)+8,0x200,2)+blob;cert+=b'\0'*((-len(cert))%8)
    struct.pack_into('<II',image,88+112+32,512,len(cert));return bytes(image)+cert


def test_public_certificate_identity_issuer_validity_cdp_ocsp_and_key_binding():
    data=metadata.certificate(certificate())
    assert data['status']=='PUBLIC_CERTIFICATE_METADATA_NOT_ACCEPTANCE'
    assert data['serial_hex']=='0123' and data['issuer']==[dict(oid='2.5.4.3',value='Synthetic public CA')]
    assert data['not_before_utc']=='2049-12-31T23:59:59Z' and data['not_after_utc']=='2051-01-01T00:00:00Z'
    assert data['crl_distribution_points']==['http://example.invalid/leaf.crl']
    assert [x['method_oid'] for x in data['authority_information_access']]==['1.3.6.1.5.5.7.48.1','1.3.6.1.5.5.7.48.2']
    assert data['authority_key_identifier']=='22'*20 and data['subject_key_identifier']=='11'*20
    assert len(data['sha256'])==len(data['spki_der_sha256'])==64
    assert 'not-a-real-signature' not in json.dumps(data)


def test_embedded_signing_and_rfc3161_times_bound_to_same_public_signer_identity():
    info=sequence(tlv(2,b'\x01'),oid('1.2.3.4'),sequence(ALG,tlv(4,b'\x00'*32)),tlv(2,b'\x01'),tlv(24,b'20260527021429.22Z'))
    token=cms(sequence(oid('1.2.840.113549.1.9.16.1.4'),tlv(160,tlv(4,info))),signer())
    outer=cms(sequence(oid('1.3.6.1.4.1.311.2.1.4')),signer(
        attr('1.2.840.113549.1.9.5',tlv(23,b'260527021400Z')),
        attr('1.3.6.1.4.1.311.3.3.1',token)))
    result=metadata.pe_signing_times(pe(outer));row=result['records'][0]['signers'][0]
    assert row['signing_time_utc']==['2026-05-27T02:14:00Z']
    assert row['timestamp_tokens'][0]['gen_time_utc']=='2026-05-27T02:14:29.220000Z'
    assert row['timestamp_tokens'][0]['validation']=='NOT_PERFORMED'
    cert=metadata.certificate(certificate());assert row['signer_identity']['issuer_name_der_sha256']==cert['issuer_name_der_sha256']
    assert row['signer_identity']['serial_hex']==cert['serial_hex']
    assert result['timestamp_validation']=='NOT_PERFORMED'


@pytest.mark.parametrize('data',[b'',b'\x30\x80\0\0',b'\x30\x81\x01\0',b'\x30\x82\0\x80'+b'\0'*128,
    b'\x1f\x01\0',b'\x30\x03\x06\x02\x80',certificate()+b'junk',b'\0'*65537])
def test_bad_or_unbounded_der_is_refused_without_argument_leak(data):
    result=metadata.observe_certificate(data)
    assert result==dict(status='UNAVAILABLE_PUBLIC_CERTIFICATE_FORMAT_OR_BUDGET')


def test_deep_der_invalid_time_url_and_fixed_budget_refuse():
    data=b''
    for _ in range(52):data=sequence(data)
    with pytest.raises(ValueError):metadata.DER().root(data)
    with pytest.raises(ValueError):metadata.utc(metadata.DER().root(tlv(23,b'260231010000Z')))
    with pytest.raises(ValueError):metadata.uris(metadata.DER().root(tlv(134,b'http://example.invalid/\rPRIVATE')))
    def expired():raise RuntimeError('PRIVATE_CONTEXT')
    result=metadata.observe_certificate(certificate(),expired)
    assert result==dict(status='UNAVAILABLE_PUBLIC_CERTIFICATE_FORMAT_OR_BUDGET')
    assert 'PRIVATE_CONTEXT' not in json.dumps(result)


def test_pe_table_bounds_no_implicit_fallback_and_legacy_counter_time():
    counter=signer(attr('1.2.840.113549.1.9.5',tlv(23,b'260527021500Z')))
    result=metadata.pe_signing_times(pe(cms(sequence(oid('1.2.3')),signer(unauth=attr('1.2.840.113549.1.9.6',counter)))))
    assert result['records'][0]['signers'][0]['legacy_counter_signers'][0]['signing_time_utc']==['2026-05-27T02:15:00Z']
    for broken in (b'x',pe(b'bad'),pe(cms(sequence(oid('1.2.3')),signer()))[:-1]):
        assert metadata.observe_pe_signing_times(broken)['status']=='UNAVAILABLE_EMBEDDED_TIME_FORMAT_OR_BUDGET'


def test_metadata_copied_from_original_context_survives_close_without_native_calls():
    from tests.test_crt_state_snapshot import graph,capture
    g=graph();raw=certificate();buffers=[C.create_string_buffer(raw) for _ in range(2)]
    for context,buffer in zip(g.contexts,buffers):context.der=C.addressof(buffer);context.length=len(raw)
    result=capture(g)['signer_chain'];assert result['verify_as_of_utc'].startswith('1601-01-01')
    assert [x['public_metadata']['sha256'] for x in result['certificates']]==[metadata.certificate(raw)['sha256']]*2
    g.reader.deactivate();buffers[0][0]=b'x'
    assert g.reader.export()['signer_chain']==result


def test_nested_and_unknown_attributes_are_visible_and_identity_is_explicit_not_timestamp_trust():
    nested=cms(sequence(oid('1.2.3')),signer(attr('1.2.840.113549.1.9.5',tlv(23,b'260527021700Z'))))
    outer=cms(sequence(oid('1.2.3')),signer(unauth=attr('1.3.6.1.4.1.311.2.4.1',nested)+attr('1.2.3.999',tlv(4,b'PRIVATE_UNINTERPRETED_VALUE'))))
    result=metadata.pe_signing_times(pe(outer));row=result['records'][0]['signers'][0]
    assert row['nested_signatures'][0]['signing_time_utc']==['2026-05-27T02:17:00Z']
    assert row['uninterpreted_attributes']==[dict(kind='UNSIGNED',oid='1.2.3.999',value_count=1)]
    assert 'PRIVATE_UNINTERPRETED_VALUE' not in json.dumps(result)
    match=metadata.provider_signer_matches(result,metadata.certificate(certificate()))
    assert match['matches']==['record[0].signer[0]','record[0].signer[0].nested[0]']
    assert match['timestamp_validation']=='NOT_PERFORMED' and result['coverage']=='PUBLIC_TIME_FIELDS_NOT_EXHAUSTIVE'
    wrong=metadata.certificate(certificate());wrong['serial_hex']='05'
    assert metadata.provider_signer_matches(result,wrong)['matches']==[]
    assert metadata.provider_signer_matches(result,{})['status']=='NOT_AVAILABLE'
