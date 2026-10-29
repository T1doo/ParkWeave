"""Bounded v6 API-set file metadata parser; never native admission.

Reads the .apiset section, not a live PEB or executable mapping. The private v6
layout is version-locked from the primary phnt headers (ntpebteb.h); Microsoft
documents loader semantics, not this private binary-layout compatibility.
Unknown versions/ambiguous data refuse. No DLL is loaded and no signature or
held native file identity is inferred from these ordinary bytes/dictionaries.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct

from .crt_pe import Image
from . import payload
from .payload import PayloadRefused


def need(ok):
    if not ok:raise PayloadRefused('API_SET_V6_METADATA_REFUSED')


def contract_name(value):
    need(type(value) is str and 0<len(value)<=512)
    value=value.lower().removesuffix('.dll')
    # v6 namespaces may also contain contract aliases without a version tail.
    # Parsing those names does not expand the product DLL/API trust policy.
    need(bool(re.fullmatch(r'(?:api|ext)-ms-[a-z0-9]+(?:-[a-z0-9]+)*',value)))
    return value


def parse_v6(raw):
    need(type(raw) is bytes and 28<=len(raw)<=4*1024*1024)
    version,size,flags,count,entries,hashes,factor=struct.unpack_from('<7I',raw)
    need(version==6 and 28<=size<=len(raw) and count<=20000 and 0<factor<=65535)
    def span(offset,length):
        need(type(offset) is int and type(length) is int and 0<=offset<=size and 0<=length<=size-offset)
        return raw[offset:offset+length]
    def words(offset,n):return struct.unpack('<'+'I'*n,span(offset,n*4))
    def text(offset,length,*,empty=False):
        need(length%2==0 and 0<=length<=1024 and (empty or length>0))
        try:value=span(offset,length).decode('utf-16-le')
        except UnicodeError:need(False)
        need(all(32<=ord(c)<127 for c in value))
        return value.lower()
    if count:
        need(entries>=28 and hashes>=28)
        span(entries,count*24);span(hashes,count*8)
    result={};by_index=[];total_values=0
    for i in range(count):
        entry_flags,name_offset,name_length,hashed_length,value_offset,value_count=words(entries+i*24,6)
        name=contract_name(text(name_offset,name_length))
        need(name not in result and hashed_length%2==0 and 0<hashed_length<=name_length and value_count<=64)
        total_values+=value_count;need(total_values<=65536)
        if value_count:span(value_offset,value_count*20)
        values=[];aliases=set()
        for j in range(value_count):
            value_flags,alias_offset,alias_length,host_offset,host_length=words(value_offset+j*20,5)
            alias=text(alias_offset,alias_length,empty=True);host=text(host_offset,host_length,empty=True)
            need(alias not in aliases and (not alias or re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*',alias)))
            need(not host or re.fullmatch(r'[a-z0-9_-]+\.dll',host))
            aliases.add(alias);values.append(dict(flags=value_flags,alias=alias,host=host))
        h=0
        for char in text(name_offset,hashed_length):h=(h*factor+ord(char))&0xffffffff
        by_index.append(h)
        result[name]=dict(flags=entry_flags,hashed_length=hashed_length,values=values)
    indices=set();prior=-1
    for i in range(count):
        h,index=words(hashes+i*8,2)
        need(h>=prior and index<count and index not in indices and by_index[index]==h)
        indices.add(index);prior=h
    return dict(schema_version=version,namespace_size=size,namespace_flags=flags,
        hash_factor=factor,namespace_count=count,namespace_sha256=sha256(raw[:size]).hexdigest(),entries=result,
        hash_index_validation='VALIDATED_FROM_BYTES',response_is_native_witness=False,activation_allowed=False)


def extract_image(raw,expected_sha256):
    need(type(expected_sha256) is str and bool(re.fullmatch('[a-f0-9]{64}',expected_sha256))
         and sha256(raw).hexdigest()==expected_sha256)
    image=Image(raw);pe=image.opt-24;count=image.u(pe+6,'H');start=image.opt+image.u(pe+20,'H')
    found=[]
    for i in range(count):
        offset=start+i*40
        name=raw[offset:offset+8].rstrip(b'\0')
        if name==b'.apiset':
            length=image.u(offset+16,'I');position=image.u(offset+20,'I')
            need(28<=length<=4*1024*1024 and position+length<=len(raw))
            found.append(raw[position:position+length])
    need(len(found)==1)
    return dict(**parse_v6(found[0]),file_sha256=expected_sha256,machine='AMD64')


def selected_metadata(value,expected_sha256):
    """Validate a bounded collector response, not its uncollected native trust."""
    need(type(value) is dict and value.get('schema')=='parkweave-api-set-selected-v6/1')
    need({'file','namespace','requested','entries','missing_contracts'}<=set(value))
    need(value.get('response_is_native_witness') is False and value.get('activation_allowed') is False
         and value.get('usable_product') is False and value.get('hash_index_validated') is True)
    file=value['file'];header=value['namespace']
    need(type(file) is dict and type(header) is dict and file.get('sha256')==expected_sha256
         and type(expected_sha256) is str and bool(re.fullmatch('[a-f0-9]{64}',expected_sha256))
         and file.get('machine')=='AMD64' and type(file.get('size')) is int and 64<=file['size']<=4*1024*1024
         and file.get('identity')=='NOT_COLLECTED' and file.get('signature')=='NOT_COLLECTED')
    for key in ('version','size','flags','count','hash_factor'):
        need(type(header.get(key)) is int and 0<=header[key]<=0xffffffff)
    need(header['version']==6 and 28<=header['size']<=file['size'] and header['count']<=20000
         and 0<header['hash_factor']<=65535)
    requested=value['requested'];rows=value['entries'];missing=value['missing_contracts']
    need(type(requested) is list and 0<len(requested)<=64 and type(rows) is list and len(rows)<=64
         and type(missing) is list and len(missing)<=64)
    wanted=[contract_name(name) for name in requested];absent=[contract_name(name) for name in missing]
    need(len(set(wanted))==len(wanted) and len(set(absent))==len(absent))
    entries={}
    for row in rows:
        need(type(row) is dict and set(row)=={'contract','flags','hashed_length','values'})
        name=contract_name(row['contract']);need(name not in entries and name not in absent)
        need(type(row['flags']) is int and 0<=row['flags']<=0xffffffff
             and type(row['hashed_length']) is int and row['hashed_length']%2==0
             and 0<row['hashed_length']<=len(name)*2 and type(row['values']) is list and len(row['values'])<=64)
        values=[];seen=set()
        for target in row['values']:
            need(type(target) is dict and set(target)=={'flags','alias','host'}
                 and type(target['flags']) is int and 0<=target['flags']<=0xffffffff
                 and type(target['alias']) is str and type(target['host']) is str
                 and len(target['alias'])<=512 and len(target['host'])<=512)
            alias=target['alias'].lower();host=target['host'].lower()
            need(alias not in seen and (not alias or re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*',alias))
                 and (not host or re.fullmatch(r'[a-z0-9_-]+\.dll',host)))
            seen.add(alias);values.append(dict(flags=target['flags'],alias=alias,host=host))
        entries[name]=dict(flags=row['flags'],hashed_length=row['hashed_length'],values=values)
    need(set(wanted)==set(entries)|set(absent) and len(entries)<=header['count'])
    return dict(entries=entries,collected_contracts=tuple(wanted),file_sha256=expected_sha256,
        namespace_flags=header['flags'],schema_version=6,hash_index_validation='COLLECTOR_REPORTED',
        response_is_native_witness=False,activation_allowed=False)


def resolve_metadata(mapping,contract,importer_basename):
    """Static selection only; caller cannot turn this into a native witness."""
    need(type(importer_basename) is str and bool(re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(?:exe|dll|pyd)',importer_basename)))
    name=contract_name(contract);entry=mapping['entries'].get(name)
    result=dict(contract=name+'.dll',importer_basename=importer_basename.lower(),host=None,
        status='ABSENT' if entry is None else 'UNMAPPED',response_is_native_witness=False,activation_allowed=False)
    if 'collected_contracts' in mapping and name not in mapping['collected_contracts']:
        return dict(result,status='NOT_COLLECTED')
    if entry is None:return result
    # This parser does not silently normalize undocumented alias styles. Exact
    # basenames are supported; a matching extensionless alias needs native
    # verification instead of incorrectly falling back to the default host.
    importer=importer_basename.lower();stem=importer.rsplit('.',1)[0]
    exact=[row for row in entry['values'] if row['alias']==importer]
    if not exact and any(row['alias']==stem for row in entry['values']):
        return dict(result,status='ALIAS_STYLE_NOT_ACCEPTED')
    choices=exact or [row for row in entry['values'] if row['alias']=='']
    need(len(choices)<=1)
    if choices and choices[0]['host']:
        result.update(status='STATIC_MAPPED_NOT_NATIVE_VERIFIED',host=choices[0]['host'],
            selected_by='EXACT_IMPORTER_ALIAS' if exact else 'DEFAULT')
    return result


def apply_requirements(mapping,requirements):
    """Prepare precise host-export reads; never approve a load or trust a host."""
    need(type(requirements) is dict and requirements.get('schema')=='parkweave-static-loader-symbols/1'
         and requirements.get('activation_allowed') is False and requirements.get('usable_product') is False
         and type(requirements.get('external_imports')) is list and len(requirements['external_imports'])<=16000)
    results=[];hosts={}
    for row in requirements['external_imports']:
        need(type(row) is dict and type(row.get('dependency')) is str)
        if not row['dependency'].startswith(('api-','ext-')):continue
        need(type(row.get('symbols')) is list and len(row['symbols'])<=8192
             and all(type(symbol) is str and 0<len(symbol)<=1024 and all(32<=ord(c)<127 for c in symbol)
                     for symbol in row['symbols']))
        resolved=resolve_metadata(mapping,row['dependency'],row['importer_basename'])
        results.append(dict(**resolved,symbols=row['symbols']))
        if resolved['host']:hosts.setdefault(resolved['host'],set()).update(row['symbols'])
    declared=payload.OS_DLLS|payload.SYSTEM_CRT_PREREQUISITES|payload.SYSTEM_DLL_CANDIDATES
    return dict(schema='parkweave-api-set-target-resolution/1',payload_source=requirements.get('payload_source'),
        payload_manifest_sha256=requirements.get('payload_manifest_sha256'),api_set_file_sha256=mapping.get('file_sha256'),
        schema_version=mapping['schema_version'],hash_index_validation=mapping['hash_index_validation'],
        results=results,target_hosts=[dict(name=name,symbols=sorted(symbols),
            policy='DECLARED_BUT_NOT_OBSERVED' if name in declared else 'UNDECLARED_HOST_REQUIRES_POLICY_REVIEW')
            for name,symbols in sorted(hosts.items())],
        not_mapped=[row for row in results if row['host'] is None],
        native_acceptance='NOT_ACCEPTED',response_is_native_witness=False,activation_allowed=False,usable_product=False,
        limits=['file schema metadata is not the active PEB namespace or loaded process evidence',
            'selected JSON remains collector-reported; host files, signatures, exports and forwarders still require verification'])


def read_bounded(path):
    path=Path(path);need(path.is_file() and not path.is_symlink() and path.stat().st_size<=4*1024*1024)
    raw=path.read_bytes();need(0<len(raw)<=4*1024*1024);return raw


def read_json(path):
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    return json.loads(read_bounded(path),object_pairs_hook=pairs)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--image',type=Path);group.add_argument('--selected',type=Path)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--requirements',required=True,type=Path)
    args=parser.parse_args(argv)
    mapping=(extract_image(read_bounded(args.image),args.expected_sha256) if args.image is not None
             else selected_metadata(read_json(args.selected),args.expected_sha256))
    print(json.dumps(apply_requirements(mapping,read_json(args.requirements)),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
