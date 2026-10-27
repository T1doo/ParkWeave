"""Local startup observations, not business authority or physical DB proof."""
import json
import os
import re
import select
import stat
import time

from .store import Denied

LIMIT = 4096
DATABASE_SQL = """SELECT current_database() AS name,current_user AS role,session_user AS login,
    (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) AS oid,
    inet_server_addr()::text AS address,inet_server_port() AS port,
    pg_postmaster_start_time()::text AS postmaster,
    (SELECT max(version) FROM schema_version) AS schema,
    (SELECT r.rolcanlogin AND NOT(r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
      AND NOT EXISTS(SELECT 1 FROM pg_roles x JOIN pg_database d ON d.datname=current_database()
        WHERE r.oid=d.datdba OR ((x.rolsuper OR x.rolcreatedb OR x.rolcreaterole OR x.rolreplication
          OR x.rolbypassrls OR x.oid=d.datdba OR left(x.rolname,3)='pg_') AND pg_has_role(r.oid,x.oid,'MEMBER')))
      FROM pg_roles r WHERE r.rolname=current_user) AS safe"""


def challenge(value):
    if type(value) is not str or not re.fullmatch('[a-f0-9]{16,64}', value):
        raise Denied('bounded startup challenge required')
    return value  # Public freshness value, never an authentication secret.


def database(c, mode):
    return validate_database(dict(c.execute(DATABASE_SQL).fetchone()),mode)


def validate_database(row, mode):
    if mode != 'LOCAL': raise Denied('LOCAL startup required')
    if (set(row) != {'name','role','login','oid','address','port','postmaster','schema','safe'}
            or row['safe'] is not True or row['name'] != 'parkweave' or row['role'] != 'parkweave_app' or row['login'] != 'parkweave_app'
            or type(row['oid']) is not int or not 0 < row['oid'] < 2**32
            or row['address'] != '127.0.0.1' or type(row['port']) is not int or not 1 <= row['port'] <= 65535
            or type(row['schema']) is not int or row['schema'] != 32
            or type(row['postmaster']) is not str or not 1 <= len(row['postmaster']) <= 80):
        raise Denied('current application database identity required')
    return row  # OID/boot observations supplement, never replace physical binding.


def actor(principal):
    result = {name:principal[name] for name in ('id','park_id','org_id','role')}
    if any(type(v) is not str or not 1 <= len(v.encode('utf-8')) <= 256 for v in result.values()):
        raise Denied('bounded current actor binding required')
    return result


def api_probe(store, bearer, nonce):
    challenge(nonce)
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL statement_timeout='1500ms'")
        current = store.auth(c,bearer)  # Existing current active principal, no new capability.
        identity = database(c,store.mode)
        principal = actor(current)
    return dict(schema='parkweave-api-ready/1',challenge=nonce,pid=os.getpid(),database=identity,
                actor=principal,mode='LOCAL',business_authority=False)


def validate_frame(frame, kind):
    if type(frame) is not dict: raise Denied('startup frame object required')
    common={'schema','challenge','pid','database','mode'}
    keys=common|({'actor','business_authority'} if kind=='api' else {'state','business_started'})
    if (set(frame)!=keys or frame['schema']!='parkweave-'+kind+'-ready/1'
            or type(frame['pid']) is not int or not 0<frame['pid']<2**32):
        raise Denied('startup frame schema invalid')
    challenge(frame['challenge']);validate_database(frame['database'],frame['mode'])
    if kind=='api':
        if frame['business_authority'] is not False or type(frame['actor']) is not dict or set(frame['actor'])!={'id','park_id','org_id','role'}:
            raise Denied('startup API authority invalid')
        actor(frame['actor'])
    elif frame['state']!='WAITING_GO' or frame['business_started'] is not False:
        raise Denied('worker must wait before business')
    return frame


def _pairs(items):
    result = {}
    for key,value in items:
        if key in result: raise Denied('duplicate startup frame field')
        result[key]=value
    return result


def parse(raw):
    if not 0 < len(raw) <= LIMIT: raise Denied('startup frame limit')
    try: value=json.loads(raw,object_pairs_hook=_pairs)
    except (ValueError,UnicodeError): raise Denied('invalid startup frame') from None
    if type(value) is not dict: raise Denied('startup frame object required')
    return value


def require_pipe(fd):
    if os.name == 'nt':
        import ctypes as C
        import msvcrt
        kernel=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        kind=kernel.GetFileType;kind.argtypes,kind.restype=[C.c_void_p],C.c_uint32
        if kind(msvcrt.get_osfhandle(fd))!=3: raise Denied('private startup pipe required')
    elif not stat.S_ISFIFO(os.fstat(fd).st_mode): raise Denied('private startup pipe required')


def write_frame(fd, frame):
    require_pipe(fd)
    raw=json.dumps(frame,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')+b'\n'
    if len(raw)>LIMIT or os.write(fd,raw)!=len(raw): raise Denied('startup frame write unknown')


def _available(fd, remaining):
    if os.name == 'nt':
        import ctypes as C
        import msvcrt
        kernel=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        kind=kernel.GetFileType;kind.argtypes,kind.restype=[C.c_void_p],C.c_uint32
        handle=msvcrt.get_osfhandle(fd)
        if kind(handle)!=3: raise Denied('private startup pipe required')
        peek=kernel.PeekNamedPipe
        peek.argtypes,peek.restype=[C.c_void_p,C.c_void_p,C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32),C.c_void_p],C.c_int32
        count=C.c_uint32()
        if not peek(handle,None,0,None,C.byref(count),None): raise Denied('startup pipe closed or unknown')
        if not count.value: time.sleep(min(.01,remaining))
        return count.value
    if not stat.S_ISFIFO(os.fstat(fd).st_mode): raise Denied('private startup pipe required')
    return LIMIT if select.select([fd],[],[],remaining)[0] else 0


def read_frame(fd, deadline):
    raw=bytearray()
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0: raise Denied('startup pipe deadline')
        count=_available(fd,remaining)
        if not count: continue
        value=os.read(fd,min(count,LIMIT+1-len(raw)))
        if not value: raise Denied('startup pipe EOF before frame')
        raw.extend(value)
        if len(raw)>LIMIT: raise Denied('startup frame limit')
        if b'\n' in raw:
            if raw.count(b'\n')!=1 or not raw.endswith(b'\n'): raise Denied('one startup frame required')
            if time.monotonic()>=deadline: raise Denied('startup pipe deadline')
            return parse(raw[:-1])


def worker_handshake(store, nonce, *, source_fd=0, sink_fd=1):
    challenge(nonce)
    require_pipe(source_fd);require_pipe(sink_fd)
    deadline=time.monotonic()+10
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL statement_timeout='1500ms'")
        identity=database(c,store.mode)
    if time.monotonic()>=deadline: raise Denied('worker startup deadline')
    write_frame(sink_fd,dict(schema='parkweave-worker-ready/1',challenge=nonce,pid=os.getpid(),
                database=identity,mode='LOCAL',state='WAITING_GO',business_started=False))
    frame=read_frame(source_fd,deadline)
    if frame!={'schema':'parkweave-worker-go/1','challenge':nonce,'command':'GO'}:
        raise Denied('exact startup GO required')
    # Only now may the original claim/consume loop execute.
