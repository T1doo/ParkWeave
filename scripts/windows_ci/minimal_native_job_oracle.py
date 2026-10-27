"""Reviewed ENG070 fixed native Job oracle; no extra ownership transactions."""
import json, math, os, subprocess, sys, tempfile
from pathlib import Path
repo=Path.cwd().resolve()
if sys.platform!='win32' or sys.version_info[:2]!=(3,12) or __import__('struct').calcsize('P')!=8:
    raise SystemExit('NATIVE_PLATFORM_REQUIRED')
sys.path.insert(0,str(repo/'scripts/windows'))
try:
    import psutil
    from server_identity import WindowsBackend,redirector_authority,positive_pid,creation_time
    from scripts.windows_ci.owned_job import run,OwnedJobError
except Exception:raise SystemExit('NATIVE_DEPENDENCY_REFUSED') from None
try:authority=redirector_authority([str(repo/'.venv-windows/Scripts/python.exe')],repo)
except Exception:raise SystemExit('NATIVE_RUNTIME_BINDING_REFUSED') from None
if not (repo/'.runtime').is_dir():raise SystemExit('EXISTING_RUNTIME_REQUIRED')
known_job={'WINDOWS_REQUIRED','JOB_CREATE_REFUSED','JOB_LIMIT_REFUSED','CREATION_IDENTITY_REFUSED','JOB_BIND_REFUSED','JOB_MEMBERSHIP_REFUSED','THREAD_RESUME_REFUSED','PROCESS_WAIT_REFUSED','JOB_TERMINATE_REFUSED','JOB_QUERY_REFUSED','JOB_STOP_UNCONFIRMED'}
receipts=[]
for timed in (False,True):
    row={'case':'PARENT_TIMEOUT' if timed else 'PARENT_EXIT17','status':'FAIL','stage':'UNRELATED_SETUP','primary':'UNKNOWN','cleanup':'UNKNOWN','record':'UNKNOWN','unrelated':'UNKNOWN','descendant':'UNKNOWN','category':'OTHER','reason':'UNKNOWN'}
    leaf=None;pin=None;backend=None
    try:
        backend=WindowsBackend()
        with tempfile.TemporaryDirectory(prefix='job-native-oracle-',dir=repo/'.runtime') as td:
            root=Path(td);record=root/'owned-child.json'
            leaf=subprocess.Popen([authority['base'],'-c','import time;time.sleep(30)'])
            leaf_created=psutil.Process(leaf.pid).create_time();pin=backend.open(leaf.pid)
            pid,created,alive=backend.identity(pin)
            assert pid==leaf.pid and abs(created-leaf_created)<=.00001 and alive is True
            child='import time;time.sleep(30)'
            parent='import subprocess,sys,json,pathlib,psutil,time; p=subprocess.Popen([sys.executable,"-c",'+repr(child)+']); r=pathlib.Path('+repr(str(record))+'); t=r.with_suffix(".tmp"); t.write_text(json.dumps({"pid":p.pid,"created":psutil.Process(p.pid).create_time()}),encoding="utf-8"); t.replace(r); '+('time.sleep(30)' if timed else 'raise SystemExit(17)')
            row['stage']='PARENT_RUN'
            with (root/'out').open('wb') as out,(root/'err').open('wb') as err:
                try:
                    result=run([sys.executable,'-c',parent],timeout=2 if timed else 5,stdout=out,stderr=err,cwd=repo)
                    row['primary']='EXIT17' if result.returncode==17 else 'OTHER_EXIT'
                    cleanup=result.cleanup
                except subprocess.TimeoutExpired as e:
                    row['primary']='TIMEOUT';cleanup=getattr(e,'cleanup','UNKNOWN')
                row['cleanup']=cleanup if cleanup in ('OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED','SUSPENDED_CHILD_STOPPED','NOT_STARTED') else 'UNKNOWN'
            row['stage']='PRIMARY_GOLD';assert row['primary']==('TIMEOUT' if timed else 'EXIT17')
            row['stage']='CLEANUP_GOLD';assert row['cleanup']=='OWNED_TREE_STOPPED'
            row['stage']='RECORD_READ';data=json.loads(record.read_text(encoding='utf-8'))
            assert set(data)=={'pid','created'} and positive_pid(data['pid']) and creation_time(data['created'])
            row['record']='AVAILABLE'
            row['stage']='UNRELATED_EXACT_LEAF';pid,created,alive=backend.identity(pin)
            assert pid==leaf.pid and abs(created-leaf_created)<=.00001 and alive is True and leaf.poll() is None
            row['unrelated']='LIVE'
            row['stage']='DESCENDANT_EXACT_HANDLE'
            try:proc=psutil.Process(data['pid']);actual=proc.create_time()
            except psutil.NoSuchProcess:row['descendant']='ABSENT'
            else:
                assert creation_time(actual)
                if actual!=data['created']:row['descendant']='OLD_IDENTITY_ABSENT'
                else:
                    h=backend.open(data['pid'])
                    try:
                        pid,created,alive=backend.identity(h)
                        assert pid==data['pid'] and creation_time(created) and abs(created-data['created'])<=.00001 and type(alive) is bool
                        row['descendant']='LIVE' if alive else 'SIGNALED'
                    finally:backend.close(h)
            assert row['descendant'] in ('ABSENT','OLD_IDENTITY_ABSENT','SIGNALED')
            row['status']='PASS';row['stage']='COMPLETE';row['category']='NONE';row['reason']='NONE'
    except Exception as e:
        row['category']=type(e).__name__ if type(e).__name__ in ('AssertionError','OwnedJobError','IdentityRefused','FileNotFoundError','JSONDecodeError','OSError','AccessDenied') else 'OTHER'
        row['reason']=e.args[0] if isinstance(e,OwnedJobError) and len(e.args)==1 and e.args[0] in known_job else 'CHECK_REFUSED'
        row['status']='FAIL'
    finally:
        try:
            if leaf is not None:
                if leaf.poll() is None:leaf.terminate()
                leaf.wait(timeout=5)
        except Exception:
            row['status']='FAIL';row['stage']='UNRELATED_OWNED_CLEANUP';row['category']='OTHER';row['reason']='CHECK_REFUSED'
        finally:
            try:
                if pin is not None:backend.close(pin)
            except Exception:
                row['status']='FAIL';row['stage']='QUERY_HANDLE_CLOSE';row['category']='OTHER';row['reason']='CHECK_REFUSED'
    receipts.append(row)
print(json.dumps({'scope':'MINIMAL_NATIVE_JOB_ORACLE','results':receipts},separators=(',',':')))
raise SystemExit(0 if all(r['status']=='PASS' for r in receipts) else 1)
