"""Bounded public X.509 DER fields, parsed in memory; no crypto/native/network I/O.

Observations do not validate a signature, issuer, CRL, OCSP response or timestamp.
Only existing System32 CRT provider certificates reach the CI caller. Raw DER,
private keys, account names and machine paths are never exported.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import re


@dataclass(frozen=True)
class Node:
    tag: int
    raw: bytes
    value: bytes
    children: tuple


class DER:
    def __init__(self,guard=lambda:None):self.remaining=4096;self.guard=guard
    def one(self,data,depth=0):
        self.guard();self.remaining-=1
        if self.remaining<0 or depth>48 or not 2<=len(data)<=65536:raise ValueError('PUBLIC_DER_BOUNDS')
        tag=data[0];n=data[1];start=2
        if tag&31==31:raise ValueError('PUBLIC_DER_TAG')
        if n&128:
            count=n&127
            if not 1<=count<=3 or len(data)<2+count or data[2]==0:raise ValueError('PUBLIC_DER_LENGTH')
            n=int.from_bytes(data[2:2+count],'big');start+=count
            if n<128:raise ValueError('PUBLIC_DER_LENGTH')
        end=start+n
        if end>len(data):raise ValueError('PUBLIC_DER_TRUNCATED')
        value=data[start:end];children=[];rest=value
        if tag&32:
            while rest:
                child,rest=self.one(rest,depth+1);children.append(child)
        return Node(tag,data[:end],value,tuple(children)),data[end:]
    def root(self,data):
        node,rest=self.one(data)
        if rest:raise ValueError('PUBLIC_DER_TRAILING')
        return node


def need(ok):
    if not ok:raise ValueError('PUBLIC_CERTIFICATE_FORMAT')


def oid(node):
    need(node.tag==6 and 0<len(node.value)<=128)
    values=[];v=0;first=True
    for b in node.value:
        need(not(first and b==128));v=(v<<7)|(b&127);need(v<2**63)
        if b<128:values.append(v);v=0;first=True
        else:first=False
    need(first and values)
    leading=values.pop(0);a=min(leading//40,2)
    return '.'.join(map(str,[a,leading-40*a,*values]))


def utc(node):
    need(node.tag in (23,24));text=node.value.decode('ascii')
    if node.tag==23:
        need(re.fullmatch(r'\d{12}Z',text) is not None)
        year=int(text[:2]);text=str(year+(1900 if year>=50 else 2000))+text[2:]
    need(re.fullmatch(r'\d{14}(?:\.\d{1,6})?Z',text) is not None)
    fraction=text[15:-1] if '.' in text else ''
    value=datetime(int(text[:4]),int(text[4:6]),int(text[6:8]),int(text[8:10]),int(text[10:12]),
        int(text[12:14]),int(fraction.ljust(6,'0')) if fraction else 0,tzinfo=timezone.utc)
    return value.isoformat().replace('+00:00','Z')


def filetime_utc(value):
    if value is None:return None
    need(type(value) is int and 0<value<2**64)
    return (datetime(1601,1,1,tzinfo=timezone.utc)+timedelta(microseconds=value//10)).isoformat().replace('+00:00','Z')


def name(node):
    need(node.tag==48 and len(node.children)<=32);attrs=[]
    for rdn in node.children:
        need(rdn.tag==49 and 0<len(rdn.children)<=8)
        for pair in rdn.children:
            need(pair.tag==48 and len(pair.children)==2)
            key,value=pair.children;label=oid(key);need(len(value.value)<=512)
            enc={12:'utf-8',19:'ascii',20:'latin1',22:'ascii',30:'utf-16-be'}.get(value.tag)
            need(enc is not None);text=value.value.decode(enc)
            need(all(ord(c)>=32 and ord(c)!=127 for c in text))
            attrs.append(dict(oid=label,value=text))
    return attrs


def uris(node):
    result=[]
    if node.tag==134:
        value=node.value.decode('ascii');need(0<len(value)<=2048 and all(32<ord(c)<127 for c in value))
        result.append(value)
    for child in node.children:result.extend(uris(child))
    need(len(result)<=32)
    return result


def certificate(data,guard=lambda:None):
    parser=DER(guard);cert=parser.root(data)
    need(cert.tag==48 and len(cert.children)==3)
    tbs,algorithm,signature=cert.children;need(tbs.tag==48 and algorithm.tag==48 and signature.tag==3)
    fields=tbs.children;offset=1 if fields and fields[0].tag==160 else 0
    need(len(fields)>=offset+6)
    serial,inner_algorithm,issuer,validity,subject,spki=fields[offset:offset+6]
    need(serial.tag==2 and 0<len(serial.value)<=32 and not serial.value[0]&128)
    need(validity.tag==48 and len(validity.children)==2 and spki.tag==48 and algorithm.children)
    result=dict(status='PUBLIC_CERTIFICATE_METADATA_NOT_ACCEPTANCE',sha256=sha256(data).hexdigest(),
        serial_hex=serial.value.hex(),signature_algorithm_oid=oid(algorithm.children[0]),
        issuer=name(issuer),issuer_name_der_sha256=sha256(issuer.raw).hexdigest(),
        subject=name(subject),subject_name_der_sha256=sha256(subject.raw).hexdigest(),
        spki_der_sha256=sha256(spki.raw).hexdigest(),not_before_utc=utc(validity.children[0]),not_after_utc=utc(validity.children[1]),
        subject_key_identifier=None,authority_key_identifier=None,crl_distribution_points=[],authority_information_access=[])
    seen=set()
    for extra in fields[offset+6:]:
        if extra.tag!=163:continue
        need(len(extra.children)==1 and extra.children[0].tag==48)
        for extension in extra.children[0].children:
            need(extension.tag==48 and len(extension.children) in (2,3))
            key=oid(extension.children[0]);need(key not in seen);seen.add(key)
            blob=extension.children[-1];need(blob.tag==4)
            if key not in ('2.5.29.31','1.3.6.1.5.5.7.1.1','2.5.29.14','2.5.29.35'):continue
            value=parser.root(blob.value)
            if key=='2.5.29.31':result['crl_distribution_points']=list(dict.fromkeys(uris(value)))
            elif key=='1.3.6.1.5.5.7.1.1':
                need(value.tag==48 and len(value.children)<=32)
                for access in value.children:
                    need(access.tag==48 and len(access.children)==2)
                    method,location=access.children;addresses=uris(location)
                    result['authority_information_access'].extend(dict(method_oid=oid(method),uri=x) for x in addresses)
            elif key=='2.5.29.14':
                need(value.tag==4 and len(value.value)<=64);result['subject_key_identifier']=value.value.hex()
            else:
                need(value.tag==48)
                ids=[x.value.hex() for x in value.children if x.tag==128]
                need(len(ids)<=1 and all(len(x)<=128 for x in ids));result['authority_key_identifier']=ids[0] if ids else None
    return result


def observe_certificate(data,guard=lambda:None):
    try:return certificate(data,guard)
    except Exception:return dict(status='UNAVAILABLE_PUBLIC_CERTIFICATE_FORMAT_OR_BUDGET')


def signer_identity(node):
    if node.tag==48:
        need(len(node.children)==2);issuer,serial=node.children
        need(serial.tag==2 and 0<len(serial.value)<=32 and not serial.value[0]&128)
        return dict(kind='ISSUER_AND_SERIAL',issuer_name_der_sha256=sha256(issuer.raw).hexdigest(),serial_hex=serial.value.hex())
    need(node.tag==128 and 0<len(node.value)<=64)
    return dict(kind='SUBJECT_KEY_IDENTIFIER',key_identifier=node.value.hex())


def signed_data(node):
    need(node.tag==48 and len(node.children)==2 and oid(node.children[0])=='1.2.840.113549.1.7.2')
    explicit=node.children[1];need(explicit.tag==160 and len(explicit.children)==1)
    value=explicit.children[0];need(value.tag==48 and len(value.children)>=4)
    return value


def attributes(node):
    need(node.tag in (160,161) and len(node.children)<=32)
    result=[]
    for attr in node.children:
        need(attr.tag==48 and len(attr.children)==2 and attr.children[1].tag==49)
        result.append((oid(attr.children[0]),attr.children[1].children))
    return result


def signer_times(node,parser,depth=0):
    need(depth<=3 and node.tag==48 and 5<=len(node.children)<=7)
    fields=node.children;result=dict(signer_identity=signer_identity(fields[1]),signing_time_utc=[],timestamp_tokens=[],
        legacy_counter_signers=[],nested_signatures=[],uninterpreted_attributes=[],coverage='PUBLIC_TIME_FIELDS_NOT_EXHAUSTIVE')
    for field in fields[3:]:
        if field.tag not in (160,161):continue
        for key,values in attributes(field):
            need(len(values)<=8)
            if key=='1.2.840.113549.1.9.5':
                need(field.tag==160 and len(values)==1);result['signing_time_utc'].append(utc(values[0]))
            elif key in ('1.2.840.113549.1.9.16.2.14','1.3.6.1.4.1.311.3.3.1'):
                need(field.tag==161)
                for token in values:
                    data=signed_data(token);content=data.children[2]
                    need(content.tag==48 and len(content.children)==2 and oid(content.children[0])=='1.2.840.113549.1.9.16.1.4')
                    wrapped=content.children[1];need(wrapped.tag==160 and len(wrapped.children)==1 and wrapped.children[0].tag==4)
                    info=parser.root(wrapped.children[0].value)
                    need(info.tag==48 and len(info.children)>=5 and info.children[4].tag==24)
                    result['timestamp_tokens'].append(dict(gen_time_utc=utc(info.children[4]),token_sha256=sha256(token.raw).hexdigest(),validation='NOT_PERFORMED'))
            elif key=='1.2.840.113549.1.9.6':
                need(field.tag==161)
                if depth==3:result['legacy_counter_signers'].append(dict(status='NOT_COLLECTED_NESTING_BOUND'))
                else:result['legacy_counter_signers'].extend(signer_times(x,parser,depth+1) for x in values)
            elif key=='1.3.6.1.4.1.311.2.4.1':
                need(field.tag==161)
                if depth==3:result['nested_signatures'].append(dict(status='NOT_COLLECTED_NESTING_BOUND'))
                else:
                    for nested in values:
                        data=signed_data(nested);signers=data.children[-1]
                        need(signers.tag==49 and 0<len(signers.children)<=8)
                        result['nested_signatures'].extend(signer_times(x,parser,depth+1) for x in signers.children)
            else:result['uninterpreted_attributes'].append(dict(kind='SIGNED' if field.tag==160 else 'UNSIGNED',oid=key,value_count=len(values)))
    return result


def pe_signing_times(image,guard=lambda:None):
    """Read only embedded PKCS#7 timestamps; never certify their truth/binding."""
    import struct
    need(type(image) is bytes and 64<=len(image)<=128*1024*1024 and image[:2]==b'MZ')
    pe=struct.unpack_from('<I',image,60)[0];need(64<=pe<=len(image)-24 and image[pe:pe+4]==b'PE\0\0')
    optional=pe+24;size=struct.unpack_from('<H',image,pe+20)[0]
    need(optional+size<=len(image) and size>=144)
    magic=struct.unpack_from('<H',image,optional)[0];need(magic in (0x10b,0x20b))
    directory=optional+(112 if magic==0x20b else 96)
    need(directory+40<=optional+size and struct.unpack_from('<I',image,directory-4)[0]>=5)
    offset,count=struct.unpack_from('<II',image,directory+32)
    if not offset and not count:return dict(status='NO_EMBEDDED_CERTIFICATE_TABLE',records=[])
    need(offset%8==0 and optional+size<=offset and 8<=count<=256*1024 and offset+count<=len(image))
    end=offset+count;records=[];parser=DER(guard)
    while offset<end:
        guard();need(len(records)<4 and offset+8<=end)
        length,revision,kind=struct.unpack_from('<IHH',image,offset)
        need(8<length<=65544 and offset+length<=end and revision==0x200 and kind==2)
        node,padding=parser.one(image[offset+8:offset+length]);need(all(x==0 for x in padding))
        data=signed_data(node);signers=data.children[-1];need(signers.tag==49 and 0<len(signers.children)<=8)
        records.append(dict(index=len(records),signers=[signer_times(x,parser) for x in signers.children]))
        offset+=(length+7)&~7
    need(offset==end)
    return dict(status='EMBEDDED_PUBLIC_TIME_FIELDS_ONLY',coverage='PUBLIC_TIME_FIELDS_NOT_EXHAUSTIVE',timestamp_validation='NOT_PERFORMED',records=records)


def observe_pe_signing_times(image,guard=lambda:None):
    try:return pe_signing_times(image,guard)
    except Exception:return dict(status='UNAVAILABLE_EMBEDDED_TIME_FORMAT_OR_BUDGET')


def provider_signer_matches(times,metadata):
    """Exact public identity relation only, never signature/time acceptance."""
    if metadata.get('status')!='PUBLIC_CERTIFICATE_METADATA_NOT_ACCEPTANCE':return dict(status='NOT_AVAILABLE')
    matches=[]
    def visit(row,path,depth=0):
        need(depth<=4)
        identity=row.get('signer_identity',{});kind=identity.get('kind');same=False
        if kind=='ISSUER_AND_SERIAL':
            same=(identity['issuer_name_der_sha256']==metadata['issuer_name_der_sha256'] and
                int(identity['serial_hex'],16)==int(metadata['serial_hex'],16))
        elif kind=='SUBJECT_KEY_IDENTIFIER':same=bool(metadata.get('subject_key_identifier') and identity['key_identifier']==metadata['subject_key_identifier'])
        if same:matches.append(path)
        for i,nested in enumerate(row.get('nested_signatures',[])):visit(nested,path+f'.nested[{i}]',depth+1)
    for i,record in enumerate(times.get('records',[])):
        for j,row in enumerate(record['signers']):visit(row,f'record[{i}].signer[{j}]')
    return dict(status='PUBLIC_IDENTITY_COMPARISON_ONLY',matches=matches,timestamp_validation='NOT_PERFORMED')
