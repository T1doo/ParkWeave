"""Finite fixture capability, original clock arithmetic, and actual HTTP/PG."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

import pytest

from parkweave import handling_deadline as hd, synthetic_pause_clock as clock
from parkweave.store import Denied, Store
from test_handling_deadline import (definition, compute, attach, deadline_http,
                                    runtime_definition, snapshot)
from test_preparation import preparation_fixture, filled, headers, add


def setup(f, tmp_path, *, duration=3600):
    p = filled(f)
    registry = attach(f, p)
    with f[1].connect() as c:
        now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
    caps = {p['preparation_id']: dict(actor_id='prep-specialist-fixture-a',
            valid_from=(now-timedelta(seconds=1)).isoformat(),
            valid_until=(now+timedelta(seconds=duration)).isoformat())}
    journal = tmp_path/'clock.synthetic-pause.sqlite3'
    service = clock.IsolatedPauseClock(f[0], registry, journal, capabilities=caps, enabled_for_isolated_tests=True)
    return p, service, caps


def url(p):
    return '/api/preparations/'+p['preparation_id']+'/synthetic-pause-clock'


def view(f, p, user='fixture-a', key=None):
    return f[3].get(url(p), headers=headers(f[2], user, key))


def post(f, p, v, action='PAUSE', user='prep-specialist-fixture-a', key=None, **extra):
    body = dict(action=action, reason=clock.REASON, note='SYNTHETIC explicit controlled clock action',
                expected_revision=v['revision'], expected_definition_sha256=v['definition_sha256'])
    body.update(extra)
    return f[3].post(url(p), headers=headers(f[2], user, key or uuid4().hex), json=body)


@pytest.mark.parametrize('pauses,deadline,elapsed', [
    ([('2026-10-09T16:45:00+08:00','2026-10-12T09:05:00+08:00')], '2026-10-12T09:50:00+08:00', 1500),
    ([('2026-10-10T00:00:00+08:00','2026-10-11T23:00:00+08:00')], '2026-10-12T09:30:00+08:00', 2700),
    ([('2026-10-09T16:30:00+08:00','2026-10-09T16:40:00+08:00'),
      ('2026-10-12T09:00:00+08:00','2026-10-12T09:15:00+08:00')], '2026-10-12T09:55:00+08:00', 1200),
])
def test_manual_original_half_open_working_windows_minus_only_pause_overlap(pauses, deadline, elapsed):
    result = hd._calculate(definition(), hd.instant('2026-10-09T16:30:00+08:00'),
        hd.instant('2026-10-12T09:15:00+08:00'), service_id='synthetic-material-preparation',
        service_version=1, org_id='org-a', excluded=[(hd.instant(a),hd.instant(b)) for a,b in pauses])
    assert result['state'] == 'SYNTHETIC_CALCULATED'
    assert result['deadline_local'] == deadline and result['elapsed_work_seconds'] == elapsed
    raw = definition(); raw['pauses'] = [dict(reason=clock.REASON, claimed_legal=True)]
    assert compute(raw)['issues'] == ['PAUSE_AUTHORITY_UNAVAILABLE']


@pytest.mark.parametrize('pauses', [
    [('2026-10-09T16:29:00+08:00','2026-10-09T17:00:00+08:00')],
    [('2026-10-09T17:00:00+08:00','2026-10-09T16:50:00+08:00')],
    [('2026-10-09T16:30:00+08:00','2026-10-09T17:00:00+08:00'),('2026-10-09T16:50:00+08:00','2026-10-12T09:00:00+08:00')],
    [('2026-10-12T09:00:00+08:00','2026-10-12T09:16:00+08:00')],
])
def test_private_interval_guard_cannot_backdate_overlap_reverse_or_use_future(pauses):
    result = hd._calculate(definition(), hd.instant('2026-10-09T16:30:00+08:00'),
        hd.instant('2026-10-12T09:15:00+08:00'), service_id='synthetic-material-preparation',
        service_version=1, org_id='org-a', excluded=[(hd.instant(a),hd.instant(b)) for a,b in pauses])
    assert result['state'] == 'UNKNOWN' and result['deadline_utc'] is None


def test_source_blind_literal_projection_open_resume_and_lunch_not_authority():
    raw=definition('2026-10-09','2026-10-09','UTC',7200,
                   daily={'2026-10-09':[('09:00:00','12:00:00'),('13:00:00','17:00:00')]})
    source=dict(definition=raw,binding=dict(started_at='2026-10-09T09:00:00Z',
        preparation_id='pure-no-capability',case_id='pure-case',run_id='pure-run',
        service_id='synthetic-material-preparation',service_version=1,org_id='org-a'))
    project=clock.IsolatedPauseClock.projection
    pause=[dict(occurred_at='2026-10-09T10:00:00+00:00')]
    v=project(source,hd.instant('2026-10-09T10:30:00Z'),pause)
    assert v['elapsed_work_seconds']==3600 and v['deadline_utc'] is None
    assert v['state']=='SYNTHETIC_PAUSED'
    v=project(source,hd.instant('2026-10-09T11:00:00Z'),pause+[dict(occurred_at='2026-10-09T10:30:00+00:00')])
    assert v['elapsed_work_seconds']==5400 and v['deadline_utc']=='2026-10-09T11:30:00+00:00'
    v=project(source,hd.instant('2026-10-09T14:00:00Z'),
              [dict(occurred_at='2026-10-09T12:00:00+00:00'),dict(occurred_at='2026-10-09T13:00:00+00:00')])
    assert v['elapsed_work_seconds']==14400 and v['deadline_utc']=='2026-10-09T11:00:00+00:00'


def test_actual_http_pause_read_resume_recovery_no_business_or_authority_writes(deadline_http, tmp_path):
    f, requests = deadline_http
    p, service, caps = setup(f, tmp_path)
    before = snapshot(f)
    initial = view(f,p).json(); assert initial['revision'] == 0
    assert initial['fixture_write_enabled'] is False and initial['formal_sla'] is False
    key = uuid4().hex
    response = post(f,p,initial,key=key); assert response.status_code == 201,response.text
    event = response.json()
    paused = view(f,p).json(); time.sleep(.02); later = view(f,p).json()
    assert paused['state'] == later['state'] == 'SYNTHETIC_PAUSED'
    assert paused['deadline_utc'] is None and paused['elapsed_work_seconds'] == later['elapsed_work_seconds']
    assert post(f,p,initial,key=key).json() == event
    assert post(f,p,initial,key=key,note='SYNTHETIC changed same key').status_code == 409
    recovered = view(f,p,'prep-specialist-fixture-a',key).json()
    assert recovered['recovery_status'] == 'COMMITTED' and recovered['recovered_event'] == event
    assert view(f,p,key=uuid4().hex).json()['recovery_status'] == 'NOT_OBSERVED'
    assert post(f,p,paused).status_code == 409
    resume = post(f,p,paused,'RESUME'); assert resume.status_code == 201,resume.text
    final = view(f,p).json()
    interval = hd.instant(resume.json()['occurred_at'])-hd.instant(event['occurred_at'])
    assert hd.instant(final['deadline_utc']) == hd.instant(initial['deadline_utc'])+interval
    assert final['state'] == 'SYNTHETIC_CALCULATED' and final['revision'] == 2
    assert final['events'][1]['previous_sha256'] == event['sha256']
    assert snapshot(f) == before
    normal = f[3].get(url(p).replace('synthetic-pause-clock','handling-deadline'),headers=headers(f[2])).json()
    assert normal['state'] == 'UNKNOWN' and normal['issues'] == ['USE_SYNTHETIC_PAUSE_CLOCK_READ']
    with sqlite3.connect(service.path) as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM fixture_events')
        assert db.execute('SELECT count(*) FROM fixture_events').fetchone()[0] == 2
    out = Path('.runtime/synthetic-handling-pause-20261018/actual-http-outcome.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(dict(scope=clock.SCOPE,initial=initial,pause=event,paused=paused,resume=resume.json(),final=final,
        business_authority_rows_unchanged=True, real_model_calls=0, formal_AT29=False),indent=2)+'\n')


@pytest.mark.parametrize('damage', ['owner','cross-scope','read','review','inactive','role','assignment','material','source-registry'])
def test_current_authority_binding_and_separate_capability_refuse_without_journal_effect(deadline_http,tmp_path,damage):
    f,_ = deadline_http;p,service,_ = setup(f,tmp_path);v = view(f,p).json()
    user='prep-specialist-fixture-a'
    with f[1].connect() as c:
        if damage=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(user,))
        elif damage=='review':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(user,))
        elif damage=='inactive':c.execute('UPDATE principals SET active=false WHERE id=%s',(user,))
        elif damage=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id=%s",(user,))
        elif damage=='assignment':c.execute("UPDATE preparations SET reviewer_id='prep-specialist-fixture-b' WHERE id=%s",(p['preparation_id'],))
    if damage=='owner':user='fixture-a'
    elif damage=='cross-scope':user='prep-specialist-fixture-b'
    elif damage=='material':assert add(f,p).status_code==200
    elif damage=='source-registry':attach(f,p)
    before=snapshot(f);response=post(f,p,v,user=user)
    assert response.status_code in (403,409),response.text
    assert snapshot(f)==before
    with sqlite3.connect(service.path) as db:assert db.execute('SELECT count(*) FROM fixture_events').fetchone()[0]==0


def test_default_disabled_cold_store_and_unissued_constructor_never_create_journal(deadline_http,tmp_path):
    f,_=deadline_http;p=filled(f);v=dict(revision=0,definition_sha256='0'*64)
    before=snapshot(f);assert post(f,p,v).status_code==403 and view(f,p).status_code==403
    path=tmp_path/'refused.synthetic-pause.sqlite3'
    with pytest.raises(Denied):clock.IsolatedPauseClock(f[0],hd.IsolatedDeadlineSources(),path,capabilities={},enabled_for_isolated_tests=True)
    assert not path.exists() and snapshot(f)==before
    p,service,caps=setup(f,tmp_path)
    from parkweave.api import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(Store(f[0].dsn))) as client:
        assert client.get(url(p),headers=headers(f[2])).status_code==403
    with pytest.raises(Denied):clock.IsolatedPauseClock(f[0],service.registry,path,capabilities=caps,enabled_for_isolated_tests=True)
    assert not path.exists()
    cold=Store(f[0].dsn);service.registry.attach_store(cold)
    assert hd.read(cold,f[2]['fixture-a'],__import__('uuid').UUID(p['preparation_id']))['state']=='UNKNOWN'


def test_unknown_fields_time_claims_stale_revision_and_concurrent_pause_do_not_duplicate(deadline_http,tmp_path):
    f,_=deadline_http;p,service,_=setup(f,tmp_path);v=view(f,p).json();before=snapshot(f)
    for extra in [dict(claimed_legal=True),dict(occurred_at='2026-01-01T00:00:00Z'),dict(reason='IMPROVE_SLA'),dict(note='   ')]:
        assert post(f,p,v,**extra).status_code==422
    assert post(f,p,dict(v,revision=1)).status_code==409
    with ThreadPoolExecutor(2) as pool:responses=list(pool.map(lambda _:post(f,p,v),range(2)))
    assert sorted(r.status_code for r in responses)==[201,409]
    assert view(f,p).json()['revision']==1 and snapshot(f)==before


def test_expired_capability_refuses_writes_but_keeps_history_read_only(deadline_http,tmp_path):
    f,_=deadline_http;p,service,_=setup(f,tmp_path,duration=.25);v=view(f,p).json()
    assert post(f,p,v).status_code==201
    end=hd.instant(json.loads(service.capabilities[p['preparation_id']])['capability']['valid_until'])
    while datetime.now(timezone.utc)<end:time.sleep(.02)
    v=view(f,p).json();before=snapshot(f)
    assert not v['fixture_capability_current'] and v['revision']==1
    assert post(f,p,v,'RESUME').status_code==403 and snapshot(f)==before
    assert view(f,p).json()['events']==v['events']


def test_retained_tampered_journal_fails_closed_without_repair(deadline_http,tmp_path):
    f,_=deadline_http;p,service,_=setup(f,tmp_path);v=view(f,p).json();assert post(f,p,v).status_code==201
    with sqlite3.connect(service.path) as db:
        db.execute('DROP TRIGGER fixture_no_update')
        db.execute("UPDATE fixture_events SET payload='{}'")
    damaged=service.path.read_bytes();before=snapshot(f)
    assert view(f,p).status_code==409
    assert service.path.read_bytes()==damaged and snapshot(f)==before


@pytest.mark.parametrize('damage',['bool-revision','request-fingerprint','binding','previous-hash'])
def test_same_schema_rehashed_malformed_event_is_not_adopted(deadline_http,tmp_path,damage):
    f,_=deadline_http;p,service,_=setup(f,tmp_path);v=view(f,p).json();assert post(f,p,v).status_code==201
    with sqlite3.connect(service.path) as db:
        row=db.execute('SELECT payload FROM fixture_events').fetchone();event=json.loads(row[0])
        if damage=='bool-revision':event['revision']=True
        elif damage=='request-fingerprint':event['note']='SYNTHETIC tampered note'
        elif damage=='binding':event['binding_sha256']='0'*64
        else:event['previous_sha256']='0'*64
        event.pop('sha256');event['sha256']=hd.fingerprint(event)
        db.execute('DROP TRIGGER fixture_no_update');db.execute('UPDATE fixture_events SET payload=?',(json.dumps(event),))
        db.execute(clock.SCHEMA['fixture_no_update'])
    before=service.path.read_bytes();assert view(f,p).status_code==409
    assert service.path.read_bytes()==before
