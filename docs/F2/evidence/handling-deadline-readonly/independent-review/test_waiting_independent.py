"""Independent observable lock waits across source expiry and authority withdrawal."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,time
import pytest
from conftest import fixture,pg
from test_preparation import preparation_fixture,filled
from test_deadline_independent import own_http,source_for,attach,get,snapshot
OUT=Path('/workspace/ParkWeave/.runtime/independent-handling-deadline-review/waiting')

def wait_observed(c,pattern):
    until=time.monotonic()+1.2
    while time.monotonic()<until:
        c.execute('SELECT pg_stat_clear_snapshot()')
        row=c.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE %s) waiting",(pattern,)).fetchone()
        if row['waiting']:return True
        time.sleep(.01)
    return False

def test_expiry_uses_db_time_after_actual_preparation_lock_wait(own_http):
    f,_=own_http;p=filled(f);raw=source_for(f,p);raw['policy']['target_seconds']=1
    with f[1].connect() as c:expiry=c.execute("SELECT clock_timestamp()+interval '1.6 seconds' expires").fetchone()['expires']
    raw['source']['valid_until']=expiry.isoformat();attach(f,p,raw);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED';original=snapshot(f)
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        block.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(get,f,p)
        assert wait_observed(block,'%FROM preparations%')
        block.execute("SELECT pg_sleep(greatest(0,extract(epoch FROM (%s::timestamptz-clock_timestamp())))+.05)",(expiry,));block.commit();result=pending.result(timeout=5)
    body=result.json();assert result.status_code==200 and body['issues']==['SOURCE_NOT_CURRENT_OR_TIME_INVALID'] and body['deadline_utc'] is None
    from datetime import datetime
    assert datetime.fromisoformat(body['observed_at'])>expiry and snapshot(f)==original
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'expiry.json').write_text(json.dumps(dict(actual_lock_wait=True,deadline_before_wait_was_calculated=True,after_wait_source_unknown=True,observation_after_expiry=True,all_business_permission_rows_unchanged=True),indent=2)+'\n')

def test_waiting_identity_then_original_grant_revoked_is_403(own_http):
    f,_=own_http;p=filled(f);attach(f,p);assert get(f,p).json()['state']=='SYNTHETIC_CALCULATED'
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        f[1].lock_principal(block,'fixture-a',exclusive=True);pending=pool.submit(get,f,p)
        assert wait_observed(block,'%pg_advisory_xact_lock_shared%')
        block.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'");block.commit();result=pending.result(timeout=5)
    original=snapshot(f);assert result.status_code==403 and 'independent-source' not in result.text and snapshot(f)==original
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'revocation.json').write_text(json.dumps(dict(actual_lock_wait=True,original_prepare_grant_withdrawn=True,http_status=403,source_reference_hidden=True,read_no_business_writes=True),indent=2)+'\n')
