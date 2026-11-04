"""Actual PE table boundaries and static private closure; never native admission."""
import struct

import pytest

from scripts.windows_portable import loader_inputs as inputs,runtime_payload as runtime
from scripts.windows_portable.payload import PayloadRefused
from scripts.windows_portable.test_payload import pe


def caller(dependencies):
    raw=bytearray(pe(tuple(dependencies)))
    for i,(_,symbol) in enumerate(dependencies.items()):
        thunk=1408+i*32;hint=1600+i*64
        struct.pack_into('<I',raw,512+i*20,thunk-512+0x1000)
        struct.pack_into('<QQ',raw,thunk,hint-512+0x1000,0)
        struct.pack_into('<H',raw,hint,0)
        encoded=symbol.encode('ascii')+b'\0';raw[hint+2:hint+2+len(encoded)]=encoded
    return bytes(raw)


def module(*,name='function',forwarder=None):
    raw=bytearray(pe());opt=0x98
    struct.pack_into('<I',raw,opt+56,0x2000)
    struct.pack_into('<I',raw,opt+240+8,0x800)
    struct.pack_into('<II',raw,opt+112,0x1100,0x100)
    struct.pack_into('<IIIIII',raw,768+16,1,1,1,0x1180,0x1190,0x11a0)
    struct.pack_into('<I',raw,896,0x11c0 if forwarder else 0x1700)
    struct.pack_into('<I',raw,912,0x11b0);struct.pack_into('<H',raw,928,0)
    raw[944:944+len(name)+1]=name.encode('ascii')+b'\0'
    if forwarder:raw[960:960+len(forwarder)+1]=forwarder.encode('ascii')+b'\0'
    return bytes(raw)


def test_exact_symbols_and_importer_specific_target_requests_preserve_closed_gate():
    files={'runtime/postgresql/bin/postgres.exe':caller({'alpha.dll':'function','kernel32.dll':'GetLastError'}),
           'runtime/postgresql/bin/alpha.dll':module()}
    result=inputs.symbol_requirements(files)
    assert result['direct_private_symbol_count']==1 and not result['missing_private_symbols']
    assert result['external_imports']==[dict(importer='runtime/postgresql/bin/postgres.exe',
        importer_basename='postgres.exe',dependency='kernel32.dll',symbols=['GetLastError'],
        reason='DECLARED_SYSTEM_DLL_NOT_OBSERVED',resolution='TARGET_REQUIRED')]
    assert not result['activation_allowed'] and not result['usable_product']
    files['runtime/postgresql/bin/alpha.dll']=module(name='other')
    assert inputs.symbol_requirements(files)['missing_private_symbols'][0]['symbol']=='function'


def test_private_forwarders_resolve_only_in_original_domain_and_cycles_refuse():
    files={'runtime/python/client.exe':caller({'alpha.dll':'function'}),
           'runtime/python/alpha.dll':module(forwarder='beta.function'),
           'runtime/python/beta.dll':module()}
    result=inputs.symbol_requirements(files)
    assert result['private_symbol_count']==1 and result['direct_private_symbol_count']==0
    assert result['resolved_private_forwarders'][0]['terminal_target']=='runtime/python/beta.dll'
    assert not result['private_forwarders']
    files['runtime/python/beta.dll']=module(forwarder='alpha.function')
    assert inputs.symbol_requirements(files)['missing_private_symbols'][0]['reason']=='PRIVATE_FORWARDER_CYCLE'
    # A matching basename in the other private domain is not a replacement.
    files.pop('runtime/python/beta.dll');files['runtime/postgresql/bin/beta.dll']=module()
    result=inputs.symbol_requirements(files)
    assert not result['resolved_private_forwarders'] and not result['external_imports']
    assert result['missing_private_symbols'][0]['reason']=='PRIVATE_FORWARDER_TARGET_MISSING'


def test_api_set_and_external_forwarder_require_target_data_not_a_guessed_host():
    files={'runtime/python/client.exe':caller({'alpha.dll':'function'}),
           'runtime/python/alpha.dll':module(forwarder='api-ms-win-core-file-l1-1-0.ReadFile')}
    result=inputs.symbol_requirements(files)
    row=result['external_imports'][0]
    assert row['importer']=='runtime/python/alpha.dll' and row['symbols']==['ReadFile']
    assert row['dependency']=='api-ms-win-core-file-l1-1-0.dll'
    assert 'kernelbase.dll' not in result['direct_system_dll_names']
    files['runtime/python/alpha.dll']=module(forwarder='beta.#65536')
    with pytest.raises(PayloadRefused,match='FORWARDER_ORDINAL'):inputs.symbol_requirements(files)


def test_original_pg_static_consumer_rejects_present_dll_with_missing_export():
    files={name:pe() if name.endswith(('.dll','.exe')) else b'synthetic share' for name in runtime.REQUIRED}
    files[runtime.PG+'share/postgres.bki']=b'SYNTHETIC $libdir/plpgsql'
    files[runtime.PG+'bin/postgres.exe']=caller({'alpha.dll':'function'})
    files[runtime.PG+'bin/alpha.dll']=module(name='other')
    with pytest.raises(runtime.RuntimePayloadRefused,match='PG_PRIVATE_SYMBOL_OR_FORWARDER_UNRESOLVED'):
        runtime.static_report(files,dict(source_commit='a'*40,manifest_sha256='b'*64))
    files[runtime.PG+'bin/alpha.dll']=module()
    report=runtime.static_report(files,dict(source_commit='a'*40,manifest_sha256='b'*64))
    assert report['symbol_requirements']['private_symbol_count']==1
    assert report['native_loading']=='NOT_ACCEPTED' and not report['activation_allowed']


@pytest.mark.parametrize('dependency',['missing.dll','api-ms-win-madeup.dll'])
def test_empty_lookup_does_not_hide_missing_dll_or_invalid_virtual_contract(dependency):
    raw=bytearray(caller({dependency:'function'}));struct.pack_into('<Q',raw,1408,0)
    result=inputs.symbol_requirements({'runtime/python/client.exe':bytes(raw)})
    assert result['missing_private_symbols']==[dict(importer='runtime/python/client.exe',
        dependency=dependency,symbol=None,reason='PRIVATE_DLL_OR_INVALID_CONTRACT_MISSING')]
    assert result['missing_private_dependencies'] or result['invalid_api_set_contracts']
    assert not result['external_imports'] and not result['activation_allowed']


def test_desktop_and_loader_cannot_borrow_python_or_other_desktop_directory():
    files={'ParkWeave.exe':caller({'alpha.dll':'function'}),
        'launcher/WebView2Loader.dll':caller({'alpha.dll':'function'}),
        'runtime/python/alpha.dll':module()}
    result=inputs.symbol_requirements(files)
    assert len(result['missing_private_dependencies'])==2
    assert all(row['domain']=='desktop' for row in result['missing_private_dependencies'])
    assert len(result['missing_private_symbols'])==2 and not result['private_symbol_count']
    files['alpha.dll']=module()
    result=inputs.symbol_requirements(files)
    assert result['private_symbol_count']==1 and len(result['missing_private_dependencies'])==1
    files['launcher/alpha.dll']=module(name='other')  # Independent directory, distinct bytes allowed.
    result=inputs.symbol_requirements(files)
    assert result['private_symbol_count']==1 and result['missing_private_symbols'][0]['importer'].startswith('launcher/')
