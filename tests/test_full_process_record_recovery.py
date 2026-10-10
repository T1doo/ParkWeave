"""All original issued/PG/API/worker/browser processes exit before ordinary cold start."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil
import pytest
from normal_recovery_process import child_environment


@pytest.mark.skipif(sys.platform!='linux',reason='Linux synthetic lifecycle oracle; Windows native NOT_RUN')
def test_all_original_processes_exit_then_original_sessions_read_normal_records(tmp_path):
    root=tmp_path/'normal-records';root.mkdir(mode=0o700)
    helper=Path(__file__).with_name('normal_recovery_process.py')
    notes={}
    for phase in ('initial','restart'):
        with (root/(phase+'-private.log')).open('w') as log:
            result=subprocess.run([sys.executable,str(helper),str(root),phase],env=child_environment(),stdout=log,stderr=log,timeout=65)
        assert result.returncode==0,(root/(phase+'-private.log')).read_text()
        notes[phase]=json.loads((root/phase/'phase-safe.json').read_text())
        assert notes[phase]['decision']=='PASS'
        remaining=[]
        for info in json.loads((root/phase/'owned-instances-private.json').read_text()):
            try:
                p=psutil.Process(info['pid'])
                if p.create_time()==info['created']:remaining.append((p.pid,p.status()))
            except psutil.NoSuchProcess:pass
        assert remaining==[],remaining
        assert not (root/'data/postmaster.pid').exists()
    a,b=notes['initial'],notes['restart']
    assert a['pg_pid']!=b['pg_pid'] and a['api_pid']!=b['api_pid'] and a['worker_pid']!=b['worker_pid']
    assert a['database']['started']!=b['database']['started']
    for field in ('system_identifier','oid'):assert a['database'][field]==b['database'][field]
    assert a['session_file_sha256']==b['session_file_sha256'] and a['sessions_mode']==b['sessions_mode']=='0o600'
    assert a['business_permissions_logical_hashes']==b['business_permissions_logical_hashes']
    assert a['original_view_sha256']==b['original_view_sha256']
    assert a['migrate_calls']==a['seed_calls']==1 and b['migrate_calls']==b['seed_calls']==0
    assert b['fixture_registry_empty'] and not b['proof_transport'] and b['page_requests_only_get']
    assert b['normal_worker_alive'] and b['denial_audit_count']==a['denial_audit_count']+4
