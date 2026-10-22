"""Explicit local owner decisions for same-Case first/source-only deliveries.

This is an application-owned ledger, not an external approval source. Startup
only validates existing storage; it never creates schema, identities or grants.
"""
from uuid import UUID
from . import service_plan_approval as core
from .store import Store,Denied,Conflict

SCOPE='LOCAL_CASE_RESOURCE_APPROVAL_V1'
COLUMN='local_resource_approvals'
HEAD='local_resource_approval_head'
TRIGGER='local_resource_approval_prefix'
TRIGGER_BODY=core.TRIGGER_BODY.replace('candidate_plan_approvals',COLUMN).replace('candidate_plan_approval_head',HEAD).replace(core.SCOPE,SCOPE)


def ledger(parent):
    if parent.get(core.COL) is not None or parent.get('candidate_plan_approval_head') is not None:
        raise Conflict('local and isolated approval ledgers cannot mix')
    value,items=core._ledger(parent,column=COLUMN,head_column=HEAD,scope=SCOPE)
    for item in items.values():
        data=core.Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
        if any(getattr(data,k) is not None for k in ('expected_previous_plan_id','replacement_frontier_profile')):
            raise Conflict('local approval supports same-plan source continuation only')
    return value,items


def entered(parent):
    """The immutable Case ledger persists enrolment across application restarts."""
    if parent.get(COLUMN) is None and parent.get(HEAD) is None:return False
    ledger(parent)  # Never downgrade a malformed or partially restored ledger.
    return True


def selected(store):
    local=getattr(store,'_local_resource_approval',None)
    if local is not None:
        if type(local) is not LocalResourceApproval or local.store is not store:
            raise Denied('exact local resource approval dependency required')
        if getattr(store,'_isolated_plan_approval',None) is not None:
            raise Denied('local and isolated approval cannot mix')
    return local


class LocalResourceApproval(core._ApprovalOperations):
    scope=SCOPE;column=COLUMN;head_column=HEAD
    enabled=True
    source_reapproval_enabled=True;plan_replacement_enabled=False
    known_not_started_enabled=False;p3_closure_enabled=False

    def __init__(self,store):
        if type(store) is not Store or store.mode!='LOCAL':raise Denied('ordinary LOCAL approval store required')
        self.store=store
        if any(getattr(store,n,None) is not None for n in ('_isolated_plan_approval','_native_run_access','_isolated_run_access')):
            raise Denied('local approval cannot mix with other approval or Run authority')
        with store.connect() as c:self._schema(c)

    def attach_store(self,store):
        if store is not self.store:raise Denied('same local approval store required')
        existing=getattr(store,'_local_resource_approval',None)
        if existing is not None and existing is not self:raise Denied('local approval already bound')
        store._local_resource_approval=self
        selected(store)
        return store

    def _write_connection(self,store):
        if store is not self.store or selected(store) is not self:raise Denied('same bound local approval store required')
        return store.connect()

    def read(self,store,token,id,key=None):
        if store is not self.store or selected(store) is not self:raise Denied('same bound local approval store required')
        return super().read(store,token,id,key)

    def _schema(self,c):
        if not c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='preparations' AND column_name=%s AND data_type='jsonb'",(COLUMN,)).fetchone():
            raise Denied('existing local resource approval storage required; startup does not install schema')
        core._approval_schema(c,column=COLUMN,head_column=HEAD,trigger=TRIGGER,body=TRIGGER_BODY)

    def _scope(self,c,p,parent):
        self._schema(c)
        if (p['role']!='enterprise_operator' or p['id']!=parent['owner_id'] or parent['namespace']!='SYNTHETIC'
                or parent.get(core.COL) is not None or parent.get('candidate_plan_approval_head') is not None):
            raise Denied('current original local owner and unmixed approval ledger required')

    def _ledger(self,parent):return ledger(parent)
    def scope_ids(self,parent):return [str(parent['id'])]

    def _source(self,store,c,p,parent,data,*,consumed=None):
        if any(getattr(data,k) is not None for k in ('expected_previous_plan_id','replacement_frontier_profile')):
            raise Denied('local approval supports same-plan source continuation only')
        return super()._source(store,c,p,parent,data,consumed=consumed)

    def _unstarted(self,c,parent):
        """Conservative live-write exclusion, not an issued frontier qualification.

        Original app writers serialize on this preparation's UPDATE lock. No
        assertion is made against an administrator deleting its history.
        """
        from .difference_observation import unstarted
        unstarted(c,parent)

    def _guard(self,c,parent,aid,*,consumed=None,auth_only=False):
        if not hasattr(c,'_local_resource_approval_checks'):raise Denied('guarded local approval transaction required')
        check=dict(id=str(parent['id']),approval_id=str(aid),consumed=consumed,auth_only=auth_only)
        if check not in c._local_resource_approval_checks:c._local_resource_approval_checks.append(check)


def verify_receipt(parent,receipt,expected=None,*,link_revision=None):
    proof=receipt.get('plan_approval')
    if expected is not None and proof!=expected:raise Conflict('original local approval link reference mismatch')
    _,items=ledger(parent)
    try:
        item=items[proof['id']];event=item['consumption'];approval=item['approval']
        original=core.Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
        required_revision=original.expected_link_revision+1 if original.expected_link_revision is not None else 1
        if ((link_revision is not None and (type(link_revision) is not int or not 1<=link_revision<=64 or link_revision!=required_revision))
                or set(proof)!={'scope','id','approval_event_id','consumption_event_id','binding_sha256'}
                or proof['scope']!=SCOPE or item['state']!='CONSUMED' or not event or not approval
                or proof['approval_event_id']!=approval['id'] or proof['consumption_event_id']!=event['id']
                or proof['binding_sha256']!=core.cp._hash(item['proposal']['binding'])
                or event['receipt']['combination_id']!=receipt['combination_id']
                or event['receipt']['receipt_sha256']!=core.cp._hash(receipt)
                or event['receipt']['request_key']!=receipt['delivery_binding']['request_key']
                or event['receipt']['fingerprint']!=receipt['delivery_binding']['fingerprint']):raise ValueError()
    except (KeyError,TypeError,ValueError):raise Conflict('original local approval consumption proof mismatch') from None


def configure(store,mode):
    if mode is None:return None
    if mode!='CURRENT_OWNER':raise Denied('explicit CURRENT_OWNER local approval mode required')
    return LocalResourceApproval(store)
