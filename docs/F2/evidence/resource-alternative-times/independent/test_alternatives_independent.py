"""NEW owned PG/ASGI probes, independent interval oracle, no browser/listener."""
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
import time
import pytest
from parkweave import resource_holds as rh
from test_resource_holds import resource_fixture,configure,hold
from test_preparation import headers

TABLES=('synthetic_resources','synthetic_resource_grants','synthetic_resource_holds','synthetic_resource_receipts',
        'synthetic_resource_combinations','synthetic_resource_combination_receipts','preparations','cases',
        'service_receipt_steps','service_receipt_events','outbox','dispatch_notice_outbox','principals','capability_grants')

def snap(f):
    with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in TABLES}

def request(f,duration=17,quantity=1):
    with f[1].connect() as c:base=c.execute('SELECT clock_timestamp() t').fetchone()['t'].replace(microsecond=0)+timedelta(hours=2,seconds=17)
    return {'starts_at':base.isoformat(),'ends_at':(base+timedelta(minutes=duration)).isoformat(),'quantity':quantity,
            'search_from':base.isoformat(),'search_until':(base+timedelta(hours=3)).isoformat()}

def call(f,b,user='fixture-a',rid=rh.RESOURCE_ID):
    return f[3].post('/api/synthetic-resources/'+str(rid)+'/alternative-times',headers=headers(f[2],user),json=b)

def dt(x):return datetime.fromisoformat(x.replace('Z','+00:00'))

def peak_by_midpoint(intervals,lo,hi):
    # Separate oracle: sample each constant-occupancy segment at its midpoint.
    cuts=sorted({lo,hi,*[max(lo,min(hi,t)) for a,b,q in intervals for t in (a,b)]})
    return max([sum(q for a,b,q in intervals if a<=left+(right-left)/2<b)
                for left,right in zip(cuts,cuts[1:]) if left<right] or [0])

@pytest.mark.parametrize('quantity',[1,2,4])
def test_new_grid_matches_independent_midpoint_capacity_oracle(resource_fixture,quantity):
    f=resource_fixture;b=request(f,quantity=quantity);base=dt(b['search_from']);intervals=[]
    configure(f,capacity=20,buffer_seconds=0)
    layout=[(0,20,2,0),(5,30,1,120),(25,55,2,300),(60,75,1,0),(75,90,2,180),(90,120,1,120)]
    for start,end,q,buffer in layout:
        configure(f,buffer_seconds=buffer)
        with f[1].connect() as c:rev=c.execute('SELECT revision FROM synthetic_resources WHERE id=%s',(rh.RESOURCE_ID,)).fetchone()['revision']
        data={'starts_at':(base+timedelta(minutes=start)).isoformat(),'ends_at':(base+timedelta(minutes=end)).isoformat(),
              'quantity':q,'expected_revision':rev,'ttl_seconds':300,'purpose':'SYNTHETIC_OTHER_PRIVATE_BOOKING'}
        response=hold(f,data,user='fixture-b');assert response.status_code==201
        intervals.append((base+timedelta(minutes=start,seconds=-buffer),base+timedelta(minutes=end,seconds=buffer),q))
    configure(f,capacity=4,buffer_seconds=180)
    before=snap(f);response=call(f,b);assert response.status_code==200;result=response.json()
    duration=dt(b['ends_at'])-dt(b['starts_at']);all_starts=[];available=[];start=base
    while start+duration<=dt(b['search_until']):
        all_starts.append(start)
        if peak_by_midpoint(intervals,start-timedelta(seconds=180),start+duration+timedelta(seconds=180))+quantity<=4:available.append(start)
        start+=timedelta(minutes=15)
    assert [dt(x['starts_at']) for x in result['items']]==available[:10]
    assert result['available_candidates']==len(available) and result['scanned_candidates']==len(all_starts)
    assert result['results_truncated']==(len(available)>10) and result['grid_exhausted'] is True
    assert all(x['quantity']==quantity and dt(x['ends_at'])-dt(x['starts_at'])==duration for x in result['items'])
    assert result['coverage']=='SEARCH_WINDOW_GRID_ONLY' and dt(result['grid_anchor'])==base
    assert 'SYNTHETIC_OTHER_PRIVATE_BOOKING' not in response.text and 'fixture-b' not in response.text
    assert snap(f)==before

def test_read_only_read_grant_even_when_execute_hold_revoked(resource_fixture,monkeypatch):
    f=resource_fixture;b=request(f)
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    original=f[0].connect;queries=[]
    class Audited:
        def __init__(self,c):self.c=c
        def execute(self,sql,*a,**k):queries.append(str(sql).lstrip().split()[0]);return self.c.execute(sql,*a,**k)
    @contextmanager
    def connect():
        with original() as c:yield Audited(c)
    monkeypatch.setattr(f[0],'connect',connect)
    before=snap(f);response=call(f,b);assert response.status_code==200 and response.json()['items']
    assert set(queries)<={'SELECT','SET'} and snap(f)==before

@pytest.mark.parametrize('change',['resource_read','global_read','principal_active','tenant','foreign_resource'])
def test_denial_is_generic_no_occupant_or_resource_echo(resource_fixture,change):
    f=resource_fixture;b=request(f);rid=rh.RESOURCE_ID
    with f[1].connect() as c:
        if change=='resource_read':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif change=='global_read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif change=='principal_active':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif change=='tenant':c.execute("UPDATE principals SET org_id='org-unassigned' WHERE id='fixture-a'")
        else:rid=uuid4()
    before=snap(f);response=call(f,b,rid=rid);assert response.status_code==403
    assert response.json()=={'detail':'record unavailable or authorization denied'} and str(rid) not in response.text
    assert snap(f)==before

@pytest.mark.parametrize('side',['minimum','maximum'])
def test_datetime_buffer_extremes_bounded_empty_grid(resource_fixture,side):
    f=resource_fixture;configure(f,buffer_seconds=1800)
    a,z=('0001-01-01T00:00:00Z','0001-01-01T00:00:01Z') if side=='minimum' else ('9999-12-31T23:59:58Z','9999-12-31T23:59:59Z')
    b={'starts_at':a,'ends_at':z,'search_from':a,'search_until':z,'quantity':1};before=snap(f)
    response=call(f,b);assert response.status_code==200 and response.json()['items']==[]
    assert response.json()['scanned_candidates']==1 and snap(f)==before

@pytest.mark.parametrize('field',['starts_at','ends_at','search_from','search_until'])
@pytest.mark.parametrize('side',['minimum','maximum'])
def test_each_iso_field_utc_overflow_returns_validation_not_exception(resource_fixture,field,side):
    f=resource_fixture;b=request(f)
    b[field]='0001-01-01T00:00:00+01:00' if side=='minimum' else '9999-12-31T23:59:59-01:00'
    before=snap(f);response=call(f,b);assert response.status_code==422 and snap(f)==before

def test_single_grid_candidate_and_24h_at_most_96(resource_fixture):
    f=resource_fixture;b=request(f,duration=1);b['ends_at']=(dt(b['starts_at'])+timedelta(seconds=1)).isoformat()
    b['search_until']=b['ends_at'];one=call(f,b).json();assert one['scanned_candidates']==1 and len(one['items'])==1
    b['search_until']=(dt(b['search_from'])+timedelta(hours=24)).isoformat();full=call(f,b).json()
    assert full['scanned_candidates']==96 and full['grid_exhausted'] is True
    assert len(full['items'])==10 and full['results_truncated'] is True

def test_actual_resource_lock_wait_rechecks_rule_revision_and_database_clock(resource_fixture,monkeypatch):
    f=resource_fixture;b=request(f);entered=Event();backend=[];original=rh._lock
    def signal(c,id,shared=False):
        if shared:backend.append(c.info.backend_pid);entered.set()
        return original(c,id,shared=shared)
    monkeypatch.setattr(rh,'_lock',signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            rh._lock(c,rh.RESOURCE_ID)
            c.execute('UPDATE synthetic_resources SET buffer_seconds=0,capacity=1,revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
            revision=c.execute('SELECT revision FROM synthetic_resources WHERE id=%s',(rh.RESOURCE_ID,)).fetchone()['revision']
            future=pool.submit(rh.alternative_times,f[0],f[2]['fixture-a'],rh.RESOURCE_ID,rh.AlternativeTimes(**b));assert entered.wait(2)
            observed=False;deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                with f[1].connect() as observer:row=observer.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(backend[-1],)).fetchone()
                if row and row['wait_event_type']=='Lock':observed=True;break
                time.sleep(.01)
            assert observed and not future.done()
            unlock_time=c.execute('SELECT clock_timestamp() t').fetchone()['t']
        result=future.result(timeout=5)
    assert result['resource_revision']==revision and result['capacity']==1 and result['buffer_seconds']==0
    assert result['server_time']>=unlock_time and result['items']

def test_aggregate_expired_held_released_vs_confirmed_no_cleanup(resource_fixture):
    f=resource_fixture;configure(f,capacity=1,buffer_seconds=0);b=request(f,duration=30)
    with f[1].connect() as c:rev=c.execute('SELECT revision FROM synthetic_resources WHERE id=%s',(rh.RESOURCE_ID,)).fetchone()['revision']
    h={'starts_at':b['starts_at'],'ends_at':b['ends_at'],'quantity':1,'expected_revision':rev,'ttl_seconds':120,'purpose':'SYNTHETIC'}
    owned=hold(f,h,user='fixture-b').json()['hold'];hid=UUID(owned['id'])
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '2 day',expires_at=clock_timestamp()-interval '1 day' WHERE id=%s",(hid,))
    before=snap(f);assert dt(call(f,b).json()['items'][0]['starts_at'])==dt(b['search_from']) and snap(f)==before
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET state='CONFIRMED' WHERE id=%s",(hid,))
    before=snap(f);assert dt(call(f,b).json()['items'][0]['starts_at'])==dt(b['ends_at']) and snap(f)==before
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET state='RELEASED' WHERE id=%s",(hid,))
    before=snap(f);assert dt(call(f,b).json()['items'][0]['starts_at'])==dt(b['search_from']) and snap(f)==before
