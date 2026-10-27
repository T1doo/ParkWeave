"""CaseStep transactions with isolated and ordinary business admission.

Shared business transactions retain the original isolated admission unchanged.
Ordinary admission consumes current existing preparation rights, never a permit.
No installer, DDL, SQL grants, identity writes or Native policy issuance.
"""
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from . import preparation as prep, service_dispatches as sd, executor_receipts as er
from .business_frontier_types import request as frontier_request, historical_fields
from .store import Store, Denied, Conflict, digest

CONTRACT = 'ISOLATED_CASE_STEP_ASSIGNMENT_V1'
ORDINARY_CONTRACT = 'CASE_STEP_ASSIGNMENT_V1'
ORDINARY_MODE = 'CURRENT_PREPARATION'
LOCAL_DEMO_MODE = 'LOCAL_DEMO_CURRENT_PREPARATION'
TITLE = '合成人工办理回执'
MARKER = 'case_step_assignment'


def _now(c):
    return c.execute('SELECT clock_timestamp() t').fetchone()['t']


def _fp(kind, id, data):
    return digest(prep.canonical(dict(contract=CONTRACT, kind=kind, id=str(id), **frontier_request(data))))


class _CaseStepTransactions:
    contract = CONTRACT

    def _reoffer_predecessor(self,c,parent,root):
        return None

    def _check_reoffer_prefix(self,c,parent,offer,event,marker):
        raise Denied('original isolated CaseStep permits only its first OFFER')

    def _receipt_history_empty(self,c,parent,root):
        return not c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s',(parent['id'],)).fetchone()

    def __init__(self, store, owner, proof, *, owner_id, reviewer_id, executor_ids,
                 enabled_for_isolated_tests=False, seconds=3600, offer_seconds=300):
        from .native_run_access import _proof
        if (enabled_for_isolated_tests is not True or type(store) is not Store or store.mode != 'LOCAL'
                or type(seconds) is not int or not 1 <= seconds <= 3600
                or type(offer_seconds) is not int or not 1 <= offer_seconds <= 300
                or type(executor_ids) not in (tuple, list) or not 1 <= len(executor_ids) <= 8
                or len(set(executor_ids)) != len(executor_ids)
                or len({owner_id, reviewer_id, *executor_ids}) != 2 + len(executor_ids)):
            raise Denied('explicit bounded owned CaseStep dependency required')
        self.endpoint = _proof(owner, proof)
        self.proof, self.store = proof, store
        self.owner_id, self.reviewer_id, self.executor_ids = owner_id, reviewer_id, tuple(executor_ids)
        self.offer_seconds = offer_seconds
        self.tainted_runs = set()
        self._checks = {}
        self._issued = self
        self.contract_id = str(proof.nonce)
        self._unmixed()
        with store.connect() as c:
            self._database(c)
            if any(c.execute('SELECT 1 FROM '+t+' LIMIT 1').fetchone() for t in
                   ('runs','cases','preparations','run_assignments','service_dispatches','service_receipt_steps')):
                raise Denied('fresh zero-business CaseStep initial state required')
            p = c.execute('SELECT * FROM principals WHERE id=%s', (owner_id,)).fetchone()
            if not p: raise Denied('existing CaseStep owner required')
            self.park_id, self.org_id = p['park_id'], p['org_id']
            self._generations(c)
            self.valid_until = _now(c) + timedelta(seconds=seconds)
        self._surfaces()

    def _surfaces(self):
        self.dispatches = SimpleNamespace(Offer=sd.Offer, Command=sd.Command, Reassign=sd.Reassign,
            AcceptRecoverySelection=sd.AcceptRecoverySelection, catalog=self.catalog,
            read_preparation=self.read_preparation, read=self.read_dispatch,
            list_items=self.list_dispatches, offer=self.offer, command=self.dispatch_command,
            recover_accept=self.recover_accept, reassign=self.unsupported,
            recover_reassignment=self.unsupported)
        self.receipts = SimpleNamespace(Create=er.Create, Command=er.Command,
            SubmitRecoverySelection=er.SubmitRecoverySelection, catalog=self.receipt_catalog,
            list_steps=self.list_receipts, create=self.unsupported, read=self.read_receipt,
            command=self.receipt_command, recover_submit=self.recover_submit)

    def _fp(self, kind, id, data):
        return digest(prep.canonical(dict(contract=self.contract, kind=kind, id=str(id), **frontier_request(data))))

    def unsupported(self, *args, **kwargs):
        raise Denied('operation outside isolated CaseStep contract')

    def _unmixed(self):
        if any(getattr(self.store, n, None) is not None for n in (
                '_native_run_access','_isolated_run_access','_isolated_plan_approval',
                '_isolated_local_execution','_isolated_execution_preview',
                '_isolated_resource_execution_preview','_isolated_dispatch_execution_preview',
                '_isolated_receipt_execution_preview','_isolated_lifecycle_execution_preview',
                '_isolated_service_capability_catalog')):
            raise Denied('CaseStep dependency cannot mix with other access or execution providers')
        if (getattr(self.store,'_local_synthetic_demo_catalog',None) is not None
                or getattr(self,'local_synthetic_demo',None) is not None):
            if not local_demo_pair(self,self.store,getattr(self,'local_synthetic_demo',None)):
                raise Denied('CaseStep dependency requires its exact explicit local demo pair')

    def _database(self, c):
        from . import case_fact_clarifications as facts
        p = self.proof
        if (type(p) is not facts.FixtureDatabaseEvidence or facts._fixture_databases.get(p.nonce) is not p
                or facts._fixture_clusters.get(p.cluster.nonce) is not p.cluster or c.autocommit):
            raise Denied('current original owned fixture proof required')
        row = c.execute('SELECT oid,datname,pg_postmaster_start_time() started FROM pg_database WHERE datname=current_database()').fetchone()
        if ((c.info.host, c.info.port) != self.endpoint or row['oid'] != p.database_oid
                or row['datname'] != p.database_name or row['started'] != p.cluster.postmaster_start):
            raise Denied('CaseStep database binding changed')

    def validate(self, store):
        if type(self) is not IsolatedCaseStepAssignments or self._issued is not self or store is not self.store:
            raise Denied('exact isolated CaseStep dependency required')
        with self._connection(store): pass

    @contextmanager
    def _connection(self, store):
        if store is not self.store or self._issued is not self: raise Denied('CaseStep store binding required')
        self._unmixed()
        with store.connect() as c:
            c.execute("SET LOCAL lock_timeout='3s'")
            self._database(c)
            if _now(c) >= self.valid_until: raise Denied('isolated CaseStep dependency expired')
            self._checks[c] = []
            try:
                yield c
                for check in self._checks[c]: check()
            finally:
                self._checks.pop(c, None)
            self._database(c)
            if _now(c) >= self.valid_until: raise Denied('isolated CaseStep dependency expired')

    def _generations(self, c, executors=None):
        ids = [(self.owner_id,'enterprise_operator',('READ','EXECUTE'),'PREPARE'),
               (self.reviewer_id,'park_specialist',('READ',),'REVIEW_ASSIGNED')]
        ids += [(x,'service_executor',('READ',),None) for x in (self.executor_ids if executors is None else executors)]
        result = {}
        for id, role, caps, permission in sorted(ids):
            self.store.lock_principal(c, id)
            p = c.execute('SELECT *,xmin::text generation FROM principals WHERE id=%s',(id,)).fetchone()
            if not p or not p['active'] or p['role'] != role or (p['park_id'],p['org_id']) != (self.park_id,self.org_id):
                raise Denied('current same-domain CaseStep participant required')
            g = {'principal':p['generation']}
            for cap in caps:
                self.store.check_capability(c,p,cap)
                row = c.execute('SELECT xmin::text generation FROM capability_grants WHERE principal_id=%s AND capability=%s AND active',(id,cap)).fetchone()
                g[cap] = row['generation']
            if permission:
                prep.grant(self.store,c,p,permission)
                g[permission] = c.execute('SELECT xmin::text generation FROM preparation_grants WHERE principal_id=%s AND capability=%s AND active',(id,permission)).fetchone()['generation']
            result[id] = g
        return result

    def _parent(self, c, token, id, *, write=False, stopping=False, final=False, recipient_id=None):
        if recipient_id is None:
            p = sd._auth(self.store,c,token)
        else:
            # Trusted outbox consumer uses the original current DB recipient,
            # never a session/identity issued from an event or marker.
            self.store.lock_principal(c,recipient_id)
            p=c.execute('SELECT * FROM principals WHERE id=%s AND active',(recipient_id,)).fetchone()
            if not p:raise Denied('current CaseStep recipient required')
            self.store.check_capability(c,p,'READ')
        if p['id'] not in (self.owner_id,self.reviewer_id,*self.executor_ids): raise Denied('CaseStep participant required')
        parent = c.execute('SELECT * FROM preparations WHERE id=%s '+('FOR UPDATE' if write else 'FOR SHARE'),(id,)).fetchone()
        if (not parent or parent['namespace'] != 'SYNTHETIC'
                or (parent['park_id'],parent['org_id'],parent['owner_id'],parent['reviewer_id']) !=
                   (self.park_id,self.org_id,self.owner_id,self.reviewer_id)):
            raise Denied('exact CaseStep Case scope required')
        # No fallback for any existing/revoked Run authority or Native history.
        run = c.execute('SELECT to_jsonb(r) value FROM runs r WHERE id=%s',(parent['run_id'],)).fetchone()
        native = run and any(v is not None for k,v in run['value'].items() if k.startswith('native_run_access'))
        if (not run or (self.tainted_runs is not None and str(parent['run_id']) in self.tainted_runs) or native or
                c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()):
            if self.tainted_runs is not None:self.tainted_runs.add(str(parent['run_id']))
            raise Denied('existing Run authority cannot become CaseStep fallback')
        if (run['value']['principal_id'] != self.owner_id or run['value']['namespace'] != 'SYNTHETIC'
                or run['value']['state'] != 'SUCCEEDED' or run['value']['success_scope'] != 'LOCAL_CASE_CREATED'):
            raise Denied('original successful synthetic Case creation required')
        case=c.execute('SELECT * FROM cases WHERE id=%s',(parent['case_id'],)).fetchone()
        operation=c.execute("SELECT 1 FROM operations WHERE run_id=%s AND action='case.create' AND state='VERIFIED'",(parent['run_id'],)).fetchone()
        if not case or case['run_id']!=parent['run_id'] or (case['park_id'],case['org_id'])!=(self.park_id,self.org_id) or not operation:
            raise Denied('original Case and verified create operation required')
        if p['role'] != 'service_executor': prep.scoped(self.store,c,p,id)
        if write and not stopping: prep.case_write_guard(c,parent)
        if not final:
            self._checks[c].append(lambda: self._parent(c,token,id,write=write,stopping=stopping,final=True,recipient_id=recipient_id))
        return p,parent

    def owns_notice(self,c,source):
        row=c.execute("SELECT e.payload FROM service_dispatch_events e WHERE e.dispatch_id=%s AND e.action='OFFER' ORDER BY e.revision LIMIT 1",(source['dispatch_id'],)).fetchone()
        try:
            binding=row['payload'][MARKER]['binding']
            return binding['contract']==self.contract and binding['contract_id']==self.contract_id
        except (KeyError,TypeError):return False

    def notice_source(self,c,source):
        # Structural proof before a consumer may terminally suppress intent.
        # Lock the parent first; no receipt lock precedes its parent.
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR SHARE',(source['preparation_id'],)).fetchone()
        if (not parent or parent['namespace']!='SYNTHETIC' or
                (parent['owner_id'],parent['reviewer_id'],parent['park_id'],parent['org_id'])!=
                (self.owner_id,self.reviewer_id,self.park_id,self.org_id)):
            raise Denied('original CaseStep notification parent required')
        root=self._root(c,parent)
        offer=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',(source['offer_id'],)).fetchone() if root else None
        historical=type(self) is _OrdinaryCaseStep and self.service.local_synthetic_demo is None
        if (not offer or root['id']!=source['dispatch_id'] or offer['dispatch_id']!=root['id']
                or offer['id']!=root['current_offer_id'] and not historical):
            raise Denied('exact original CaseStep notification required')
        event=c.execute('SELECT * FROM service_dispatch_events WHERE id=%s',(source['event_id'],)).fetchone()
        try:
            action=event['action'];payload=event['payload']
            offered=self._offered(c,offer)
            if action in ('OFFER','REOFFER'):
                first=c.execute('SELECT id FROM service_dispatch_events WHERE offer_id=%s ORDER BY revision LIMIT 1',(offer['id'],)).fetchone()
                if event['revision']!=offered['revision'] or not first or event['id']!=first['id']:raise ValueError('original OFFER event required')
                self._marker(c,parent,offer)
            elif action in ('ACCEPT','DECLINE','WITHDRAW'):
                if action=='DECLINE' and (event['revision']!=offered['revision']+1 or offer['state']!='DECLINED'):raise ValueError('original terminal decline required')
                if action=='WITHDRAW':
                    if offer['state']!='WITHDRAWN' or event['revision'] not in (offered['revision']+1,offered['revision']+2):raise ValueError('original withdrawal required')
                    if event['revision']==offered['revision']+2:self._accepted_step(c,parent,offer)
                step=self._accepted_step(c,parent,offer) if action=='ACCEPT' else None
                expected=dict(dispatch_id=str(root['id']),offer_id=str(offer['id']),revision=event['revision'],
                    action=action,state={'ACCEPT':'ACCEPTED','DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[action],
                    actor_id=event['actor_id'],executor_id=offer['executor_id'],receipt_step_id=str(step['id']) if step else None)
                original=sd.Command(action=action,expected_revision=event['revision']-1,reason=payload['reason'],**historical_fields(payload))
                if (event['actor_id']!=(self.reviewer_id if action=='WITHDRAW' else offer['executor_id'])
                        or not sd._typed_fields_equal(payload,expected)
                        or event['fingerprint']!=self._fp('DISPATCH_COMMAND',root['id'],original)):
                    raise ValueError('original notification command proof mismatch')
            else:raise ValueError('unknown CaseStep notification action')
            if (event['dispatch_id']!=root['id'] or event['offer_id']!=offer['id']
                    or event['revision']>root['revision'] or event['revision']!=source['revision']
                    or any(event[k]!=source[k] for k in ('action','actor_id','created_at'))
                    or source['executor_id']!=offer['executor_id']):
                raise ValueError('notification source mismatch')
        except (KeyError,TypeError,ValueError,AttributeError):
            raise Denied('original CaseStep notification proof required') from None
        return parent,root

    def notice_authority(self,c,p,source,*,final=False):
        p,parent=self._parent(c,None,source['preparation_id'],recipient_id=p['id'],final=final)
        _,root=self.notice_source(c,source)
        if p['role']=='service_executor':
            offer=self._own(c,p,parent,root,final=final)
            if source['offer_id']!=offer['id'] or source['executor_id']!=p['id']:
                raise Denied('notification belongs to a prior CaseStep offer')
        if not final:self._checks[c].append(lambda:self.notice_authority(c,p,source,final=True))
        return parent,root

    def notice_item(self,c,p,parent,root,source,item):
        offer=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',(source['offer_id'],)).fetchone()
        try:self._live(c,parent,offer,final=True);live=offer['state']=='OFFERED'
        except Denied:live=False
        item.update(assignment_contract=self.contract,run_access_granted=False,
            assignment_valid_until=self._marker(c,parent,offer)['valid_until'],
            actionable=item['actionable'] and live and p['role']=='service_executor',historical=item['historical'] or not live or offer['id']!=root['current_offer_id'])
        return item

    def _catalog(self,c,parent):
        row = c.execute('SELECT *,xmin::text generation FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
                        (parent['park_id'],parent['service_id'],parent['service_version'])).fetchone()
        if (not row or row['namespace'] != 'SYNTHETIC' or row['qualification'] != 'NOT_EVALUATED'
                or not isinstance(row['source'],dict) or row['source'].get('kind') != 'SYNTHETIC'):
            raise Denied('current original synthetic service required')
        from .catalog_publication import proof
        proof(row)
        return digest(prep.canonical(row))

    def _binding(self,c,parent,executor):
        generations = self._generations(c,(executor,))
        if executor not in self.executor_ids: raise Denied('configured existing executor required')
        return dict(contract=self.contract, contract_id=self.contract_id,
            preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            owner_id=self.owner_id,reviewer_id=self.reviewer_id,executor_id=executor,
            service_id=parent['service_id'],service_version=parent['service_version'],
            preparation_revision=parent['revision'],preparation_sha256=parent['review_sha256'],
            catalog_sha256=self._catalog(c,parent),generations={id:generations[id] for id in (self.owner_id,self.reviewer_id,executor)})

    def _offered(self,c,offer):
        return c.execute("SELECT * FROM service_dispatch_events WHERE offer_id=%s AND action IN ('OFFER','REOFFER') ORDER BY revision LIMIT 1",(offer['id'],)).fetchone()

    def _marker(self,c,parent,offer):
        from datetime import datetime
        import re
        row=self._offered(c,offer)
        try:
            marker=row['payload'][MARKER];binding=marker['binding']
            end=datetime.fromisoformat(marker['valid_until'])
            original=sd.Offer(expected_preparation_revision=offer['preparation_revision'],expected_dispatch_revision=row['revision']-1,
                              executor_id=offer['executor_id'],reason=offer['reason'],**historical_fields(row['payload']))
            expected=dict(dispatch_id=str(offer['dispatch_id']),offer_id=str(offer['id']),revision=row['revision'],
                action=row['action'],state='OFFERED',actor_id=self.reviewer_id,executor_id=offer['executor_id'],
                reason=offer['reason'],receipt_step_id=None)
            if (type(marker) is not dict or set(marker)!={'binding','valid_until'} or type(binding) is not dict
                    or set(binding)!={'contract','contract_id','preparation_id','case_id','run_id','owner_id','reviewer_id','executor_id','service_id','service_version','preparation_revision','preparation_sha256','catalog_sha256','generations'}
                    or binding['contract']!=self.contract or binding['contract_id']!=self.contract_id
                    or any(binding[k]!=str(parent[v]) for k,v in (('preparation_id','id'),('case_id','case_id'),('run_id','run_id')))
                    or (binding['owner_id'],binding['reviewer_id'],binding['executor_id'])!=(self.owner_id,self.reviewer_id,offer['executor_id'])
                    or (binding['preparation_revision'],binding['preparation_sha256'])!=(offer['preparation_revision'],offer['preparation_sha256'])
                    or type(binding['preparation_revision']) is not int or type(binding['service_version']) is not int
                    or binding['service_version']<1 or type(binding['service_id']) is not str or not binding['service_id']
                    or any(type(binding[k]) is not str or not re.fullmatch('[0-9a-f]{64}',binding[k]) for k in ('preparation_sha256','catalog_sha256'))
                    or row['action']=='OFFER' and row['revision']!=1 or row['actor_id']!=self.reviewer_id
                    or row['dispatch_id']!=offer['dispatch_id'] or not sd._typed_fields_equal(row['payload'],expected)
                    or row['fingerprint']!=self._fp('OFFER',parent['id'],original)
                    or end.tzinfo is None or (self.valid_until is not None and end>self.valid_until) or end>row['created_at']+timedelta(seconds=self.offer_seconds)
                    or end<=row['created_at']):
                raise ValueError('invalid original marker')
            generations=binding['generations']
            if type(generations) is not dict or set(generations)!={self.owner_id,self.reviewer_id,offer['executor_id']}:
                raise ValueError('invalid original participant generations')
            for id,keys in ((self.owner_id,{'principal','READ','EXECUTE','PREPARE'}),
                            (self.reviewer_id,{'principal','READ','REVIEW_ASSIGNED'}),
                            (offer['executor_id'],{'principal','READ'})):
                g=generations[id]
                if type(g) is not dict or set(g)!=keys or any(type(v) is not str or not re.fullmatch('[0-9]{1,20}',v) for v in g.values()):
                    raise ValueError('invalid original authorization generation')
            if row['action']=='REOFFER':self._check_reoffer_prefix(c,parent,offer,row,marker)
            return marker
        except (KeyError,TypeError,ValueError,AttributeError):
            raise Denied('original CaseStep offer proof required') from None

    def _live(self,c,parent,offer,*,final=False):
        from datetime import datetime
        marker = self._marker(c,parent,offer)
        if (prep.canonical(marker['binding']) != prep.canonical(self._binding(c,parent,offer['executor_id']))
                or _now(c) >= datetime.fromisoformat(marker['valid_until'])
                or not er.material_current(c,parent,self.store) or prep.case_write_blocked(c,parent)):
            raise Denied('CaseStep expired, changed or revoked; no fallback')
        if not final:
            self._checks[c].append(lambda: self._live(c,parent,offer,final=True))
        return marker

    def _root(self,c,parent,write=False):
        root = sd._root(c,parent,write)
        if root:
            for offer in c.execute('SELECT * FROM service_dispatch_offers WHERE dispatch_id=%s',(root['id'],)).fetchall(): self._marker(c,parent,offer)
        elif c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s',(parent['id'],)).fetchone():
            raise Denied('legacy receipt cannot become CaseStep assignment')
        return root

    def _own(self,c,p,parent,root,*,final=False):
        if not root: raise Denied('explicit CaseStep offer required')
        offer = sd._own_offer(c,p,root)
        if not offer or offer['id'] != root['current_offer_id'] or offer['state'] not in ('OFFERED','ACCEPTED'):
            raise Denied('current own CaseStep offer required')
        self._live(c,parent,offer,final=final)
        return offer

    def _dispatch_view(self,c,p,parent,root,event=None,*,terminal=False):
        if p['role'] == 'service_executor' and not terminal: self._own(c,p,parent,root)
        x = sd._view(c,p,parent,root,event,self.store)
        x.update(goal=TITLE,assignment_contract=self.contract,run_access_granted=False,
                 can_withdraw=bool(root and p['role']=='park_specialist' and x['current_offer']['state'] in ('OFFERED','ACCEPTED')))
        x['can_reoffer'] = False
        if root:
            try: marker=self._live(c,parent,x['current_offer'],final=True);live=True
            except Denied: marker=self._marker(c,parent,x['current_offer']);live=False
            x['assignment_valid_until']=marker['valid_until']
            x['can_accept']=x['can_accept'] and live
            x['dependency']='CURRENT' if live and x['current_offer']['state'] in ('OFFERED','ACCEPTED') else 'DEPENDENCY_CHANGED'
        if x['event']:x['event']={k:v for k,v in x['event'].items() if k != MARKER}
        for e in x['history']: e['payload']={k:v for k,v in e['payload'].items() if k != MARKER}
        return x

    def read_preparation(self,store,token,id):
        with self._connection(store) as c:
            p,parent=self._parent(c,token,id);root=self._root(c,parent)
            return self._dispatch_view(c,p,parent,root)

    def read_dispatch(self,store,token,id):
        with self._connection(store) as c:
            base=c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s',(id,)).fetchone()
            if not base: raise Denied('CaseStep unavailable')
            p,parent=self._parent(c,token,base['preparation_id']);root=self._root(c,parent)
            return self._dispatch_view(c,p,parent,root)

    def catalog(self,store,token,id):
        with self._connection(store) as c:
            p,parent=self._parent(c,token,id)
            if p['role']!='park_specialist': raise Denied('responsible CaseStep specialist required')
            root=self._root(c,parent)
            previous=self._reoffer_predecessor(c,parent,root) if root else None
            if not root or previous:self._generations(c);self._catalog(c,parent)
            current=sd._own_offer(c,p,root) if root else None
            existing=bool(c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s',(id,)).fetchone())
            executors=[x for x in self.executor_ids if not previous or x!=current['executor_id']]
            ready=er.material_current(c,parent,store) and not prep.case_write_blocked(c,parent) and (not root or bool(previous)) and self._receipt_history_empty(c,parent,root) and bool(executors)
            return dict(scope=sd.SCOPE,assignment_contract=self.contract,run_access_granted=False,
                preparation_revision=parent['revision'],dispatch_revision=root['revision'] if root else 0,
                ready=ready,executors=[dict(id=x) for x in executors] if not root or previous else [],has_receipt_step=existing,
                can_reassign=False,can_reoffer=False,history_limit_reached=bool(root and root['revision']>=(61 if type(self) is _OrdinaryCaseStep and self.service.local_synthetic_demo is None else 63)),
                **(dict(can_offer_again=bool(previous and ready),offer_again_kind='WITHDRAWN_ZERO_RECEIPT' if previous and existing else 'UNACCEPTED_TERMINAL' if previous else None) if type(self) is _OrdinaryCaseStep and self.service.local_synthetic_demo is None else {}),
                offer_seconds=self.offer_seconds,authority_valid_until=self.valid_until)

    def _offer_deadline(self,c):
        end=_now(c)+timedelta(seconds=self.offer_seconds)
        return min(end,self.valid_until) if self.valid_until is not None else end

    def offer(self,store,token,id,key,data):
        if type(data) is not sd.Offer or data.recovery_receipt_step_id is not None: raise Denied('initial CaseStep offer only')
        fp=self._fp('OFFER',id,data)
        with self._connection(store) as c:
            p,parent=self._parent(c,token,id,write=True)
            if p['role']!='park_specialist': raise Denied('responsible CaseStep specialist required')
            sd._key(c,p,key);root=self._root(c,parent,True)
            marker=dict(binding=self._binding(c,parent,data.executor_id),valid_until=self._offer_deadline(c).isoformat())
            old=sd._replay(c,p,key,fp,root)
            if old:
                if old.get('offer_id')!=str(root['current_offer_id']):raise Conflict('original key belongs to a prior or unverified CaseStep offer')
                return self._dispatch_view(c,p,parent,root,old)
            from .business_frontier import check_fence
            from .controlled_plans import gate
            check_fence(c,parent,data);gate(store,c,parent,2,observe=False)
            if not er.material_current(c,parent,store) or parent['revision']!=data.expected_preparation_revision: raise Conflict('current confirmed preparation required')
            if (root['revision'] if root else 0)!=data.expected_dispatch_revision: raise Conflict('stale CaseStep dispatch revision')
            if not self._receipt_history_empty(c,parent,root): raise Conflict('accepted CaseStep without proven empty history cannot be renewed')
            if root:
                previous=self._reoffer_predecessor(c,parent,root)
                if previous is None:raise Conflict('original terminal CaseStep and unchanged deadline required')
                current=sd._own_offer(c,p,root)
                if current['executor_id']==data.executor_id:raise Conflict('explicit different existing executor required')
                marker['valid_until']=previous['valid_until']
            oid=uuid4();action='REOFFER' if root else 'OFFER'
            if root: root=c.execute('UPDATE service_dispatches SET revision=revision+1,current_offer_id=%s WHERE id=%s RETURNING *',(oid,root['id'])).fetchone()
            else: root=c.execute('INSERT INTO service_dispatches(id,preparation_id,revision,current_offer_id) VALUES(%s,%s,1,%s) RETURNING *',(uuid4(),id,oid)).fetchone()
            offer=c.execute("INSERT INTO service_dispatch_offers(id,dispatch_id,executor_id,preparation_revision,preparation_sha256,reason,state) VALUES(%s,%s,%s,%s,%s,%s,'OFFERED') RETURNING *",(oid,root['id'],data.executor_id,parent['revision'],parent['review_sha256'],data.reason)).fetchone()
            event=sd._event(c,p,root,offer,key,fp,action,data.reason,**{MARKER:marker})
            self._live(c,parent,offer)
            return self._dispatch_view(c,p,parent,root,event)

    def dispatch_command(self,store,token,id,key,data):
        if type(data) is not sd.Command: raise Denied('typed CaseStep decision required')
        fp=self._fp('DISPATCH_COMMAND',id,data)
        with self._connection(store) as c:
            base=c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s',(id,)).fetchone()
            if not base: raise Denied('CaseStep unavailable')
            p,parent=self._parent(c,token,base['preparation_id'],write=True,stopping=data.action=='WITHDRAW')
            if p['role']!=('park_specialist' if data.action=='WITHDRAW' else 'service_executor'): raise Denied('own CaseStep decision required')
            sd._key(c,p,key);root=self._root(c,parent,True);offer=sd._own_offer(c,p,root)
            if data.action!='WITHDRAW': self._own(c,p,parent,root)
            else: prep.grant(store,c,p,'REVIEW_ASSIGNED')
            old=sd._replay(c,p,key,fp,root)
            if old:
                if old.get('offer_id')!=str(root['current_offer_id']):raise Conflict('original key belongs to a prior or unverified CaseStep offer')
                return self._dispatch_view(c,p,parent,root,old)
            from .business_frontier import check_fence
            check_fence(c,parent,data)
            allowed=('OFFERED','ACCEPTED') if data.action=='WITHDRAW' else ('OFFERED',)
            if not offer or offer['id']!=root['current_offer_id'] or offer['state'] not in allowed: raise Conflict('current CaseStep decision required')
            if root['revision']!=data.expected_revision or root['revision']>=64: raise Conflict('stale or bounded CaseStep revision')
            step_id=offer['receipt_step_id']
            if data.action=='ACCEPT':
                from .controlled_plans import gate
                gate(store,c,parent,2,observe=False)
                if not self._receipt_history_empty(c,parent,root): raise Conflict('CaseStep receipt already exists without proven empty history')
                step=er._insert_step(c,parent,p['id']);step_id=step['id']
                er._event(c,p,step,'dispatch-accept:'+str(offer['id']),fp,'CREATE',dispatch_id=str(id),offer_id=str(offer['id']),reason=data.reason)
            state={'ACCEPT':'ACCEPTED','DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[data.action]
            if state!='ACCEPTED':step_id=None
            offer=c.execute('UPDATE service_dispatch_offers SET state=%s,receipt_step_id=%s WHERE id=%s RETURNING *',(state,step_id,offer['id'])).fetchone()
            root=c.execute('UPDATE service_dispatches SET revision=revision+1 WHERE id=%s RETURNING *',(id,)).fetchone()
            event=sd._event(c,p,root,offer,key,fp,data.action,data.reason)
            if data.action=='ACCEPT':self._live(c,parent,offer)
            return self._dispatch_view(c,p,parent,root,event,terminal=data.action=='DECLINE')

    def _accepted_step(self,c,parent,offer):
        try:
            accepted=c.execute("SELECT * FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT'",(offer['id'],)).fetchall()
            if len(accepted)!=1:raise ValueError('unique original acceptance required')
            accepted=accepted[0];payload=accepted['payload'];id=UUID(payload['receipt_step_id'])
            row=er._locked(c,id)
            created=c.execute("SELECT * FROM service_receipt_events WHERE step_id=%s AND action='CREATE'",(id,)).fetchall()
            original=sd.Command(action='ACCEPT',expected_revision=accepted['revision']-1,reason=payload['reason'],**historical_fields(payload))
            expected=dict(dispatch_id=str(offer['dispatch_id']),offer_id=str(offer['id']),revision=accepted['revision'],action='ACCEPT',state='ACCEPTED',actor_id=offer['executor_id'],executor_id=offer['executor_id'],receipt_step_id=str(id))
            if (not row or len(created)!=1 or accepted['actor_id']!=offer['executor_id']
                    or accepted['dispatch_id']!=offer['dispatch_id'] or accepted['revision']!=self._offered(c,offer)['revision']+1
                    or row['namespace']!='SYNTHETIC' or offer['state'] not in ('ACCEPTED','WITHDRAWN')
                    or (offer['state']=='ACCEPTED' and offer['receipt_step_id']!=id)
                    or not sd._typed_fields_equal(payload,expected) or accepted['fingerprint']!=self._fp('DISPATCH_COMMAND',offer['dispatch_id'],original)
                    or any(row[k]!=parent[k] for k in ('run_id','case_id','owner_id','park_id','org_id','service_id','service_version'))
                    or row['preparation_id']!=parent['id'] or row['executor_id']!=offer['executor_id']
                    or row['preparation_revision']!=offer['preparation_revision'] or row['preparation_sha256']!=offer['preparation_sha256']
                    or created[0]['actor_id']!=offer['executor_id'] or created[0]['revision']!=1
                    or created[0]['request_key']!='dispatch-accept:'+str(offer['id']) or created[0]['fingerprint']!=accepted['fingerprint']
                    or not sd._typed_fields_equal(created[0]['payload'],dict(step_id=str(id),revision=1,state='AWAITING_RECEIPT',action='CREATE',actor_id=offer['executor_id'],scope=er.SCOPE,dispatch_id=str(offer['dispatch_id']),offer_id=str(offer['id']),reason=payload['reason']))):
                raise ValueError('acceptance/receipt CREATE mismatch')
            return row
        except (KeyError,TypeError,ValueError,AttributeError):
            raise Denied('original CaseStep acceptance and receipt proof required') from None

    def _receipt_context(self,c,token,id,write=False):
        base=c.execute('SELECT preparation_id FROM service_receipt_steps WHERE id=%s',(id,)).fetchone()
        if not base:raise Denied('CaseStep receipt unavailable')
        p,parent=self._parent(c,token,base['preparation_id'],write=write)
        if p['role'] not in ('enterprise_operator','service_executor'): raise Denied('CaseStep receipt party required')
        root=self._root(c,parent);offer=sd._own_offer(c,p,root)
        row=er._locked(c,id,write)
        original=self._accepted_step(c,parent,offer)
        if original['id']!=id:raise Denied('exact CaseStep receipt required')
        if p['role']=='service_executor':self._own(c,p,parent,root)
        return p,parent,root,offer,row

    def _receipt_view(self,c,p,parent,root,offer,row,event=None):
        x=er._view(c,p,row,parent,event,self.store)
        try:self._live(c,parent,offer,final=True);live=offer['state']=='ACCEPTED'
        except Denied:live=False
        x.update(assignment_contract=self.contract,run_access_granted=False,assignment_valid_until=self._marker(c,parent,offer)['valid_until'],
                 dependency='CURRENT' if live else 'DEPENDENCY_CHANGED',can_submit=x['can_submit'] and live)
        x['step']={k:v for k,v in row.items() if k in ('id','preparation_id','case_id','run_id','executor_id','service_id','service_version','preparation_revision','preparation_sha256','state','revision','namespace')}
        x['step']['goal']=TITLE
        x['local_execution']={'enabled':False,'can_execute':False,'current':False,'requires_adapter':False,'record':None}
        return x

    def read_receipt(self,store,token,id):
        with self._connection(store) as c:
            p,parent,root,offer,row=self._receipt_context(c,token,id)
            return self._receipt_view(c,p,parent,root,offer,row)

    def receipt_command(self,store,token,id,key,data):
        if type(data) is not er.Command:raise Denied('manual CaseStep receipt only')
        fp=self._fp('RECEIPT_COMMAND',id,data)
        with self._connection(store) as c:
            p,parent,root,offer,row=self._receipt_context(c,token,id,True)
            if p['role']!=('service_executor' if data.action=='SUBMIT' else 'enterprise_operator'):raise Denied('original CaseStep receipt party required')
            if p['role']=='enterprise_operator':store.check_capability(c,p,'EXECUTE')
            er._key(c,p,key);self._live(c,parent,offer)
            if offer['state']!='ACCEPTED':raise Denied('accepted CaseStep required')
            old=er._replay(c,p,key,fp)
            if old:return self._receipt_view(c,p,parent,root,offer,row,old)
            from .business_frontier import check_fence
            from .controlled_plans import gate
            check_fence(c,parent,data);gate(store,c,parent,2,observe=False)
            if row['revision']!=data.expected_revision or row['revision']>=64:raise Conflict('stale or bounded CaseStep receipt revision')
            current=er._current(c,row);current_id=row['current_receipt_id']
            if data.action=='SUBMIT':
                if row['state'] not in ('AWAITING_RECEIPT','CHANGES_REQUESTED'):raise Conflict('CaseStep not awaiting receipt')
                receipt=c.execute("INSERT INTO service_step_receipts(id,step_id,version,text,source_kind,source_label,source_sha256,actor_id) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,%s) RETURNING *",(uuid4(),id,(current['version'] if current else 0)+1,data.text,data.source_label,digest(data.text),p['id'])).fetchone()
                current_id=receipt['id'];state='RECEIPT_RECORDED'
            else:
                if not current or data.receipt_sha256!=current['source_sha256']:raise Conflict('current CaseStep receipt hash required')
                if data.action in ('ACKNOWLEDGE','REQUEST_CHANGES'):
                    if row['state']!='RECEIPT_RECORDED':raise Conflict('recorded CaseStep receipt required')
                    state='LOCAL_ACKNOWLEDGED' if data.action=='ACKNOWLEDGE' else 'CHANGES_REQUESTED'
                else:
                    if row['state'] not in ('RECEIPT_RECORDED','LOCAL_ACKNOWLEDGED'):raise Conflict('recorded CaseStep receipt required')
                    state='AWAITING_RECEIPT'
            row=c.execute('UPDATE service_receipt_steps SET state=%s,revision=revision+1,current_receipt_id=%s WHERE id=%s RETURNING *',(state,current_id,id)).fetchone()
            event=er._event(c,p,row,key,fp,data.action,receipt_id=str(current_id),receipt_sha256=er._current(c,row)['source_sha256'],reason=data.reason)
            self._live(c,parent,offer)
            return self._receipt_view(c,p,parent,root,offer,row,event)

    def receipt_catalog(self,store,token,id):
        with self._connection(store) as c:
            p,parent=self._parent(c,token,id)
            if p['role']!='enterprise_operator':raise Denied('CaseStep owner required')
            return dict(scope=er.SCOPE,preparation_revision=parent['revision'],ready=False,executors=[],assignment_contract=self.contract)

    def _list(self,store,token,receipts=False):
        with self._connection(store) as c:
            p=sd._auth(store,c,token)
            if p['id'] not in (self.owner_id,self.reviewer_id,*self.executor_ids):raise Denied('CaseStep participant required')
            rows=c.execute('SELECT id,preparation_id FROM service_dispatches ORDER BY created_at DESC,id DESC LIMIT 101').fetchall()
            items=[]
            for base in rows[:100]:
                try:
                    _,parent=self._parent(c,token,base['preparation_id']);root=self._root(c,parent)
                    if p['role']=='service_executor':offer=self._own(c,p,parent,root)
                    else:offer=sd._own_offer(c,p,root)
                    if receipts:
                        if p['role']=='park_specialist':continue
                        s=self._accepted_step(c,parent,offer);items.append(dict(id=s['id'],goal=TITLE,state=s['state'],revision=s['revision'],case_cancelled=prep.case_cancelled(c,parent),case_reconciling=False,case_write_blocked=prep.case_write_blocked(c,parent)))
                    else:items.append(dict(id=root['id'],preparation_id=parent['id'],goal=TITLE))
                except (Denied,Conflict):continue
            return dict(scope=er.SCOPE if receipts else sd.SCOPE,role=p['role'],items=items,has_older_records=len(rows)>100,access_filtered=min(len(rows),100)-len(items),assignment_contract=self.contract)

    def list_dispatches(self,store,token):return self._list(store,token)
    def list_receipts(self,store,token):return self._list(store,token,True)

    def recover_accept(self,store,token,id,key,selection):
        if type(selection) is not sd.AcceptRecoverySelection:raise Denied('typed CaseStep acceptance selection required')
        with self._connection(store) as c:
            p,parent=self._parent(c,token,selection.preparation_id);root=self._root(c,parent)
            if p['role']!='service_executor' or not root or root['id']!=id:raise Denied('own CaseStep required')
            sd._key(c,p,key);offer=self._own(c,p,parent,root)
            if (parent['case_id']!=selection.case_id or parent['run_id']!=selection.run_id or offer['id']!=selection.offer_id or offer['preparation_revision']!=selection.preparation_revision):raise Denied('exact CaseStep selection required')
            if selection.expected_revision!=self._offered(c,offer)['revision']:raise Conflict('original CaseStep OFFER revision required')
            old=c.execute('SELECT * FROM service_dispatch_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone();event=None
            if old:
                try:
                    original=sd.Command(action='ACCEPT',expected_revision=selection.expected_revision,reason=old['payload']['reason'],**historical_fields(old['payload']))
                    step=self._accepted_step(c,parent,offer)
                    expected=dict(dispatch_id=str(id),offer_id=str(offer['id']),revision=selection.expected_revision+1,action='ACCEPT',state='ACCEPTED',actor_id=p['id'],executor_id=p['id'],receipt_step_id=str(step['id']))
                    if (step['id']!=offer['receipt_step_id'] or old['dispatch_id']!=id or old['offer_id']!=offer['id'] or old['action']!='ACCEPT' or old['revision']!=selection.expected_revision+1 or old['revision']>root['revision'] or not sd._typed_fields_equal(old['payload'],expected) or old['fingerprint']!=self._fp('DISPATCH_COMMAND',id,original)):raise ValueError('proof mismatch')
                except (KeyError,TypeError,ValueError,AttributeError):
                    raise Conflict('CaseStep acceptance proof mismatch') from None
                event=dict(id=str(old['id']),action='ACCEPT',revision=old['revision'],receipt_step_id=str(offer['receipt_step_id']))
            self._live(c,parent,offer)
            return dict(scope=sd.SCOPE,actor_ref=digest(prep.canonical(dict(actor_id=p['id']))),dispatch_id=str(id),**{k:str(getattr(selection,k)) for k in ('preparation_id','case_id','run_id','offer_id')},expected_revision=selection.expected_revision,preparation_revision=selection.preparation_revision,request_key=key,status='COMMITTED' if old else 'NOT_OBSERVED',event=event,historical_only=True,read_only=True,automatically_replayed=False,case_goal_completed=False)

    def recover_submit(self,store,token,id,key,selection):
        if type(selection) is not er.SubmitRecoverySelection:raise Denied('typed CaseStep submit selection required')
        with self._connection(store) as c:
            p,parent,root,offer,row=self._receipt_context(c,token,id)
            if p['role']!='service_executor':raise Denied('own CaseStep submit required')
            er._key(c,p,key)
            if (parent['id']!=selection.preparation_id or parent['case_id']!=selection.case_id or parent['run_id']!=selection.run_id or row['preparation_revision']!=selection.preparation_revision):raise Denied('exact CaseStep submission selection required')
            if selection.expected_revision>row['revision']:raise Conflict('original CaseStep submission revision required')
            old=c.execute('SELECT * FROM service_receipt_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone();event=None
            if old:
                try:
                    payload=old['payload'];r=c.execute('SELECT * FROM service_step_receipts WHERE id=%s AND step_id=%s',(UUID(payload['receipt_id']),id)).fetchone()
                    expected=dict(step_id=str(id),revision=selection.expected_revision+1,state='RECEIPT_RECORDED',action='SUBMIT',actor_id=p['id'],scope=er.SCOPE,reason=None)
                    if not r:raise ValueError('receipt missing')
                    original=er.Command(action='SUBMIT',expected_revision=selection.expected_revision,text=r['text'],source_kind=r['source_kind'],source_label=r['source_label'],**historical_fields(payload))
                    if (old['step_id']!=id or old['action']!='SUBMIT' or old['revision']!=selection.expected_revision+1 or old['revision']>row['revision'] or not sd._typed_fields_equal(payload,expected) or payload['receipt_id']!=str(r['id']) or r['source_kind']!='SYNTHETIC' or 'adapter_execution' in payload or 'record_mode' in payload or r.get('adapter_execution') is not None or r['actor_id']!=p['id'] or digest(r['text'])!=r['source_sha256'] or payload.get('receipt_sha256')!=r['source_sha256'] or r['version']!=c.execute("SELECT count(*) n FROM service_receipt_events WHERE step_id=%s AND action='SUBMIT' AND revision<=%s",(id,old['revision'])).fetchone()['n'] or old['fingerprint']!=self._fp('RECEIPT_COMMAND',id,original)):raise ValueError('proof mismatch')
                except (KeyError,TypeError,ValueError,AttributeError):
                    raise Conflict('CaseStep original submission proof mismatch') from None
                event=dict(id=str(old['id']),action='SUBMIT',revision=old['revision'],receipt_id=str(r['id']),receipt_version=r['version'],receipt_sha256=r['source_sha256'])
            self._live(c,parent,offer)
            return dict(scope=er.SCOPE,actor_ref=digest(prep.canonical(dict(actor_id=p['id']))),step_id=str(id),**{k:str(getattr(selection,k)) for k in ('preparation_id','case_id','run_id')},expected_revision=selection.expected_revision,preparation_revision=selection.preparation_revision,request_key=key,status='COMMITTED' if old else 'NOT_OBSERVED',event=event,historical_only=True,read_only=True,automatically_replayed=False,case_goal_completed=False)



class IsolatedCaseStepAssignments(_CaseStepTransactions):
    """Original fresh-owned, in-process fixture admission; never ordinary startup."""


class _OrdinaryCaseStep(_CaseStepTransactions):
    """Per-operation context from existing rows; not an authority issuer."""
    contract=ORDINARY_CONTRACT

    def __init__(self, service, parent, executors):
        self.service,self.store=service,service.store
        self.owner_id,self.reviewer_id=parent['owner_id'],parent['reviewer_id']
        self.park_id,self.org_id=parent['park_id'],parent['org_id']
        self.executor_ids=tuple(executors)
        self.contract_id=str(parent['id'])
        self.offer_seconds=300
        self.valid_until=None
        self.tainted_runs=None
        self._checks=service._checks

    def _connection(self,store):return self.service._connection(store)

    def _pending_step_empty(self,c,step):
        # A recorded/reopened result never becomes an empty step again.
        return (type(step['revision']) is int and step['revision']==1
            and step['state']=='AWAITING_RECEIPT' and step['current_receipt_id'] is None
            and not c.execute('SELECT 1 FROM service_step_receipts WHERE step_id=%s',(step['id'],)).fetchone()
            and not c.execute("SELECT 1 FROM service_receipt_events WHERE step_id=%s AND action<>'CREATE'",(step['id'],)).fetchone())

    def _terminal_marker(self,c,parent,offer,revision):
        try:
            events=c.execute('SELECT * FROM service_dispatch_events WHERE offer_id=%s ORDER BY revision LIMIT 4',
                             (offer['id'],)).fetchall()
            origin=self._offered(c,offer)
            accepted=len(events)==3
            if (not origin or type(revision) is not int or not 2<=revision<=62
                    or len(events) not in (2,3) or events[0]['id']!=origin['id']
                    or [e['revision'] for e in events]!=list(range(origin['revision'],revision+1))
                    or any(type(e['revision']) is not int or e['dispatch_id']!=offer['dispatch_id'] for e in events)
                    or events[-1]['action'] not in ('DECLINE','WITHDRAW')
                    or offer['receipt_step_id'] is not None
                    or offer['state']!={'DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[events[-1]['action']]):
                raise ValueError('original adjacent terminal predecessor required')
            terminal=events[-1]
            if accepted:
                if terminal['action']!='WITHDRAW' or events[1]['action']!='ACCEPT':
                    raise ValueError('accepted predecessor requires explicit withdrawal')
                step=self._accepted_step(c,parent,offer)
                if not self._pending_step_empty(c,step):raise ValueError('original receipt must have no submission history')
            expected=dict(dispatch_id=str(offer['dispatch_id']),offer_id=str(offer['id']),revision=revision,
                action=terminal['action'],state=offer['state'],actor_id=self.reviewer_id if terminal['action']=='WITHDRAW' else offer['executor_id'],
                executor_id=offer['executor_id'],receipt_step_id=None)
            original=sd.Command(action=terminal['action'],expected_revision=revision-1,
                                reason=terminal['payload']['reason'],**historical_fields(terminal['payload']))
            if (terminal['actor_id']!=expected['actor_id'] or not sd._typed_fields_equal(terminal['payload'],expected)
                    or terminal['fingerprint']!=self._fp('DISPATCH_COMMAND',offer['dispatch_id'],original)
                    or any(a['created_at']>b['created_at'] for a,b in zip(events,events[1:]))):
                raise ValueError('original predecessor command proof required')
            return self._marker(c,parent,offer),terminal
        except (KeyError,TypeError,ValueError,AttributeError):
            raise Denied('ordinary terminal CaseStep proof required') from None

    def _receipt_history_empty(self,c,parent,root):
        if self.service.local_synthetic_demo is not None:
            return super()._receipt_history_empty(c,parent,root)
        rows=c.execute('SELECT id FROM service_receipt_steps WHERE preparation_id=%s ORDER BY id LIMIT 32',(parent['id'],)).fetchall()
        if not rows:return True
        if not root or len(rows)>31:return False
        expected=set()
        offers=c.execute("SELECT o.* FROM service_dispatch_offers o WHERE o.dispatch_id=%s AND EXISTS(SELECT 1 FROM service_dispatch_events e WHERE e.offer_id=o.id AND e.action='ACCEPT') ORDER BY o.id LIMIT 32",(root['id'],)).fetchall()
        if len(offers)>31:return False
        for offer in offers:
            if offer['state']!='WITHDRAWN':return False
            origin=self._offered(c,offer)
            if not origin:return False
            self._terminal_marker(c,parent,offer,origin['revision']+2)
            step=self._accepted_step(c,parent,offer)
            if step['id'] in expected or not self._pending_step_empty(c,step):return False
            expected.add(step['id'])
        return expected=={r['id'] for r in rows}

    def _check_reoffer_prefix(self,c,parent,offer,event,marker):
        """Prove each terminal predecessor; no current old-executor authority."""
        try:
            if (type(self) is not _OrdinaryCaseStep or self.service.local_synthetic_demo is not None
                    or type(event['revision']) is not int or not 3<=event['revision']<=61):
                raise ValueError('ordinary bounded terminal generation required')
            previous=c.execute('SELECT offer_id FROM service_dispatch_events WHERE dispatch_id=%s AND revision=%s',
                               (offer['dispatch_id'],event['revision']-1)).fetchone()
            prior=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',
                            (previous['offer_id'],)).fetchone() if previous else None
            origin=self._offered(c,prior) if prior else None
            if (not prior or not origin or origin['revision'] not in (event['revision']-2,event['revision']-3)
                    or prior['dispatch_id']!=offer['dispatch_id'] or prior['executor_id']==offer['executor_id']):
                raise ValueError('adjacent different original executor required')
            previous_marker,terminal=self._terminal_marker(c,parent,prior,event['revision']-1)
            binding,previous_binding=marker['binding'],previous_marker['binding']
            frozen=('contract','contract_id','preparation_id','case_id','run_id','owner_id','reviewer_id',
                    'service_id','service_version','preparation_revision','preparation_sha256','catalog_sha256')
            if (marker['valid_until']!=previous_marker['valid_until'] or terminal['created_at']>event['created_at']
                    or any(binding[k]!=previous_binding[k] for k in frozen)
                    or any(binding['generations'][id]!=previous_binding['generations'][id] for id in (self.owner_id,self.reviewer_id))):
                raise ValueError('original predecessor source, authority and deadline required')
        except (KeyError,TypeError,ValueError,AttributeError):
            raise Denied('ordinary terminal CaseStep prefix proof required') from None

    def _reoffer_predecessor(self,c,parent,root):
        if (self.service.local_synthetic_demo is not None or not root or root['revision']>60):
            return None
        offer=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',(root['current_offer_id'],)).fetchone()
        if not offer or offer['state'] not in ('DECLINED','WITHDRAWN'):return None
        marker,_=self._terminal_marker(c,parent,offer,root['revision'])
        if not self._receipt_history_empty(c,parent,root):return None
        binding=marker['binding'];generations=self._generations(c,())
        if (binding['preparation_revision']!=parent['revision'] or binding['preparation_sha256']!=parent['review_sha256']
                or binding['catalog_sha256']!=self._catalog(c,parent)
                or any(binding['generations'][id]!=generations[id] for id in (self.owner_id,self.reviewer_id))):
            return None
        from datetime import datetime
        return marker if _now(c)<datetime.fromisoformat(marker['valid_until']) else None


class OrdinaryCaseStepAssignments:
    """Ordinary business routing; every operation rechecks existing rights.

    The durable first OFFER supplies the immutable deadline and source proof.
    No fixture issuer, participant configuration, startup expiry or new Grant.
    """
    contract=ORDINARY_CONTRACT
    contract_id=None

    def __init__(self,store,*,local_synthetic_demo=None):
        if type(store) is not Store or store.mode!='LOCAL':raise Denied('ordinary LOCAL CaseStep store required')
        self.store=store
        self.local_synthetic_demo=local_synthetic_demo
        if local_synthetic_demo is not None:
            from .local_synthetic_demo import LocalSyntheticDemo,LocalDemoCatalog,LocalDemoSelector
            if (type(local_synthetic_demo) is not LocalSyntheticDemo
                    or type(local_synthetic_demo.catalog) is not LocalDemoCatalog
                    or type(local_synthetic_demo.selector) is not LocalDemoSelector
                    or local_synthetic_demo.catalog.store is not store
                    or getattr(store,'_local_synthetic_demo_catalog',None) not in (None,local_synthetic_demo.catalog)):
                raise Denied('exact same-Store local demo CaseStep pair required')
            store._local_synthetic_demo_catalog=local_synthetic_demo.catalog
        self._checks={}
        _CaseStepTransactions._surfaces(self)
        self.validate(store)

    def validate(self,store):
        if type(self) is not OrdinaryCaseStepAssignments or store is not self.store:
            raise Denied('exact ordinary CaseStep service required')
        with self._connection(store):pass

    @contextmanager
    def _connection(self,store):
        if store is not self.store:raise Denied('ordinary CaseStep store binding required')
        _CaseStepTransactions._unmixed(self)
        with store.connect() as c:
            c.execute("SET LOCAL lock_timeout='3s'")
            if c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] not in (32,33):
                raise Denied('preinstalled ordinary CaseStep business schema required')
            if self.local_synthetic_demo is not None:self.local_synthetic_demo.catalog.validate(c)
            self._checks[c]=[]
            try:
                yield c
                for check in self._checks[c]:check()
                if self.local_synthetic_demo is not None:self.local_synthetic_demo.catalog.validate(c)
                _CaseStepTransactions._unmixed(self)
            finally:self._checks.pop(c,None)

    def _context(self,c,id,executor=None,*,catalog=False):
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(id,)).fetchone()
        if not parent:raise Denied('CaseStep unavailable')
        demo_executor=None
        if self.local_synthetic_demo is not None:
            value=self.local_synthetic_demo.catalog.validate(c,parent)
            demo_executor=value['roles']['service_executor']
            if c in self._checks:
                self._checks[c].append(lambda:self.local_synthetic_demo.catalog.validate(c,parent))
        if catalog:
            executors=[r['id'] for r in c.execute("SELECT p.id FROM principals p JOIN capability_grants g ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id AND g.capability='READ' AND g.active WHERE p.park_id=%s AND p.org_id=%s AND p.role='service_executor' AND p.active ORDER BY p.id LIMIT 100",(parent['park_id'],parent['org_id']))]
        elif executor is not None:executors=[executor]
        else:
            executors=[r['executor_id'] for r in c.execute('SELECT o.executor_id FROM service_dispatch_offers o JOIN service_dispatches d ON d.id=o.dispatch_id WHERE d.preparation_id=%s',(id,))]
        if demo_executor is not None:
            if catalog:executors=[id for id in executors if id==demo_executor]
            elif any(id!=demo_executor for id in executors):
                raise Denied('existing exact local demo executor mapping required')
        return _OrdinaryCaseStep(self,parent,executors)

    def _call(self,method,store,token,id,*args):
        # This lookup only chooses a context. The original transaction authenticates
        # and locks current parent/participants again; no lookup grants access.
        with self._connection(store) as c:
            parent_id=id
            if method in ('read_dispatch','dispatch_command','recover_accept'):
                row=c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s',(id,)).fetchone()
                if not row:raise Denied('CaseStep unavailable')
                parent_id=row['preparation_id']
            elif method in ('read_receipt','receipt_command','recover_submit'):
                row=c.execute('SELECT preparation_id FROM service_receipt_steps WHERE id=%s',(id,)).fetchone()
                if not row:raise Denied('CaseStep unavailable')
                parent_id=row['preparation_id']
            executor=args[-1].executor_id if method=='offer' else None
            context=self._context(c,parent_id,executor,catalog=method=='catalog')
        return getattr(context,method)(store,token,id,*args)

    def read_preparation(self,store,token,id):return self._call('read_preparation',store,token,id)
    def read_dispatch(self,store,token,id):return self._call('read_dispatch',store,token,id)
    def catalog(self,store,token,id):return self._call('catalog',store,token,id)
    def offer(self,store,token,id,key,data):
        if type(data) is not sd.Offer:raise Denied('typed CaseStep offer required')
        return self._call('offer',store,token,id,key,data)
    def dispatch_command(self,store,token,id,key,data):return self._call('dispatch_command',store,token,id,key,data)
    def read_receipt(self,store,token,id):return self._call('read_receipt',store,token,id)
    def receipt_command(self,store,token,id,key,data):return self._call('receipt_command',store,token,id,key,data)
    def receipt_catalog(self,store,token,id):return self._call('receipt_catalog',store,token,id)
    def recover_accept(self,store,token,id,key,data):return self._call('recover_accept',store,token,id,key,data)
    def recover_submit(self,store,token,id,key,data):return self._call('recover_submit',store,token,id,key,data)
    def unsupported(self,*args,**kwargs):return _CaseStepTransactions.unsupported(self,*args,**kwargs)

    def _list(self,store,token,receipts=False):
        with self._connection(store) as c:
            p=sd._auth(store,c,token)
            if p['role']=='service_executor':scope="EXISTS (SELECT 1 FROM service_dispatch_offers o WHERE o.dispatch_id=d.id AND o.executor_id=%s)"
            else:scope='p.'+('owner_id' if p['role']=='enterprise_operator' else 'reviewer_id')+'=%s'
            rows=c.execute("SELECT d.id,d.preparation_id FROM service_dispatches d JOIN preparations p ON p.id=d.preparation_id WHERE p.park_id=%s AND p.org_id=%s AND "+scope+" AND EXISTS (SELECT 1 FROM service_dispatch_events e WHERE e.dispatch_id=d.id AND e.action='OFFER' AND e.payload->%s->'binding'->>'contract'=%s) ORDER BY d.created_at DESC,d.id DESC LIMIT 101",(p['park_id'],p['org_id'],p['id'],MARKER,self.contract)).fetchall()
            items=[]
            for base in rows[:100]:
                checkpoint=len(self._checks[c])
                try:
                    context=self._context(c,base['preparation_id'])
                    _,parent=context._parent(c,token,base['preparation_id']);dispatch=context._root(c,parent)
                    offer=context._own(c,p,parent,dispatch) if p['role']=='service_executor' else sd._own_offer(c,p,dispatch)
                    if receipts:
                        if p['role']=='park_specialist':continue
                        step=context._accepted_step(c,parent,offer)
                        items.append(dict(id=step['id'],goal=TITLE,state=step['state'],revision=step['revision'],case_cancelled=prep.case_cancelled(c,parent),case_reconciling=False,case_write_blocked=prep.case_write_blocked(c,parent)))
                    else:items.append(dict(id=dispatch['id'],preparation_id=parent['id'],goal=TITLE))
                except (Denied,Conflict):del self._checks[c][checkpoint:]
            return dict(scope=er.SCOPE if receipts else sd.SCOPE,role=p['role'],items=items,has_older_records=len(rows)>100,access_filtered=min(len(rows),100)-len(items),assignment_contract=self.contract)

    def list_dispatches(self,store,token):return self._list(store,token)
    def list_receipts(self,store,token):return self._list(store,token,True)

    def owns_notice(self,c,source):
        return self._context(c,source['preparation_id'],source['executor_id']).owns_notice(c,source)

    def notice_source(self,c,source):
        return self._context(c,source['preparation_id'],source['executor_id']).notice_source(c,source)

    def notice_authority(self,c,p,source):
        return self._context(c,source['preparation_id'],source['executor_id']).notice_authority(c,p,source)

    def notice_item(self,c,p,parent,root,source,item):
        return self._context(c,source['preparation_id'],source['executor_id']).notice_item(c,p,parent,root,source,item)


def validate_dependency(service,store):
    if type(service) not in (IsolatedCaseStepAssignments,OrdinaryCaseStepAssignments):
        raise Denied('exact CaseStep service required')
    service.validate(store)


def local_demo_pair(service,store,demo):
    """An exact routing composition, never an admission or authority proof."""
    from .local_synthetic_demo import LocalSyntheticDemo,LocalDemoCatalog,LocalDemoSelector
    return (type(service) is OrdinaryCaseStepAssignments and service.store is store
        and demo is not None and getattr(service,'local_synthetic_demo',None) is demo
        and type(demo) is LocalSyntheticDemo and type(demo.catalog) is LocalDemoCatalog
        and type(demo.selector) is LocalDemoSelector and demo.catalog.store is store
        and getattr(store,'_local_synthetic_demo_catalog',None) is demo.catalog)


def from_environment(store,environment):
    mode=environment.get('PARKWEAVE_CASE_STEP_MODE')
    if mode is None:return None
    if mode==LOCAL_DEMO_MODE:
        if any(environment.get(k) is not None for k in (
                'PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG',
                'PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG')):
            raise Denied('independent local demo ordinary CaseStep mode required; no fallback')
        from .local_synthetic_demo import configure,PROFILE
        if environment.get('PARKWEAVE_SERVICE_PROFILE')!=PROFILE or environment.get('PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG') is None:
            raise Denied('explicit existing local demo inputs required')
        demo=configure(store,PROFILE,environment['PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG'])
        return OrdinaryCaseStepAssignments(store,local_synthetic_demo=demo)
    if mode!=ORDINARY_MODE or any(environment.get(k) is not None for k in (
            'PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG',
            'PARKWEAVE_SERVICE_PROFILE','PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG',
            'PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG')):
        raise Denied('independent ordinary CaseStep mode required; no fallback')
    return OrdinaryCaseStepAssignments(store)

def has_marker(c,preparation_id):
    return bool(c.execute("SELECT 1 FROM service_dispatch_events e JOIN service_dispatches d ON d.id=e.dispatch_id WHERE d.preparation_id=%s AND e.payload ? %s LIMIT 1",(preparation_id,MARKER)).fetchone())


def refuse_legacy(c,preparation_id):
    if has_marker(c,preparation_id):
        raise Denied('CaseStep marker requires its original explicit isolated service; no legacy interpretation')

def legacy_rows(c,rows,key,*,receipt=False):
    result=[]
    for row in rows:
        id=row[key]
        if receipt:
            source=c.execute('SELECT preparation_id FROM service_receipt_steps WHERE id=%s',(id,)).fetchone()
            id=source['preparation_id'] if source else None
        try:refuse_legacy(c,id)
        except Denied:continue
        result.append(row)
    return result
