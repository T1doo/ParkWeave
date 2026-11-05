"""Real packaged EXE + WebView2 UIAutomation under an original live trial.

The attachment is a UI observer/operator, not a native authority receiver.
Parent keeps the original Controller/lease/profile. No JS injection, CDP,
browser fallback, API write substitute or production admission.
"""
from contextlib import contextmanager
import ctypes as C
from hashlib import sha256
import json
import os
from pathlib import Path
import queue
import re
import struct
import subprocess
import threading
import time
from uuid import uuid4
from scripts.windows_portable import native_trial_authority as a
from scripts.windows_portable.desktop_profile import NativeDesktopProfile
from scripts.windows_portable.local_preparation import PreparationReference
from scripts.windows_portable.native_web_login import MATERIAL_LABELS

_retained=[]
BUTTON=50000;TEXT=50020


def encoded(value):
    a.need(type(value) is str and len(value)<=4096 and '\0' not in value)
    return value.encode('utf-16-le').hex()


class Session:
    def __init__(self,cap,workspace,profile,driver):
        self.cap,self.workspace,self.profile=cap,workspace,profile
        self.proc=None;self.duplicate=C.c_void_p();self.reader=None;self.unknown=False;self.closed=False
        self.close_attempted=False;self.abort_attempted=False;self.abort_result='NOT_ATTEMPTED';self.failure_details=None
        self.responses=queue.Queue();self.end=workspace.deadline
        state=a.state(cap);workspace.check();profile.verify()
        a.need(os.name=='nt' and self.end is not None and self.end<=state.deadline)
        k=profile.api.readonly.k
        duplicate=k.DuplicateHandle;duplicate.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p),C.c_uint32,C.c_int32,C.c_uint32];duplicate.restype=C.c_int32
        current=k.GetCurrentProcess;current.argtypes=[];current.restype=C.c_void_p
        # Retain before every partial native output or child creation.
        _retained.append(self)
        a.need(duplicate(current(),profile.profile,current(),C.byref(self.duplicate),0,True,2))
        startup=subprocess.STARTUPINFO();startup.lpAttributeList={'handle_list':[self.duplicate.value]}
        names=('SystemRoot','WINDIR','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA',
               'GITHUB_ACTIONS','GITHUB_JOB','RUNNER_TRACKING_ID')
        env={name:os.environ[name] for name in names if name in os.environ}
        a.need(env.get('GITHUB_JOB')=='native-business-trial' and env.get('GITHUB_ACTIONS')=='true')
        self.proc=subprocess.Popen([str(driver)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            startupinfo=startup,close_fds=True,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        def read():
            try:
                while True:
                    line=self.proc.stdout.readline(32769)
                    if not line or len(line)>32768:raise RuntimeError('UI_CHANNEL_UNKNOWN')
                    self.responses.put(line)
            except BaseException:self.responses.put(None)
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        # Do not assume a Python version's monotonic epoch is the tick epoch. Map the
        # remaining original window once; never send QPC seconds as tick count.
        ticks=k.GetTickCount64;ticks.argtypes=[];ticks.restype=C.c_uint64
        now=time.monotonic();tick_now=ticks()
        tick_end=tick_now+max(0,int((self.end-now)*1000))
        cleanup_tick_end=tick_now+max(0,int((state.cleanup_end-now)*1000))
        self.call('OPEN',encoded(str(state.payload/'ParkWeave.exe')),str(self.duplicate.value),
            str(workspace.application.port),str(tick_end),str(cleanup_tick_end),'TRIAL_ONLY')

    def call(self,*fields):
        a.state(self.cap);self.workspace.check();self.profile.verify()
        a.need(not self.unknown and not self.closed and time.monotonic()<self.end
             and all(type(x) is str and '\n' not in x and '\t' not in x for x in fields))
        raw=('\t'.join(fields)+'\n').encode('ascii');a.need(len(raw)<=32768)
        try:
            self.proc.stdin.write(raw);self.proc.stdin.flush()
            answer=self.responses.get(timeout=max(.001,self.end-time.monotonic()))
            a.need(answer is not None)
            parts=answer.decode('ascii').rstrip('\n').split('\t')
            if (len(parts)==4 and parts[:2]==['UI1','UNKNOWN'] and parts[2] in
                ('OPEN','SET','CLICK','ITEM','SELECT','SELECT_CONTROL','SELECT_EXPAND',
                 'SELECT_OPTIONS','SELECT_ITEM','SELECT_CONFIRM','REFERENCE','WAIT','CAPTURE','CLOSE')
                and (parts[3]=='NOT_RECORDED' or re.fullmatch('[a-f0-9]{8}',parts[3]))):
                self.failure_details=dict(operation=parts[2],hresult=parts[3])
            a.need(parts[:2]==['UI1','OK']);return parts[2:]
        except BaseException:
            self.unknown=True
            self.abort()
            raise RuntimeError('OWN_DESKTOP_OPERATION_UNKNOWN_NO_RETRY') from None

    def abort(self):
        """Bounded original driver HANDLE only, never a PID or normal close claim.

        Driver owns a kill-on-close UI Job. A forced exit still cannot prove
        normal browser/profile release: retain this whole graph as UNKNOWN.
        """
        if self.abort_attempted:return
        self.abort_attempted=True;self.unknown=True
        try:
            state=a.state(self.cap,cleanup=True)
            left=state.cleanup_end-time.monotonic();a.need(left>0)
            if self.proc is not None:
                if self.proc.poll() is None:self.proc.terminate()
                state=a.state(self.cap,cleanup=True)
                left=state.cleanup_end-time.monotonic();a.need(left>0)
                self.proc.wait(timeout=min(5,left))
            self.abort_result='OWN_DRIVER_EXIT_OBSERVED_BROWSER_PROFILE_RELEASE_UNKNOWN'
        except BaseException:self.abort_result='OWN_DRIVER_EXIT_UNKNOWN'

    def finish(self):
        a.need(not self.close_attempted);self.close_attempted=True
        try:
            answer=self.call('CLOSE')
            a.need(answer==['CLOSED_ORIGINAL_HOST_AND_UI_JOB_ZERO'])
            a.need(self.proc.wait(timeout=max(.001,self.end-time.monotonic()))==0)
            self.proc.stdin.close()
            if self.reader is not None:self.reader.join(timeout=min(1,max(.001,self.end-time.monotonic())))
            a.need(not self.reader.is_alive())
            self.proc.stdout.close()
            close=self.profile.api.readonly.k.CloseHandle;close.argtypes=[C.c_void_p];close.restype=C.c_int32
            original=self.duplicate.value
            a.need(close(original));self.duplicate.value=None
            # Only after browser original HANDLE signal, inner UI Job observation,
            # outer UI Job zero and original driver exit were all acknowledged.
            self.profile.close()
            self.closed=True;_retained.remove(self)
        except BaseException:
            self.abort()
            raise RuntimeError('OWN_DESKTOP_CLOSE_UNKNOWN_NO_RETRY') from None


class NativeDesktopTrial:
    def __init__(self,cap,passwords):
        value=a.state(cap);a.need('OWN_EXE_WEBVIEW_UI_AND_PIXELS' in value.window.operations)
        self.cap=cap;self.driver=value.source_pins.pin_ui_driver()
        self.passwords={key:passwords[key] for key in ('fixture-a','prep-specialist-fixture-a')}
        self.goal='SYNTHETIC UI '+str(uuid4())
        self.checkpoint=None;self.captures=[];self.sessions=[];self.state='NOT_STARTED';self.phase='NOT_STARTED'
        self.directory=Path(dict(value.context[0])['RUNNER_TEMP'])/'parkweave-ui-evidence'
        a.need(not self.directory.exists());self.directory.mkdir()

    @contextmanager
    def session(self,workspace,invocation,fresh):
        profile=NativeDesktopProfile(workspace,invocation,fresh)
        session=object.__new__(Session);self.sessions.append(session)
        try:
            Session.__init__(session,self.cap,workspace,profile,self.driver)
            yield session
        except BaseException:
            session.abort()  # Before Controller stops the backend callback.
            raise

    def cleanup(self):
        for session in self.sessions:
            if not session.closed:session.abort()
        self.discard_inputs()

    def public(self):
        return dict(state=self.state,phase=self.phase,sessions=[dict(closed=x.closed,
            unknown=x.unknown,abnormal_cleanup=x.abort_result,failure=x.failure_details) for x in self.sessions],
            captures_completed=len(self.captures),normal_product_entry='NOT_ACCEPTED',usable_product=False)

    def login(self,session,specialist=False):
        self.phase='LOGIN'
        account='prep-specialist-fixture-a' if specialist else 'fixture-a'
        session.call('SELECT',encoded('账号'),encoded(dict(MATERIAL_LABELS)[account]))
        password=self.passwords[account]
        session.call('SET',encoded('密码'),encoded(password));session.call('CLICK',encoded('登录工作台'))
        session.call('WAIT',encoded('我的事项'),str(TEXT))

    def selected(self,session):session.call('ITEM',encoded(self.goal))

    def reference(self,session,revision):
        return bytes.fromhex(session.call('REFERENCE',str(revision))[0]).decode('utf-16-le')

    def evidence(self,session,slot,text,label,revision):
        self.phase='EVIDENCE'
        session.call('SELECT',encoded('材料项'),encoded(slot))
        session.call('SET',encoded('材料内容'),encoded(text));session.call('SET',encoded('来源与版本'),encoded(label))
        session.call('CLICK',encoded('保存本次材料'))
        self.reference(session,revision)

    def decision(self,session,button,text,revision):
        self.phase='DECISION'
        session.call('SET',encoded('本次办理说明'),encoded(text));session.call('CLICK',encoded(button))
        self.reference(session,revision)

    def switch(self,session,specialist):
        session.call('CLICK',encoded('退出账号'));self.login(session,specialist);self.selected(session)

    def capture(self,session,phase):
        self.phase='CAPTURE'
        for w,h in ((1366,768),(1440,900)):
            path=self.directory/(phase+'-'+str(w)+'x'+str(h)+'.png')
            result=session.call('CAPTURE',encoded(str(path)),str(w),str(h));raw=path.read_bytes()
            a.need(raw[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',raw[16:24])==(w,h) and len(result)==5)
            self.captures.append(dict(file=path.name,bytes=len(raw),sha256=sha256(raw).hexdigest(),
                outer=[w,h],client=[int(result[0]),int(result[1])],dpi=int(result[2]),
                original_host_pid=int(result[3]),original_host_birth=result[4],kind='ACTUAL_EXE_WEBVIEW2_TRIAL_ONLY',
                blank_check='GDI_PIXEL_SAMPLE_VARIETY_AND_VISIBLE_OWN_UIA_CONTROLS',human_visual_review='PENDING'))

    def first(self,workspace,invocation):
        a.need(self.state=='NOT_STARTED');self.state='UNKNOWN'
        with self.session(workspace,invocation,True) as session:
            self.login(session);session.call('SET',encoded('这次希望准备什么？'),encoded(self.goal))
            session.call('CLICK',encoded('提交本地诉求'));session.call('CLICK',encoded('开始准备材料'))
            self.reference(session,1)
            self.evidence(session,'诉求摘要','SYNTHETIC 初稿','SYNTHETIC v1',2)
            self.switch(session,True);self.decision(session,'要求补正','SYNTHETIC 请补齐两项材料',3)
            self.switch(session,False)
            self.evidence(session,'诉求摘要','\u0085SYNTHETIC 修订需求\u0085','SYNTHETIC v2',4)
            self.evidence(session,'材料目录','\ufeffSYNTHETIC 申请与人员清单\ufeff','SYNTHETIC 目录 v1',5)
            self.switch(session,True);self.decision(session,'核对当前资料包','SYNTHETIC 核对当前材料',6)
            self.switch(session,False);self.decision(session,'确认资料准备','SYNTHETIC 企业确认',7)
            self.decision(session,'重开资料准备','SYNTHETIC 显式重开',8)
            self.switch(session,True);self.decision(session,'核对当前资料包','SYNTHETIC 重开后复核',9)
            self.switch(session,False);self.decision(session,'确认资料准备','SYNTHETIC 再次确认',10)
            reference=self.reference(session,10)
            match=re.fullmatch(r'事项 ([a-f0-9-]{36}) · Case ([a-f0-9-]{36}) · 版本 (\d+)',reference);a.need(match is not None)
            # Verification GET only. Every write above came from actual UIA user
            # actions and the real page JavaScript, never this Python client.
            self.phase='VERIFY_READ_ONLY'
            view=workspace.enterprise._request('GET','/api/preparations/'+match[1]);row=view['preparation']
            a.need(row['goal']==self.goal and row['id']==match[1] and row['case_id']==match[2]
                and row['revision']==int(match[3])==10 and row['state']=='LOCAL_CONFIRMED')
            expected=['CREATE','ADD_EVIDENCE','REQUEST_CHANGES','ADD_EVIDENCE','ADD_EVIDENCE','REVIEW','CONFIRM','REOPEN','REVIEW','CONFIRM']
            a.need([x['action'] for x in view['history']]==expected)
            ref=PreparationReference(row['id'],row['run_id'],row['case_id'],row['revision'],row['state'])
            self.checkpoint=workspace.enterprise.checkpoint(ref)
            self.capture(session,'confirmed');self.phase='CLOSE';session.finish();self.state='FIRST_UI_AND_CLOSE_CONFIRMED'

    def reopened(self,workspace,invocation):
        a.need(self.state=='FIRST_UI_AND_CLOSE_CONFIRMED');self.state='UNKNOWN'
        workspace.enterprise.verify_reopened(self.checkpoint)
        with self.session(workspace,invocation,False) as session:
            self.login(session);self.selected(session)
            reference=self.reference(session,10)
            a.need(self.checkpoint.reference.preparation_id in reference and '版本 10' in reference)
            self.capture(session,'reopened');self.phase='CLOSE';session.finish();self.state='UI_EXACT_PERSISTENT_READBACK_AND_CLOSE'
            self.discard_inputs()

    def discard_inputs(self):self.passwords=None  # immutable Python caller copies cannot promise erasure

    def result(self):
        a.need(self.state=='UI_EXACT_PERSISTENT_READBACK_AND_CLOSE' and all(x.closed for x in self.sessions))
        value=dict(result=self.state,artifact_scope='SYNTHETIC_ONLY',captures=self.captures,
            product_new_reopen_entry='NOT_ACCEPTED_TRIAL_VIEWER_ATTACHMENT_ONLY',usable_product=False)
        (self.directory/'desktop-summary.json').write_text(json.dumps(value,indent=2)+'\n')
        return value
