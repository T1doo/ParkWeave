# ENG070 最小原生验收方案（本轮不执行）

目标是两项 Job 专项的原生失败阶段，随后分别定位 SESSION/CONFIG 首次创建与真实 occupied/refused、HTTP。当前只有 Linux 与受控证据，不能替代 native PASS。仅适用于可用且已授权的原生 Windows 环境；本轮环境为 Linux，明确不触发新 CI 或启用新 runner。不能改变既有 owner/ACL、身份或权限，也不调用 LIVE。环境必须是现有指定 managed Windows3.12 x64 venv，工作目录为同一仓库；禁止从 PATH 选其他解释器。

## Job：两个场景，三个独立 gold

下面可直接作为 managed Python 的 stdin 运行。只调用原 production Job；normal5秒/父timeout2秒、Job既有5秒清理不变。父及 descendant 保持 managed链；无关进程使用当前运行时经过已有 redirector_authority 绑定的 base executable作为单一 leaf，避免只观察/终止 launcher。只终止本次 Popen 返回的无关 leaf，绝不按读取的 descendant PID kill。每例私有out/err/record在新临时目录，公开仅固定枚举，不含PID、路径、命令、错误文本。

```python
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
```

验收关键：两例都必须独立满足 primary、无关 exact leaf LIVE、descendant ABSENT/旧identity消失/精确handle SIGNALED。missing/partial record、OpenProcess/read/close/权限、时间非法或identity不符全部FAIL/UNKNOWN，不能因为 cleanup=OWNED_TREE_STOPPED就PASS。receipt stage=PARENT_RUN定位production拒绝；RECORD_READ定位启动/落盘；UNRELATED_EXACT_LEAF与DESCENDANT_EXACT_HANDLE定位具体liveness。2秒前record缺失并不允许增加父timeout；先说明启动成本或记录竞态。当前原专项record为直接write_text，本方案atomic落盘避免读partial JSON，但不把该候选归为两例实际共同根因（normal返回17前写入已完成）。

## owner：只测首次新建，既有文件拒绝

单独执行原两项native tests（不得混进Job结论）：

```powershell
& .\.venv-windows\Scripts\python.exe -m pytest -q --tb=no --show-capture=no tests/test_synthetic_session_file.py::test_native_session_owner_matches_current_user_and_existing_bytes_protected tests/test_synthetic_config_file.py::test_native_config_first_creation_and_existing_bytes_protected
```

若仍FAIL，受控backend subclass只在调用前记录固定stage：CURRENT_USER、CREATE_NEW、INSPECT_BEFORE、SET_OWNER、INSPECT_AFTER、VERIFY_OWNER、DACL_COMPARE、CONTROL_COMPARE、FD_TRANSFER、TEXT_WRAP；first bytes和second refusal另记FIRST_BYTES、SECOND_REFUSAL、EXISTING_BYTES。仅允许公开SessionOwnerError已有固定reason与category，以及owner_same/acl_equal/control_equal bool；不输出SID/path/exceptionstr/descriptor。before/after owner_defaulted位之外控制位不能变、DACL字节必须相同；失败不得写token。existing第二次动作必须FileExistsError、零SetOwner调用、原bytes不变；失败后不修复既有文件owner/ACL。阶段数据缺失则仍UNKNOWN。

## 两个其他原生边界单独验收

- 真实port用既有test_real_loopback_refusal_and_occupied_port_are_distinct：先只观察bind失败的errno/winerror是否为已有10048/10013或UNKNOWN；permission拒绝保持，不能把10013无条件视占用或尝试SO_REUSEADDR。再测试已关闭自己的listener所对应database_connect/OperationalError。端口号不公开，不杀外来listener。
- HTTP用LF/CRLF×legacy/current四gold的现有测试。old-default必须500、current必须200及完整UTF8 canonical bytes；真实失败分readiness/status/header/content/owned-thread-cleanup固定阶段，不能提高deadline或接受其他状态。

本方案是可在原生环境复现的受控测量，不是此次执行或CI通过证据。先取得对象/阶段，再决定是否存在产品修复；任何首次新建SERVICE_LOG/PROCESS_RECORD/FILES owner事务也超过目前session/config边界，本方案不执行该权限变更。既有对象owner/ACL仍不自动修复。
