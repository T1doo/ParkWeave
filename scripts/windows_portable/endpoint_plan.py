"""Exact-lease endpoint consistency only, never port/socket or role authority.

Only NEW requests have a public factory. REOPEN registration is an internal
fixed-store finalization step after all reads, closes and lease verification.
No DSN, socket, random source, persistent write or native operation is here.
"""
from dataclasses import dataclass
from enum import Enum
from threading import get_ident
import weakref

from . import fixed_journal as journal
from .fixed_directories import FixedDirectoryLease, _exclusive_entry


class EndpointRefused(RuntimeError):
    def __init__(self): super().__init__('PRIVATE_ENDPOINT_PLAN_REFUSED')


def need(condition):
    if not condition: raise EndpointRefused()


class PlanMode(Enum):
    NEW = 'NEW'
    REOPEN = 'REOPEN'


@dataclass(frozen=True)
class EndpointRequest:
    database_port: int
    api_port: int

    def __post_init__(self):
        need(type(self) is EndpointRequest and
             all(type(x) is int and 1 <= x <= 65535 for x in (self.database_port,self.api_port))
             and self.database_port != self.api_port)


def validate_record(value):
    need(type(value) is dict and set(value)=={'schema','host','database_port','api_port'}
         and type(value['schema']) is str and value['schema']=='parkweave-private-endpoints/1'
         and type(value['host']) is str and value['host']=='127.0.0.1')
    return EndpointRequest(value['database_port'],value['api_port'])


def _record(database_port,api_port):
    EndpointRequest(database_port,api_port)
    return dict(schema='parkweave-private-endpoints/1',host='127.0.0.1',
                database_port=database_port,api_port=api_port)


class InstanceEndpointPlan:
    __slots__=('__weakref__',)
    def __reduce__(self): raise TypeError('ENDPOINT_PLAN_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('ENDPOINT_PLAN_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo): raise TypeError('ENDPOINT_PLAN_NOT_TRANSFERABLE')


@dataclass(frozen=True,repr=False)
class _Registration:
    lease: object
    plan: object
    key: tuple
    mode: PlanMode
    database_port: int
    api_port: int


_issued=weakref.WeakKeyDictionary()
_by_lease=weakref.WeakKeyDictionary()


def _key_held(lease):
    need(type(lease) is FixedDirectoryLease and lease._operation_owner==get_ident()
         and lease._operation_depth>0)
    instance_id=lease._verified_instance_uuid()
    record=journal.decode(lease.snapshot[0],format=journal.FixedFormat.INSTANCE_V2)
    need(journal.encode(lease.record)==lease.snapshot[0] and record['handoff']=='OWNED')
    return (instance_id,tuple(record['root']),tuple(record['lock']),tuple(record['journal']),record['generation'])


def _register_held(lease,request,mode,*,closed_recovery=None,native_recovery=None):
    # This private function is not a JSON/import API or native authorization.
    # Exact registry membership is checked at every later use of its result.
    need(type(mode) is PlanMode)
    key=_key_held(lease)
    need(lease not in _by_lease)
    record=journal.decode(lease.snapshot[0],format=journal.FixedFormat.INSTANCE_V2)
    if mode is PlanMode.NEW:
        need(closed_recovery is None and native_recovery is None and type(request) is EndpointRequest)
        need(record['phase']=='NEW' and record['initialized'] is False and key[-1]==1)
    else:
        # An arbitrary request/dict, even under this same gate, cannot stand
        # in for the completed fixed-store read and successful close sequence.
        need(request is None)
        if native_recovery is not None:
            need(closed_recovery is None)
            from .native_secret_store_candidate import _consume_ticket
            _,_,request=_consume_ticket(lease,native_recovery,'ENDPOINT')
        else:
            from .fixed_secret_store import _consume_closed_endpoint_recovery
            request=_consume_closed_endpoint_recovery(lease,closed_recovery)
        need(record['phase']=='READY_STOPPED' and record['initialized'] is True and key[-1]>=2)
    request=EndpointRequest(request.database_port,request.api_port)
    plan=InstanceEndpointPlan()
    registration=_Registration(weakref.ref(lease),weakref.ref(plan),key,mode,
                               request.database_port,request.api_port)
    _by_lease[lease]=registration
    _issued[plan]=registration
    return plan


@_exclusive_entry
def _create_new_entry(lease,request):
    return _register_held(lease,request,PlanMode.NEW)


def create_new_plan(lease,request):
    need(type(lease) is FixedDirectoryLease)
    return _create_new_entry(lease,request)


def _record_held(lease,plan,*,mode):
    need(type(plan) is InstanceEndpointPlan and type(mode) is PlanMode)
    registration=_issued.get(plan)
    need(registration is not None and registration.plan() is plan and registration.lease() is lease
         and _by_lease.get(lease) is registration and registration.mode is mode)
    need(_key_held(lease)==registration.key)
    return _record(registration.database_port,registration.api_port)


@_exclusive_entry
def _record_entry(lease,plan,*,mode):
    return _record_held(lease,plan,mode=mode)


def endpoint_record(lease,plan,*,mode):
    need(type(lease) is FixedDirectoryLease)
    return _record_entry(lease,plan,mode=mode)
