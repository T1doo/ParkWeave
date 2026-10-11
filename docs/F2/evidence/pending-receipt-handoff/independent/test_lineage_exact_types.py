"""Owner-corruption negative controls for equivalent JSON values with different types."""
from uuid import UUID
import pytest
from psycopg.types.json import Jsonb
from test_handoff_independent import preparation_fixture,receipt_fixture,setup,body,post,snap
from test_service_dispatches import command as decide

@pytest.mark.parametrize('field,replacement',[
    ('predecessor_receipt_revision',True),
    ('previous_preparation_revision','FLOAT_OF_CURRENT'),
    ('accepted_preparation_revision','FLOAT_OF_CURRENT'),
])
def test_handoff_lineage_equal_value_different_json_type_refused(receipt_fixture,field,replacement):
    f=receipt_fixture;p,row=setup(f);pending=post(f,row,body(f,p,row)).json()
    with f[1].connect() as c:
        event=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(UUID(pending['current_offer']['id']),)).fetchone()['payload']
        old=event[field]
        if replacement=='FLOAT_OF_CURRENT':replacement=float(old)
        assert replacement==old and type(replacement) is not type(old)
        event[field]=replacement
        c.execute("UPDATE service_dispatch_events SET payload=%s WHERE offer_id=%s AND action='REOFFER'",(Jsonb(event),UUID(pending['current_offer']['id'])))
        loaded=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(UUID(pending['current_offer']['id']),)).fetchone()['payload']
        assert type(loaded[field]) is type(replacement)
    before=snap(f);response=decide(f,pending,'ACCEPT')
    assert response.status_code==409,'different lineage JSON type was accepted with HTTP '+str(response.status_code)
    assert snap(f)==before

def test_actual_accept_payload_revision_float_cannot_authorize_new_handoff(receipt_fixture):
    f=receipt_fixture;p,row=setup(f);request=body(f,p,row)
    with f[1].connect() as c:
        event=c.execute("SELECT id,payload FROM service_dispatch_events WHERE dispatch_id=%s AND action='ACCEPT'",(UUID(row['dispatch_id']),)).fetchone()
        changed=dict(event['payload']);original=changed['revision'];assert type(original) is int
        changed['revision']=float(original)
        c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(changed),event['id']))
        loaded=c.execute('SELECT payload FROM service_dispatch_events WHERE id=%s',(event['id'],)).fetchone()['payload']
        assert type(loaded['revision']) is float and loaded['revision']==original
    before=snap(f);response=post(f,row,request)
    assert response.status_code==409 and snap(f)==before
