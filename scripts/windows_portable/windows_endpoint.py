"""Read-only exact connected TCP tuple/PID witness; native NOT_RUN.

No OpenProcess, privilege changes, listener takeover or payload transmission.
"""
import ctypes as C
import os
import socket

from .processes import ProcessRefused


class Row(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ('state','local_address','local_port','remote_address','remote_port','pid')]


class Table(C.Structure):
    _fields_=[('count',C.c_uint32),('rows',Row*1)]


LIMIT=1024*1024


def require_native_support():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8 or C.sizeof(Row)!=24 or Table.rows.offset!=4:
        raise ProcessRefused('NATIVE_WINDOWS_OWNED_ENDPOINT_REQUIRED')


def unique_owner(raw, size, client, server, pid):
    if connected_owner(raw,size,client,server)!=pid:
        raise ProcessRefused('EXACT_ESTABLISHED_API_OWNER_REQUIRED')


def connected_owner(raw, size, client, server):
    if not Table.rows.offset<=size<=min(len(raw),LIMIT): raise ProcessRefused('ENDPOINT_TABLE_BOUNDS')
    count=C.c_uint32.from_buffer_copy(raw[:4]).value
    if count>(size-Table.rows.offset)//C.sizeof(Row): raise ProcessRefused('ENDPOINT_TABLE_COUNT')
    matches=[]
    for index in range(count):
        offset=Table.rows.offset+index*C.sizeof(Row)
        row=Row.from_buffer_copy(raw[offset:offset+C.sizeof(Row)])
        local=(socket.inet_ntoa(row.local_address.to_bytes(4,'little')),socket.ntohs(row.local_port & 0xffff))
        remote=(socket.inet_ntoa(row.remote_address.to_bytes(4,'little')),socket.ntohs(row.remote_port & 0xffff))
        if local==server and remote==client: matches.append((row.state,row.pid))
    if len(matches)!=1 or matches[0][0]!=5 or matches[0][1]<=0:
        raise ProcessRefused('EXACT_ESTABLISHED_API_OWNER_REQUIRED')
    return matches[0][1]


def verify_connection(connection, pid):
    if connection_owner(connection)!=pid:
        raise ProcessRefused('EXACT_ESTABLISHED_API_OWNER_REQUIRED')


def connection_owner(connection):
    require_native_support()
    if (type(connection) is not socket.socket or connection.family!=socket.AF_INET
            or connection.type!=socket.SOCK_STREAM or connection.getpeername()[0]!='127.0.0.1'
            or connection.getsockname()[0]!='127.0.0.1'):
        raise ProcessRefused('EXACT_IPV4_LOOPBACK_CONNECTION_REQUIRED')
    client,server=connection.getsockname(),connection.getpeername()
    library=C.WinDLL('iphlpapi.dll',use_last_error=True,winmode=0x800)
    get=library.GetExtendedTcpTable
    get.argtypes,get.restype=[C.c_void_p,C.POINTER(C.c_uint32),C.c_int32,C.c_uint32,C.c_uint32,C.c_uint32],C.c_uint32
    size=C.c_uint32()
    if get(None,C.byref(size),False,2,5,0)!=122 or not Table.rows.offset<=size.value<=LIMIT:
        raise ProcessRefused('ENDPOINT_TABLE_SIZE_REFUSED')
    buffer=C.create_string_buffer(size.value)
    if get(buffer,C.byref(size),False,2,5,0)!=0:
        raise ProcessRefused('ENDPOINT_TABLE_READ_REFUSED')  # No alternate route or retry.
    pid=connected_owner(buffer.raw,size.value,client,server)
    if connection.getsockname()!=client or connection.getpeername()!=server:
        raise ProcessRefused('API_CONNECTION_CHANGED')
    return pid
