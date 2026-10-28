"""Static byte-model checks only; no Windows loader or registry calls."""
import hashlib
from pathlib import Path

import pytest

from scripts.windows_portable import payload
from scripts.windows_portable.test_payload import pe


def test_platform_contracts_stay_unresolved_and_crt_stays_private():
    files={'runtime/postgresql/bin/postgres.exe':pe(('kernel32.dll','vcruntime140.dll','msvcp140.dll',
           'api-ms-win-crt-runtime-l1-1-0.dll','pdh.dll')),
           'runtime/python/vcruntime140.dll':pe()}
    value=payload.dll_closure(files)
    assert value['status']=='UNRESOLVED' and value['activation_allowed'] is False
    assert {row['dependency'] for row in value['missing_private_dependencies']}=={'vcruntime140.dll','msvcp140.dll'}
    assert {row['kind'] for row in value['platform_requirements']}=={
        'DECLARED_SYSTEM_DLL','API_SET_REQUIRES_TARGET_SCHEMA','SYSTEM_DLL_REQUIRES_TARGET_OBSERVATION'}
    assert all(row['observed'] is False for row in value['platform_requirements'])
    assert 'pdh.dll' not in payload.OS_DLLS and 'vcruntime140.dll' not in payload.OS_DLLS


def test_arbitrary_wheel_code_or_directory_name_does_not_issue_search_registration():
    files={'vendor/psycopg_binary/pq.pyd':pe(('libpq-pinned.dll',)),
           'vendor/psycopg_binary/__init__.py':b"import os; os.add_dll_directory('psycopg_binary.libs')",
           'vendor/psycopg_binary.libs/libpq-pinned.dll':pe()}
    value=payload.dll_closure(files)
    assert value['wheel_directory_registrations']==[] and value['modeled_wheel_dependencies']==[]
    assert value['missing_private_dependencies']==[dict(file='vendor/psycopg_binary/pq.pyd',
        dependency='libpq-pinned.dll',domain='python')]


def test_locked_real_wheel_byte_profile_and_drift(tmp_path):
    # Use the exact already-acquired public software wheel when available.
    # Never download test fixtures or treat this static check as native loading.
    import zipfile
    path=Path('/workspace/parkweave-delivery-20261028/assets/wheels/psycopg_binary-3.3.6-cp312-cp312-win_amd64.whl')
    if not path.is_file():pytest.skip('explicit acquired locked wheel fixture unavailable')
    expected='e23a66a763fbe83fcc210bc77c27e5a5ea380ebf091c06f34d8561b695e5a40f'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    with zipfile.ZipFile(path) as z:
        files={'vendor/'+name:z.read(name) for name in z.namelist() if not name.endswith('/')}
    name='vendor/psycopg_binary/__init__.py'
    value=payload.dll_closure(files)
    assert len(value['wheel_directory_registrations'])==1
    assert len(value['modeled_wheel_dependencies'])==2
    assert all(row['target'].startswith('vendor/psycopg_binary.libs/') for row in value['modeled_wheel_dependencies'])
    assert value['native_loading']=='NOT_RUN' and value['activation_allowed'] is False
    # No registration may leak into the separate PostgreSQL process domain.
    dll=value['modeled_wheel_dependencies'][0]['dependency']
    files['runtime/postgresql/bin/postgres.exe']=pe((dll,))
    value=payload.dll_closure(files)
    assert any(row['file']=='runtime/postgresql/bin/postgres.exe' and row['dependency']==dll for row in value['missing_private_dependencies'])
    files[name]+=b'\n# changed\n'
    value=payload.dll_closure(files)
    assert value['wheel_directory_registrations']==[]
    assert len([row for row in value['missing_private_dependencies'] if row['dependency']==dll])==3
