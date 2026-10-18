"""Explicit ordinary CaseStep source adapter for the existing plan verifier.

No identity issuance, Run authority, business command or alternate plan engine.
"""
from .store import Denied, digest


def selected(store):
    service=getattr(store,'_ordinary_case_step_sources',None)
    if service is None:return None
    from .case_step_assignments import OrdinaryCaseStepAssignments, _CaseStepTransactions
    if type(service) is not OrdinaryCaseStepAssignments or service.store is not store:
        raise Denied('exact ordinary plan source dependency required')
    _CaseStepTransactions._unmixed(service)
    return service


def bind(store,service):
    from .case_step_assignments import OrdinaryCaseStepAssignments
    if type(service) is OrdinaryCaseStepAssignments:
        service.validate(store)
        old=getattr(store,'_ordinary_case_step_sources',None)
        if old is not None and old is not service:raise Denied('ordinary plan source dependency already bound')
        store._ordinary_case_step_sources=service
    elif getattr(store,'_ordinary_case_step_sources',None) is not None:
        raise Denied('ordinary plan sources require the same explicit application service')


def connection(store):
    service=selected(store)
    return service._connection(store) if service is not None else store.connect()


def parent(store,c,token,id):
    service=selected(store)
    context=service._context(c,id)
    p,row=context._parent(c,token,id,final=True)
    # A CaseStep grants no access to the whole plan or owner result collection.
    if p['role']=='service_executor':raise Denied('CaseStep grants no whole plan access')
    context._root(c,row)
    if c in service._checks:
        service._checks[c].append(lambda: context._parent(c,token,id,final=True))
    return p,row


def observation(store,c,parent):
    """Return None only for an unconfigured legacy lane, never after a denial."""
    service=selected(store)
    if service is None:return None
    context=service._context(c,parent['id'])
    _,current=context._parent(c,None,parent['id'],recipient_id=parent['owner_id'],final=True)
    root=context._root(c,current)
    from . import service_dispatches as sd, executor_receipts as er
    offer=sd._own_offer(c,{'role':'enterprise_operator'},root) if root else None
    proof=dict(contract=service.contract,contract_id=str(parent['id']),marker=None,current=False)
    if not offer:return proof
    proof['marker']=context._marker(c,current,offer)
    if offer['state']=='ACCEPTED':
        step=context._accepted_step(c,current,offer)
        receipt=er._current(c,step)
        if receipt:_receipt_proof(c,context,step,receipt)
        try:context._live(c,current,offer,final=True)
        except Denied:return proof
        proof['current']=True
    return proof


def guard_current(store,c,parent,proof):
    """Protect only consumers whose actual plan uses the ordinary P3/P4 source."""
    if proof is None or not proof['current']:return
    service=selected(store)
    if service is None or c not in service._checks:
        raise Denied('bounded ordinary plan source transaction required')
    context=service._context(c,parent['id'])
    _,current=context._parent(c,None,parent['id'],recipient_id=parent['owner_id'],final=True)
    root=context._root(c,current)
    from .service_dispatches import _own_offer
    offer=_own_offer(c,{'role':'enterprise_operator'},root) if root else None
    if not offer or offer['state']!='ACCEPTED':raise Denied('current ordinary plan acceptance required')
    # Original _live registers its final check after every subsequent wait.
    # Unrelated P1/P2-only outputs do not acquire a CaseStep deadline.
    context._live(c,current,offer)


def _receipt_proof(c,context,step,receipt):
    """Check original manual command fingerprints without exposing their body."""
    from . import executor_receipts as er
    from .business_frontier_types import historical_fields
    events=c.execute("SELECT * FROM service_receipt_events WHERE step_id=%s AND payload->>'receipt_id'=%s ORDER BY revision",(step['id'],str(receipt['id']))).fetchall()
    try:
        for event in events:
            payload=event['payload'];action=event['action']
            if action not in ('SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'):raise ValueError()
            if action=='SUBMIT':
                original=er.Command(action=action,expected_revision=event['revision']-1,text=receipt['text'],source_kind=receipt['source_kind'],source_label=receipt['source_label'],**historical_fields(payload))
                actor=step['executor_id']
            else:
                original=er.Command(action=action,expected_revision=event['revision']-1,reason=payload['reason'],receipt_sha256=receipt['source_sha256'],**historical_fields(payload))
                actor=step['owner_id']
            if (event['actor_id']!=actor or payload.get('actor_id')!=actor or payload.get('action')!=action
                    or payload.get('receipt_sha256')!=receipt['source_sha256']
                    or event['fingerprint']!=context._fp('RECEIPT_COMMAND',step['id'],original)
                    or receipt.get('adapter_execution') is not None or 'adapter_execution' in payload or 'record_mode' in payload
                    or receipt['actor_id']!=step['executor_id'] or receipt['source_kind']!='SYNTHETIC'
                    or digest(receipt['text'])!=receipt['source_sha256']):raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError):
        raise Denied('original ordinary manual receipt proof required') from None
