"""Independent pure history/receipt probes; no PostgreSQL or HTTP claim."""
from copy import deepcopy
from uuid import uuid4
import pytest
from test_fact_history_read_source import sample
from parkweave import employees_fact_provenance as fine
from parkweave import case_fact_clarifications as facts
from parkweave import source_change_adoption as adoption


def original():
    parent, _, receipts, _, _, _ = sample()
    # Reuse original public receipt fixture, with original prep.event envelope.
    for receipt in receipts:
        receipt['payload'].update(state='IN_PREPARATION',
            scope='SYNTHETIC_LOCAL_PREPARATION_ONLY', qualification='NOT_EVALUATED',
            external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE',
            reason='SYNTHETIC explicit owner selection')
    return parent, receipts


def registered(parent, index, preparation_revision):
    ledger=parent['fact_clarifications']
    prefix=dict(ledger,revision=index,events=ledger['events'][:index])
    status=facts.public_status(facts._result(prefix,'CURRENT',(),prefix['events'][-1]['source_sha256']))
    status['descriptor_sha256']=facts._hash(status)
    return {'P1': {'preparation_revision':preparation_revision,'fact_clarification':status}}


def later_confirmation(parent):
    parent['revision']=5
    ledger=parent['fact_clarifications']
    event=deepcopy(ledger['events'][-1])
    event.update(id=str(uuid4()), revision=3, preparation_revision=5)
    event['decision_sha256']=facts._hash({k:v for k,v in event.items() if k!='decision_sha256'})
    ledger['revision']=3
    ledger['events'].append(event)


def test_historical_prefix_survives_later_legitimate_confirmation():
    parent,_=original()
    before=registered(parent,2,3)
    first=fine.project(parent,before,before)[0]
    later_confirmation(parent)
    assert fine.project(parent,before,before)[0]==first
    after=registered(parent,3,5)
    proof,_=fine.project(parent,before,after)
    assert proof['before']==first['before']
    assert proof['selected_changed'] is False
    assert proof['aggregate_changed'] is True


@pytest.mark.parametrize('kind',['old_confirmation_at_new_registration','future_confirmation_at_old_registration','bool_registration'])
def test_original_registration_chronology_cannot_be_rehashed_away(kind):
    parent,_=original()
    before=registered(parent,2,3)
    later_confirmation(parent)
    after=registered(parent,3,5)
    if kind=='old_confirmation_at_new_registration':after=registered(parent,2,5)
    elif kind=='future_confirmation_at_old_registration':after=registered(parent,3,4)
    else:after['P1']['preparation_revision']=True
    with pytest.raises(fine.ERRORS):fine.project(parent,before,after)


@pytest.mark.parametrize('version',[1,2])
def test_explicit_scope_cannot_use_legacy_history_envelope(version):
    request=dict(expected_preparation_revision=3,expected_request_revision=1,
        expected_source_sha256='a'*64,expected_plan_revision=2,required_goals=['goal'],
        reason='SYNTHETIC owner decision',local_revision=True,
        fact_provenance_scope='EMPLOYEES_USER_ASSERTION_V1',
        opportunity_proof=dict(card_id=str(uuid4()),expected_ledger_revision=1,
            expected_card_version=1,expected_basis_sha256='b'*64,expected_preview_sha256='c'*64))
    event={'local_revision':{'request':request,'source_change':{'version':version}}}
    with pytest.raises(ValueError,match='scope requires source-change version 3'):
        adoption.validate_history({}, {}, event, None, None)


class Rows:
    def __init__(self,value):self.value=value
    def fetchall(self):return self.value
    def fetchone(self):return self.value


class CaptureConnection:
    def __init__(self,parent,receipts):
        self.receipts=receipts
        self.parent=dict(fact_clarifications=deepcopy(parent['fact_clarifications']),row_version='75')
    def execute(self,sql,args):
        if 'FROM preparation_events' in sql:return Rows(self.receipts)
        assert 'FROM preparations' in sql
        return Rows(self.parent)


@pytest.mark.parametrize('mutation',['none','fingerprint','decision','case','actor','revision','duplicate','missing','blank_key','duplicate_key','ledger'])
def test_actual_capture_refuses_nonmatching_original_receipts(mutation):
    parent,receipts=original()
    expected=[{k:facts._normal(r[k]) for k in ('preparation_id','actor_id','revision','action','fingerprint','payload')} for r in receipts]
    rows=[dict(deepcopy(r),id=uuid4(),row_version='71') for r in receipts]
    if mutation=='fingerprint':rows[-1]['fingerprint']='f'*64
    elif mutation=='decision':rows[-1]['payload']['decision_ref']=str(uuid4())
    elif mutation=='case':rows[-1]['payload']['case_id']=str(uuid4())
    elif mutation=='actor':rows[-1]['actor_id']='SYNTHETIC-other-owner'
    elif mutation=='revision':rows[-1]['revision']=4
    elif mutation=='duplicate':rows.append(deepcopy(rows[-1]))
    elif mutation=='missing':rows.pop()
    elif mutation=='blank_key':rows[-1]['request_key']=' '
    elif mutation=='duplicate_key':rows[-1]['request_key']=rows[0]['request_key']
    connection=CaptureConnection(parent,rows)
    if mutation=='ledger':connection.parent['fact_clarifications']['events'][-1]['reason']='different reason'
    if mutation=='none':
        result=fine._capture(connection,parent,expected)
        assert result==facts._hash(dict(ledger=connection.parent,receipts=rows))
    else:
        with pytest.raises(fine.ERRORS):fine._capture(connection,parent,expected)
