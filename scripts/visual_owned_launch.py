"""Linux-only supervision of one private visual-check worker and its children.

No PID from logs is trusted. Signals use birth-checked pidfds only. A dedicated
subreaper also retains orphaned/setsid descendants until their exit is checked.
"""
import ctypes
import errno
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time


def identity(pid):
    raw=Path('/proc',str(pid),'stat').read_text()
    fields=raw[raw.rfind(')')+2:].split()
    return dict(pid=pid,ppid=int(fields[1]),session=int(fields[3]),start_ticks=int(fields[19]),state=fields[0])


def snapshot():
    rows={}
    for name in os.listdir('/proc'):
        if not name.isdigit():continue
        try:rows[int(name)]=identity(int(name))
        except (FileNotFoundError,ProcessLookupError):pass
    return rows


def exited(fd):return bool(select.select([fd],[],[],0)[0])


def owned_basis(row,owner,private_session):
    """No numeric ancestry closure: only the dedicated parent or reserved SID."""
    return ({'DIRECT_CHILD'} if row['ppid']==owner else set()) | ({'PRIVATE_SESSION'} if private_session is not None and row['session']==private_session else set())


def stable_owned_binding(candidate,before,after,owner,private_session):
    """A snapshot is only a hint; both fresh reads must share an ownership basis."""
    return (candidate['pid']==before['pid']==after['pid'] and
            candidate['start_ticks']==before['start_ticks']==after['start_ticks'] and
            bool(owned_basis(before,owner,private_session) & owned_basis(after,owner,private_session)))


def atomic_report(path,value):
    import tempfile
    data=json.dumps(value,ensure_ascii=False).encode()
    if len(data)>2*1024*1024:raise ValueError('private worker report exceeds2MiB')
    fd,name=tempfile.mkstemp(prefix='.worker-report-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def supervise(argv,*,env,cwd,directory,started,overall_seconds=90,work_seconds=85,term_seconds=1,kill_seconds=2,minimum_operation_seconds=15):
    """Run only a caller-specified trusted worker; this is not an API endpoint.

    All configurable limits can only stay within the original90s work/cleanup
    bound. Tests use smaller limits with known stdlib children, never Chrome.
    """
    assert 0<work_seconds<overall_seconds<=90
    assert 0<term_seconds and 0<kill_seconds and work_seconds+term_seconds+kill_seconds<overall_seconds
    assert 0<minimum_operation_seconds<=15
    owner=os.getpid();libc=ctypes.CDLL(None,use_errno=True)
    report=dict(scope='ONE_DEDICATED_SUBREAPER_WORKER_TREE',status='RUNNING',processes=[],errors=[],signals=[],
                worker_returncode=None,bound_processes_exited=False,subtree_complete=False,handshake=False)
    records={};blocked=set();signal_denied=set();sent=set();worker=None;old=None;enabled=False;action='preflight';enumeration_failed=False
    stop=started+overall_seconds;work_stop=started+work_seconds
    log=directory/'worker-output.log'

    def error(stage,exc):
        report['errors'].append(dict(stage=stage,type=type(exc).__name__,errno=getattr(exc,'errno',None)))

    def pin(row,kind):
        key=(row['pid'],row['start_ticks'])
        if key in records or key in blocked:return
        private_session=worker.pid if worker is not None else None
        try:before=identity(row['pid'])
        except (FileNotFoundError,ProcessLookupError):return
        if before['start_ticks']!=row['start_ticks'] or not owned_basis(before,owner,private_session):return
        if len(records)>=64:raise RuntimeError('64 owned process handles exhausted')
        try:fd=os.pidfd_open(row['pid'],0)
        except ProcessLookupError:return
        except OSError:blocked.add(key);raise
        try:
            try:again=identity(row['pid'])
            except (FileNotFoundError,ProcessLookupError):
                if exited(fd):return
                raise
            if not stable_owned_binding(row,before,again,owner,private_session):return
            item=dict(pid=again['pid'],start_ticks=again['start_ticks'],initial_ppid=again['ppid'],initial_session=again['session'],
                      ownership_basis=sorted(owned_basis(before,owner,private_session) & owned_basis(again,owner,private_session)),
                      kind=kind,exited=False,reaped=False)
            records[key]=(fd,item);fd=None
        finally:
            if fd is not None:os.close(fd)

    def capture():
        nonlocal enumeration_failed
        try:rows=snapshot()
        except Exception:enumeration_failed=True;raise
        # The unreaped worker PID reserves this session identity throughout the
        # sweep; outside processes cannot join another process's session.
        # Escaped descendants are bound only after subreaper adoption. A stale
        # ancestor PID never supplies authority over any other process.
        private_session=worker.pid if worker is not None else None
        owned={owner}|{pid for pid,row in rows.items() if owned_basis(row,owner,private_session)}
        for pid in sorted(owned-{owner}):
            if pid in rows:pin(rows[pid],'WORKER' if worker is not None and pid==worker.pid else 'OWNED_DESCENDANT')
        return rows,owned

    def refresh():
        for fd,item in records.values():item['exited']=exited(fd)

    def worker_exited():
        if worker is None:return True
        root=[(fd,item) for fd,item in records.values() if item['kind']=='WORKER']
        if root:return exited(root[0][0])
        # A refused handshake still owns this unreaped Popen child. Observe it
        # without reaping/releasing its PID/session identity or signalling it.
        value=os.waitid(os.P_PID,worker.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
        return value is not None

    def send(sig):
        for fd,item in reversed(list(records.values())):
            if fd in signal_denied or (fd,sig) in sent or exited(fd):continue
            sent.add((fd,sig))
            try:
                signal.pidfd_send_signal(fd,sig,None,0)
                report['signals'].append(dict(pid=item['pid'],start_ticks=item['start_ticks'],signal=int(sig),via='BIRTH_CHECKED_PIDFD'))
            except ProcessLookupError:pass
            except OSError as exc:
                signal_denied.add(fd);error('pidfd_signal',exc)

    def sweep_until(until,cleanup_signal):
        while time.monotonic()<until:
            if not enumeration_failed:
                try:capture()
                except Exception as exc:error('cleanup_capture',exc)
            refresh()
            send(cleanup_signal)
            if worker_exited() and all(item['exited'] for _,item in records.values()):
                if enumeration_failed:break
                # Re-enumerate after the last known parent exited: a child may
                # have forked between the prior snapshot and pidfd readiness.
                try:
                    rows,owned=capture();refresh();send(cleanup_signal)
                    if all(item['exited'] for _,item in records.values()) and not any(rows[p]['state'] not in ('Z','X') for p in owned-{owner} if p in rows):break
                except Exception as exc:error('cleanup_capture',exc)
            time.sleep(.025)

    try:
        if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):raise RuntimeError('pidfd capability missing')
        if signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL:raise RuntimeError('dedicated supervisor requires default SIGCHLD')
        fd=os.pidfd_open(owner,0);os.close(fd)
        old=ctypes.c_int()
        if libc.prctl(37,ctypes.byref(old),0,0,0)!=0:raise OSError(ctypes.get_errno(),'subreaper query failed')
        if old.value!=0 or any(row['ppid']==owner for row in snapshot().values()):raise RuntimeError('dedicated supervisor requires no existing children/subreaper')
        if libc.prctl(36,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'subreaper setup failed')
        enabled=True
        if time.monotonic()+minimum_operation_seconds>=work_stop:raise TimeoutError('insufficient original time for operation and cleanup reserve')
        with log.open('xb',buffering=0) as output:
            worker=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=output,stderr=output,start_new_session=True)
            action='worker_pin'
            row=identity(worker.pid)
            if row['ppid']!=owner or row['session']!=worker.pid:raise RuntimeError('worker private session binding refused')
            pin(row,'WORKER')
            if (row['pid'],row['start_ticks']) not in records:raise RuntimeError('worker exited before handshake binding')
            action='handshake'
            worker.stdin.write((json.dumps(dict(parent_pid=owner,worker_pid=worker.pid,started=started))+'\n').encode());worker.stdin.close()
            report['handshake']=True
            while time.monotonic()<work_stop:
                action='work_capture';capture();refresh();action='work_wait'
                if records[(row['pid'],row['start_ticks'])][1]['exited']:break
                if log.stat().st_size>256*1024:raise RuntimeError('private worker log exceeds256KiB')
                time.sleep(.025)
            else:raise TimeoutError('original work clock reached cleanup reserve')
    except Exception as exc:error(action,exc)
    finally:
        if worker is not None and worker.stdin is not None and not worker.stdin.closed:
            worker.stdin.close() # No GO after a refused binding; child sees EOF.
        # Keep the worker unreaped and the subreaper active until descendants
        # have been enumerated, signalled by exact handles, and checked.
        if enabled:
            try:
                if not enumeration_failed:capture()
                refresh()
            except Exception as exc:error('final_capture',exc)
            if not worker_exited() or any(not item['exited'] for _,item in records.values()):
                send(signal.SIGTERM);sweep_until(min(stop,time.monotonic()+term_seconds),signal.SIGTERM)
            if not worker_exited() or any(not item['exited'] for _,item in records.values()):
                send(signal.SIGKILL);sweep_until(min(stop,time.monotonic()+kill_seconds),signal.SIGKILL)
            refresh();report['bound_processes_exited']=bool(records) and all(item['exited'] for _,item in records.values())
            if worker is not None:
                try:
                    if worker_exited():report['worker_returncode']=worker.wait(timeout=0)
                except Exception as exc:error('worker_wait',exc)
            for fd,item in records.values():
                if item['kind']=='WORKER':item['reaped']=report['worker_returncode'] is not None;continue
                if not item['exited']:continue
                try:
                    row=identity(item['pid'])
                    if row['start_ticks']==item['start_ticks'] and row['ppid']==owner:
                        pid,code=os.waitpid(item['pid'],os.WNOHANG);item['reaped']=pid==item['pid']
                except FileNotFoundError:pass
                except ChildProcessError:pass # Not an exit proof; the pidfd above is authoritative.
                except OSError as exc:error('adopted_wait',exc)
            try:
                if enumeration_failed:raise RuntimeError('scope enumeration unavailable; no retry or completeness claim')
                rows=snapshot();children=[pid for pid,row in rows.items() if row['ppid']==owner]
                session=[pid for pid,row in rows.items() if worker is not None and row['session']==worker.pid]
                report['remaining_children']=children;report['remaining_private_session_members']=session
                uncertain=any(e['stage'] not in ('work_wait','handshake') for e in report['errors']) or bool(blocked)
                report['subtree_complete']=worker is not None and report['worker_returncode'] is not None and not children and not session and report['bound_processes_exited'] and not uncertain
                if not children:
                    if libc.prctl(36,old.value,0,0,0)!=0:raise OSError(ctypes.get_errno(),'subreaper restore failed')
            except Exception as exc:error('scope_closure',exc)
        report['processes']=[item for _,item in records.values()]
        for fd,_ in records.values():os.close(fd)
        report['elapsed_seconds']=time.monotonic()-started
        report['operation_status']='PASS' if report['worker_returncode']==0 and not report['errors'] else 'FAIL'
        report['status']='CLEANUP_CONFIRMED' if report['subtree_complete'] and report['elapsed_seconds']<=overall_seconds else 'CLEANUP_UNCONFIRMED'
    return report
