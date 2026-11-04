"""Fixed public CRL fetch implementation for a future approved diagnostic only.

No work at import, no CLI execution switch, no Cryptnet/WinINet/store writes.
Request-local WinHTTP settings disable redirect/auth/cookies BEFORE send. The
watchdog bounds the caller to 15s INCLUDING native setup/cleanup. A pending
native call is UNKNOWN and retained, never raced by a close or another call;
the future diagnostic may only clean up independent known file handles and
then exit on that outcome, without further HTTP or validation. This
is not a claim that every OS network/audit/DNS side effect is memory-only.
"""
import ctypes as C
import math
import os
import threading
import time
from scripts.windows_ci.crt_crl_preparation import CDP,MAX_BYTES,FETCH_SECONDS
from scripts.windows_portable.authenticode_signature import bind
P=C.c_void_p;D=C.c_uint32;B=C.c_int32
_unknown=[]


class FetchRefused(Exception):
    def __init__(self,reason,cleanup='NOT_COMPLETED'):
        self.reason=reason;self.cleanup=cleanup
        super().__init__('FIXED_CRL_FETCH_REFUSED')


def need(ok,reason):
    if not ok:raise FetchRefused(reason)


class FixedCRLFetcher:
    def __init__(self,work_end,cleanup_end):
        now=time.monotonic()
        need(type(work_end) is float and type(cleanup_end) is float and math.isfinite(work_end)
            and math.isfinite(cleanup_end) and now<work_end<cleanup_end<=now+135,'FETCH_DEADLINE_INVALID')
        need(os.name=='nt' and C.sizeof(P)==8,'WINDOWS_AMD64_REQUIRED')
        self.deadline=min(work_end,now+FETCH_SECONDS);self.cleanup_end=min(cleanup_end,self.deadline+5)
        self.abort=threading.Event();self.done=threading.Event();self.handles=[];self.calls=[]
        self.pending=None;self.uncertain=False;self.started=False;self.data=None;self.error=None;self.thread=None

    def retain(self):
        self.uncertain=True
        if self not in _unknown:_unknown.append(self)

    def guard(self,cleanup=False):
        need(not self.abort.is_set() and not self.uncertain and self.pending is None,'FETCH_OUTCOME_UNKNOWN')
        need(time.monotonic()<(self.cleanup_end if cleanup else self.deadline),'FETCH_DEADLINE')

    def call(self,fn,*args,cleanup=False):
        self.guard(cleanup);record=[fn,args,None];self.calls.append(record);self.pending=record
        try:
            C.set_last_error(0);result=fn(*args)
        except BaseException:
            self.retain();raise FetchRefused('FETCH_NATIVE_UNKNOWN') from None
        record[2]=result
        if not result and C.get_last_error()==997:
            self.retain();raise FetchRefused('FETCH_NATIVE_PENDING_UNKNOWN')
        self.pending=None
        return result

    def handle(self,fn,*args):
        value=self.call(fn,*args)
        if value:self.handles.append(value)  # Adopt outputs before any fallible post-check.
        need(bool(value),'FETCH_HANDLE_REFUSED');self.guard();return value

    def option(self,handle,key,value):
        data=D(value);need(self.call(self.set_option,handle,key,C.byref(data),4),'FETCH_OPTION_REFUSED')

    def timeouts(self,handle):
        self.guard();remaining=max(1,min(15000,int((self.deadline-time.monotonic())*1000)))
        need(self.call(self.set_timeouts,handle,remaining,remaining,remaining,remaining),'FETCH_TIMEOUT_OPTION_REFUSED')

    def worker(self):
        primary=None
        try:
            # Watchdog already running before this loader or any WinHTTP call.
            self.guard();dll=C.WinDLL('winhttp.dll',use_last_error=True,winmode=0x800);self.dll=dll
            op=bind(dll,'WinHttpOpen',P,[C.c_wchar_p,D,C.c_wchar_p,C.c_wchar_p,D])
            connect=bind(dll,'WinHttpConnect',P,[P,C.c_wchar_p,C.c_uint16,D])
            request=bind(dll,'WinHttpOpenRequest',P,[P,C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,P,D])
            self.set_option=bind(dll,'WinHttpSetOption',B,[P,D,P,D])
            self.set_timeouts=bind(dll,'WinHttpSetTimeouts',B,[P,C.c_int32,C.c_int32,C.c_int32,C.c_int32])
            send=bind(dll,'WinHttpSendRequest',B,[P,C.c_wchar_p,D,P,D,D,C.c_size_t])
            receive=bind(dll,'WinHttpReceiveResponse',B,[P,P])
            query=bind(dll,'WinHttpQueryHeaders',B,[P,D,C.c_wchar_p,P,C.POINTER(D),C.POINTER(D)])
            read=bind(dll,'WinHttpReadData',B,[P,P,D,C.POINTER(D)])
            self.close=bind(dll,'WinHttpCloseHandle',B,[P])
            # Existing default proxy configuration only; no PAC/WPAD discovery,
            # credential sharing or proxy/system option changes.
            session=self.handle(op,'ParkWeave-CRL-readonly/1',0,None,None,0);self.timeouts(session)
            connection=self.handle(connect,session,'www.microsoft.com',80,0)
            req=self.handle(request,connection,'GET',CDP.removeprefix('http://www.microsoft.com'),None,None,None,0)
            self.option(req,63,0x1|0x2|0x4)  # disable cookies/redirect/auth, before SEND
            self.option(req,88,0)  # redirect policy NEVER
            self.option(req,77,2)  # auto-logon security HIGH, no ambient credentials
            self.timeouts(req)
            need(self.call(send,req,None,0,None,0,0,0),'FETCH_SEND_REFUSED')
            self.timeouts(req);need(self.call(receive,req,None),'FETCH_RESPONSE_REFUSED')
            code=D();size=D(4)
            need(self.call(query,req,19|0x20000000,None,C.byref(code),C.byref(size),None) and size.value==4,'FETCH_STATUS_UNAVAILABLE')
            need(not 300<=code.value<400,'FETCH_REDIRECT_REFUSED')
            need(code.value not in (401,407),'FETCH_AUTH_REFUSED');need(code.value==200,'FETCH_STATUS_REFUSED')
            total=0;chunks=[]
            while True:
                self.timeouts(req);buffer=C.create_string_buffer(min(65536,MAX_BYTES-total+1));used=D()
                need(self.call(read,req,buffer,len(buffer),C.byref(used)) and used.value<=len(buffer),'FETCH_READ_REFUSED')
                if not used.value:break
                total+=used.value;need(total<=MAX_BYTES,'FETCH_BODY_TOO_LARGE');chunks.append(buffer.raw[:used.value])
            need(total>0,'FETCH_EMPTY_BODY');self.guard();self.data=b''.join(chunks)
        except FetchRefused as error:primary=error
        except BaseException:primary=FetchRefused('FETCH_INTERNAL_FAILURE')
        try:
            if self.uncertain or self.abort.is_set():self.retain()
            else:
                while self.handles:
                    handle=self.handles[-1]
                    need(self.call(self.close,handle,cleanup=True),'FETCH_CLOSE_REFUSED');self.handles.pop()
        except BaseException:
            self.retain()
            if primary is None:primary=FetchRefused('FETCH_CLEANUP_UNKNOWN')
        if primary is not None:primary.cleanup='UNKNOWN_RETAINED' if self.uncertain else 'OWNED_HTTP_HANDLES_CLOSED'
        elif self.uncertain:primary=FetchRefused('FETCH_OUTCOME_UNKNOWN','UNKNOWN_RETAINED')
        self.error=primary;self.done.set()

    def fetch(self):
        need(not self.started,'FETCH_ONE_SHOT');self.started=True;self.guard()
        self.thread=threading.Thread(target=self.worker,daemon=True)
        try:
            self.thread.start();completed=self.done.wait(max(0,self.deadline-time.monotonic()))
        except BaseException:
            self.abort.set();self.retain();raise FetchRefused('FETCH_WAIT_UNKNOWN','UNKNOWN_RETAINED') from None
        if not completed or time.monotonic()>=self.deadline:
            self.abort.set();self.retain();raise FetchRefused('FETCH_DEADLINE_UNKNOWN','UNKNOWN_RETAINED')
        if self.error:raise self.error
        need(not self.uncertain and not self.handles and self.pending is None and self.data is not None,'FETCH_FINAL_STATE_UNKNOWN')
        return self.data
