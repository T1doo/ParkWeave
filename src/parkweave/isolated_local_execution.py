"""Dormant owned-fixture local report generation, never business fulfillment.

The report is the actual local software output. Its receipt and execution event
are committed with that output in the caller's PG transaction; no external,
filesystem, model, credential or permission effect is performed.
"""
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .isolated_run_access import IsolatedRunAccessBridge
from .store import Denied, digest

ADAPTER_ID = 'synthetic.accepted-handoff-report'
EFFECT = 'LOCAL_SYNTHETIC_HANDOFF_REPORT_CREATED'


class ExecuteLocal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    expected_revision: int = Field(ge=1, le=62)
    reason: str = Field(min_length=1, max_length=1000)


class IsolatedLocalExecutor:
    def __init__(self, bridge, *, enabled_for_isolated_tests=False):
        self.enabled = enabled_for_isolated_tests is True
        self.bridge = bridge
        if not self.enabled:
            return
        if type(bridge) is not IsolatedRunAccessBridge:
            raise Denied('issued isolated access bridge required')
        bridge._issued_proof()
        with bridge.owner.connect() as c:
            bridge._proof(c)
            c.execute('ALTER TABLE service_step_receipts ADD COLUMN IF NOT EXISTS adapter_execution jsonb')
            column = c.execute("""SELECT data_type,is_nullable FROM information_schema.columns
                WHERE table_schema='public' AND table_name='service_step_receipts'
                  AND column_name='adapter_execution'""").fetchone()
            if not column or column['data_type'] != 'jsonb' or column['is_nullable'] != 'YES':
                raise Denied('isolated local execution schema refused')

    def attach_store(self, store):
        if not self.enabled or getattr(store, '_isolated_run_access', None) is not self.bridge:
            raise Denied('isolated local execution requires attached access bridge')
        self.bridge._issued_proof()
        with self.bridge.owner.connect() as c:
            self.bridge._proof(c)
        with store.connect() as c:
            self.bridge._connection(c)
        store._isolated_local_execution = self
        return store

    def binding(self, store, c, row, parent):
        from . import executor_receipts as er
        if (not self.enabled or getattr(store, '_isolated_run_access', None) is not self.bridge or
                getattr(store, '_isolated_local_execution', None) is not self or c.autocommit):
            raise Denied('isolated local execution disabled')
        self.bridge._issued_proof()
        self.bridge._connection(c)
        executor = er._executor(store, c, row['executor_id'], row['run_id'])
        store.check_capability(c, executor, 'READ')
        assignment = c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',
                               (executor['id'], row['run_id'])).fetchone()
        if not assignment or not isinstance(assignment.get('managed_access'), dict):
            raise Denied('current managed executor lease required')
        if not store.assignment_allowed(c, executor, row['run_id'], assignment):
            raise Denied('current managed executor lease required')
        current = er.current_step(c, parent)
        offer = c.execute("""SELECT o.* FROM service_dispatches d JOIN service_dispatch_offers o
            ON o.id=d.current_offer_id WHERE d.preparation_id=%s AND o.state='ACCEPTED'""",
                          (parent['id'],)).fetchone()
        if (not current or current['id'] != row['id'] or not offer or
                offer['executor_id'] != executor['id'] or offer['receipt_step_id'] != row['id'] or
                not er._fresh(row, parent, c, store, check_execution=False)):
            raise Denied('current accepted handoff and preparation required')
        return dict(park_id=row['park_id'], org_id=row['org_id'], run_id=str(row['run_id']),
                    case_id=str(row['case_id']), step_id=str(row['id']), executor_id=executor['id'],
                    offer_id=str(offer['id']), service_id=row['service_id'], service_version=row['service_version'],
                    preparation_id=str(parent['id']), preparation_revision=parent['revision'],
                    preparation_sha256=parent['review_sha256'], managed_access=assignment['managed_access'])

    def generate(self, store, c, row, parent):
        binding = self.binding(store, c, row, parent)
        report = dict(adapter_id=ADAPTER_ID, adapter_version=1, execution_id=str(uuid4()), effect=EFFECT,
                      binding=binding, checks=['CURRENT_ACCEPTED_HANDOFF', 'CURRENT_PREPARATION_BINDING',
                                               'CURRENT_MANAGED_EXECUTOR_LEASE'],
                      external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE',
                      case_goal_completed=False)
        from .preparation import canonical
        text = canonical(report)
        return text, dict(report=report, submit_revision=row['revision'] + 1)

    def current(self, store, c, row, parent, receipt):
        from .preparation import canonical
        metadata = receipt.get('adapter_execution') if receipt else None
        if not isinstance(metadata, dict) or row['state'] not in ('RECEIPT_RECORDED', 'LOCAL_ACKNOWLEDGED'):
            return False
        try:
            report = metadata['report']
            if (set(metadata) != {'report', 'submit_revision'} or
                    report['adapter_id'] != ADAPTER_ID or report['adapter_version'] != 1 or report['effect'] != EFFECT or
                    receipt['id'] != row['current_receipt_id'] or receipt['step_id'] != row['id'] or
                    receipt['actor_id'] != row['executor_id'] or receipt['text'] != canonical(report) or
                    receipt['source_sha256'] != digest(receipt['text']) or
                    report['binding'] != self.binding(store, c, row, parent)):
                return False
            event = c.execute("""SELECT payload FROM service_receipt_events
                WHERE step_id=%s AND revision=%s AND action='SUBMIT' AND actor_id=%s""",
                              (row['id'], metadata['submit_revision'], row['executor_id'])).fetchone()
            return bool(event and event['payload'].get('adapter_execution') == metadata and
                        event['payload'].get('receipt_id') == str(receipt['id']) and
                        event['payload'].get('receipt_sha256') == receipt['source_sha256'])
        except (Denied, KeyError, TypeError, ValueError):
            return False


def provider(store):
    value = getattr(store, '_isolated_local_execution', None)
    return value if type(value) is IsolatedLocalExecutor and value.enabled else None


def current(store, c, row, parent, receipt):
    adapter = provider(store)
    return bool(adapter and adapter.current(store, c, row, parent, receipt))


def view(store, c, p, row, parent, receipt, is_current):
    from .executor_receipts import _requires_local
    adapter = provider(store)
    metadata = receipt.get('adapter_execution') if receipt else None
    valid = bool(is_current and metadata and current(store, c, row, parent, receipt))
    can_execute = False
    if adapter and is_current and p['role'] == 'service_executor':
        try:
            adapter.binding(store, c, row, parent)
            can_execute = (row['revision'] < 63 and
                (row['state'] in ('AWAITING_RECEIPT', 'CHANGES_REQUESTED') or bool(metadata) and not valid))
        except Denied:
            pass
    return dict(enabled=adapter is not None, can_execute=can_execute, current=valid,
                requires_adapter=_requires_local(c,row,receipt),
                record=metadata['report'] if isinstance(metadata, dict) and isinstance(metadata.get('report'), dict) else None,
                effect=EFFECT if metadata else None, adapter_id=ADAPTER_ID, adapter_version=1)
