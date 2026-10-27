"""One reviewed platform's full wheel closure; verification has no install effects."""
from email.parser import BytesParser
import hashlib,json,platform,re,stat,sys
from zipfile import ZipFile

TARGET='ubuntu-24.04-x86_64-cpython-3.12-manylinux_2_17'
ROOTS=['fastapi','uvicorn','psycopg','pydantic','httpx']

def normalize(name):return re.sub('[-_.]+','-',name).lower()

def load(directory):
    value=json.loads((directory/'dependencies.lock.json').read_text())
    if (set(value)!={'schema','target','roots','extras','packages'} or value['schema']!=1 or
            value['target']!=TARGET or value['roots']!=ROOTS or value['extras']!={'psycopg':['binary']} or
            type(value['packages']) is not list or len(value['packages'])!=19):raise ValueError('EXACT_WHEEL_LOCK_REQUIRED')
    rows=value['packages'];names=set()
    for r in rows:
        if (set(r)!={'name','version','filename','bytes','sha256','requires_dist','dependencies','pypi_json'} or
                type(r['name']) is not str or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',r['name']) or r['name'] in names or
                type(r['version']) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',r['version']) or
                type(r['filename']) is not str or '/' in r['filename'] or not r['filename'].endswith('.whl') or
                type(r['bytes']) is not int or not 0<r['bytes']<100000000 or
                type(r['sha256']) is not str or not re.fullmatch('[a-f0-9]{64}',r['sha256']) or
                type(r['requires_dist']) is not list or any(type(x) is not str for x in r['requires_dist']) or
                type(r['dependencies']) is not list or any(type(x) is not str for x in r['dependencies']) or
                r['pypi_json']!='https://pypi.org/pypi/'+r['name']+'/'+r['version']+'/json'):
            raise ValueError('CLOSED_WHEEL_RECORD_REQUIRED')
        names.add(r['name'])
    reached=set();pending=list(ROOTS)
    by_name={r['name']:r for r in rows}
    while pending:
        name=pending.pop()
        if name not in names:raise ValueError('COMPLETE_WHEEL_CLOSURE_REQUIRED')
        if name in reached:continue
        reached.add(name);pending.extend(by_name[name]['dependencies'])
    if reached!=names:raise ValueError('EXACT_WHEEL_CLOSURE_REQUIRED')
    expected=''.join(r['name']+'=='+r['version']+' --hash=sha256:'+r['sha256']+'\n' for r in rows)
    if (directory/'requirements.lock').read_text()!=expected:raise ValueError('HASHED_REQUIREMENTS_REQUIRED')
    return rows


def verify(directory,wheels):
    rows=load(directory)
    if {p.name for p in wheels.iterdir()}!={r['filename'] for r in rows}:raise ValueError('EXACT_WHEEL_SET_REQUIRED')
    for r in rows:
        p=wheels/r['filename'];s=p.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_size!=r['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError('WHEEL_BYTES_HASH_REQUIRED')
        with ZipFile(p) as z:
            metadata=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata)!=1:raise ValueError('ONE_WHEEL_METADATA_REQUIRED')
            m=BytesParser().parsebytes(z.read(metadata[0]))
        if (normalize(m['Name'])!=r['name'] or m['Version']!=r['version'] or
                m.get_all('Requires-Dist',[])!=r['requires_dist']):raise ValueError('EXACT_WHEEL_METADATA_REQUIRED')
    return len(rows)


def supported_host():
    if (sys.implementation.name!='cpython' or sys.version_info[:2]!=(3,12) or
            platform.system()!='Linux' or platform.machine()!='x86_64'):
        raise PermissionError('LOCKED_LINUX_X86_64_CPYTHON312_REQUIRED')


def pip_commands(directory,wheels,site):
    load(directory)
    base=['/usr/bin/python3.12','-I','-m','pip','--isolated']
    common=['--no-input','--keyring-provider=disabled','--disable-pip-version-check','--no-cache-dir',
        '--only-binary=:all:','--require-hashes','--no-deps','-r',str(directory/'requirements.lock')]
    return (base+['download',*common,'--index-url','https://pypi.org/simple','--platform','manylinux_2_17_x86_64',
        '--implementation','cp','--python-version','312','--abi','cp312','--dest',str(wheels)],
        base+['install',*common,'--no-index','--find-links',str(wheels),'--no-compile','--target',str(site)])
