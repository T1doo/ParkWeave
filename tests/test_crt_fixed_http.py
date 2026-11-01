"""Controlled WinHTTP ABI callbacks; never network or Windows evidence."""
import ctypes as C
import threading,time
from types import SimpleNamespace
import pytest
from scripts.windows_ci import crt_fixed_http as h


def controlled(monkeypatch):
    monkeypatch.setattr(C,'set_last_error',lambda x:None,raising=False)
    monkeypatch.setattr(C,'get_last_error',lambda:0,raising=False)
    s=SimpleNamespace(calls=[],status=200,body=b'PUBLIC_SYNTHETIC_CRL',pos=0,option_failure=False,close_failure=False,throw_read=False,hold=None)
    def opened(*args):s.calls.append(('OPEN',args));return 1
    def connected(*args):s.calls.append(('CONNECT',args));assert args==(1,'www.microsoft.com',80,0);return 2
    def requested(*args):
        s.calls.append(('REQUEST',args));assert args==(2,'GET',h.CDP.removeprefix('http://www.microsoft.com'),None,None,None,0);return 3
    def option(handle,key,pointer,size):
        assert handle==3 and size==4;v=C.cast(pointer,C.POINTER(h.D)).contents.value;s.calls.append(('OPTION',key,v));return not s.option_failure
    def timeout(*args):s.calls.append(('TIMEOUT',args));assert all(0<x<=15000 for x in args[1:]);return 1
    def send(*args):
        s.calls.append(('SEND',args));assert args==(3,None,0,None,0,0,0)
        assert [('OPTION',63,7),('OPTION',88,0),('OPTION',77,2)]==[x for x in s.calls if x[0]=='OPTION'];return 1
    def received(*args):s.calls.append(('RECEIVE',args));return 1
    def query(handle,kind,name,code,size,index):
        s.calls.append(('STATUS',s.status));assert handle==3 and kind==(19|0x20000000) and name is None and index is None
        code._obj.value=s.status;size._obj.value=4;return 1
    def read(handle,buffer,amount,used):
        s.calls.append(('READ',amount))
        if s.hold is not None:s.hold.wait(1)
        if s.throw_read:raise RuntimeError('PRIVATE_NATIVE_ARGUMENT')
        data=s.body[s.pos:s.pos+amount];s.pos+=len(data);C.memmove(buffer,data,len(data));used._obj.value=len(data);return 1
    def close(handle):s.calls.append(('CLOSE',handle));return not s.close_failure
    functions=dict(WinHttpOpen=opened,WinHttpConnect=connected,WinHttpOpenRequest=requested,WinHttpSetOption=option,
        WinHttpSetTimeouts=timeout,WinHttpSendRequest=send,WinHttpReceiveResponse=received,WinHttpQueryHeaders=query,WinHttpReadData=read,WinHttpCloseHandle=close)
    class Library:
        def __getattr__(self,name):assert name in functions;return functions[name]
    def loader(name,**kw):assert name=='winhttp.dll' and kw==dict(use_last_error=True,winmode=0x800);return Library()
    monkeypatch.setattr(C,'WinDLL',loader,raising=False);monkeypatch.setattr(h,'os',SimpleNamespace(name='nt'))
    s.fetcher=h.FixedCRLFetcher(float(time.monotonic()+120),float(time.monotonic()+135));return s


def test_fixed_request_disables_redirect_auth_cookies_before_send_and_closes_reverse(monkeypatch):
    s=controlled(monkeypatch);assert s.fetcher.fetch()==s.body
    assert [x for x in s.calls if x[0]=='CLOSE']==[('CLOSE',3),('CLOSE',2),('CLOSE',1)]
    assert not s.fetcher.handles and not s.fetcher.uncertain
    with pytest.raises(h.FetchRefused,match='FIXED_CRL_FETCH_REFUSED'):s.fetcher.fetch()


@pytest.mark.parametrize('status',[300,301,302,303,307,308,399,401,407,404,500])
def test_redirects_auth_challenges_and_errors_never_read_body_follow_or_retry(monkeypatch,status):
    s=controlled(monkeypatch);s.status=status
    with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
    assert caught.value.reason==('FETCH_REDIRECT_REFUSED' if 300<=status<400 else 'FETCH_AUTH_REFUSED' if status in (401,407) else 'FETCH_STATUS_REFUSED')
    assert caught.value.cleanup=='OWNED_HTTP_HANDLES_CLOSED'
    assert len([x for x in s.calls if x[0]=='SEND'])==1 and not any(x[0]=='READ' for x in s.calls)


def test_failed_disable_option_refuses_before_send_and_no_alternate_client(monkeypatch):
    s=controlled(monkeypatch);s.option_failure=True
    with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
    assert caught.value.reason=='FETCH_OPTION_REFUSED' and not any(x[0]=='SEND' for x in s.calls)


def test_body_limit_and_empty_body_refuse_without_returning_partial_bytes(monkeypatch):
    monkeypatch.setattr(h,'MAX_BYTES',4);s=controlled(monkeypatch);s.body=b'12345'
    with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
    assert caught.value.reason=='FETCH_BODY_TOO_LARGE' and s.fetcher.data is None
    s=controlled(monkeypatch);s.body=b''
    with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
    assert caught.value.reason=='FETCH_EMPTY_BODY'


def test_pending_native_watchdog_retains_graph_never_closes_or_retries(monkeypatch):
    monkeypatch.setattr(h,'FETCH_SECONDS',.05);s=controlled(monkeypatch);s.hold=threading.Event();before=len(h._unknown)
    try:
        start=time.monotonic()
        with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
        assert time.monotonic()-start<.5 and caught.value.reason=='FETCH_DEADLINE_UNKNOWN'
        assert s.fetcher.pending and s.fetcher.handles==[1,2,3] and not any(x[0]=='CLOSE' for x in s.calls)
        s.hold.set();s.fetcher.thread.join(1)
        assert s.fetcher.uncertain and not any(x[0]=='CLOSE' for x in s.calls)
    finally:
        s.hold.set();s.fetcher.thread.join(1);del h._unknown[before:]


def test_unknown_native_or_cleanup_is_not_success_or_unsafe_close(monkeypatch):
    s=controlled(monkeypatch);s.throw_read=True;before=len(h._unknown)
    try:
        with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
        assert caught.value.reason=='FETCH_NATIVE_UNKNOWN' and caught.value.cleanup=='UNKNOWN_RETAINED'
        assert 'PRIVATE_NATIVE_ARGUMENT' not in str(caught.value) and not any(x[0]=='CLOSE' for x in s.calls)
    finally:del h._unknown[before:]
    s=controlled(monkeypatch);s.close_failure=True;before=len(h._unknown)
    try:
        with pytest.raises(h.FetchRefused) as caught:s.fetcher.fetch()
        assert caught.value.cleanup=='UNKNOWN_RETAINED' and s.fetcher.handles==[1,2,3]
        assert [x for x in s.calls if x[0]=='CLOSE']==[('CLOSE',3)]
    finally:del h._unknown[before:]
