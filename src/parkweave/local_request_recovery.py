"""Exact original-key local workbench reads; never retry or settle an absence.

Receipts already exist in runs/preparation_events. No new index, write, body
retention, role enrollment or schema migration is required for this reader.
"""
import json

from . import preparation as prep
from .domain import Intake
from .store import Denied, Conflict, digest

OPERATIONS = ('CREATE_RUN', 'CREATE_PREPARATION', 'REQUEST_CHANGES', 'REVIEW', 'CONFIRM', 'REOPEN')


def read(store, token, operation, key, preparation_id=None):
    if operation not in OPERATIONS or ((operation in OPERATIONS[2:]) != (preparation_id is not None)):
        raise Conflict('exact local recovery operation and target required')
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL lock_timeout='3s'")
        p = store.auth(c, token, lock=True)
        store.check_capability(c, p, 'READ')
        result = dict(recovery_contract='parkweave-local-request-recovery/1', operation=operation,
            status='NOT_OBSERVED', read_only=True, historical_only=True, automatically_replayed=False,
            event=None, current_revision=None,
            request_binding=dict(request_key=key, fingerprint=None, legacy_page_fingerprint=None,
                actor={name:p[name] for name in ('id','park_id','org_id','role')}))
        if operation == 'CREATE_RUN':
            if p['role'] != 'enterprise_operator':raise Denied('current enterprise owner required')
            # Same lock as Store.submit. A missing row never proves a delayed
            # writer cannot arrive after this read, so it stays NOT_OBSERVED.
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(p['id']+':'+key,))
            row = c.execute('SELECT id,input,fingerprint,namespace FROM runs WHERE principal_id=%s '
                'AND park_id=%s AND org_id=%s AND request_key=%s',
                (p['id'],p['park_id'],p['org_id'],key)).fetchone()
            if row is None:return result
            data = Intake.model_validate(row['input'])
            simple = Intake(goal=data.goal, source=data.source)
            if (row['namespace'] != 'SYNTHETIC' or data.snapshot() != simple.snapshot()
                    or row['fingerprint'] != digest(json.dumps(data.snapshot(),sort_keys=True,ensure_ascii=False))):
                raise Conflict('original local case request binding changed')
            fp = digest(prep.canonical(dict(goal=data.goal,source=data.source)))
            result['event'] = dict(run_id=str(row['id']),namespace='SYNTHETIC')
        else:
            prep.grant(store,c,p,'PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED')
            if operation == 'CREATE_PREPARATION' and p['role'] != 'enterprise_operator':
                raise Denied('original enterprise creator required')
            prep.key_lock(c,p,key)
            record = c.execute('SELECT preparation_id,action,payload,fingerprint FROM preparation_events '
                'WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
            if record is None:
                if preparation_id is not None:prep.scoped(store,c,p,preparation_id,read_only=True)
                return result
            expected = 'CREATE' if operation=='CREATE_PREPARATION' else operation
            if record['action'] != expected or (preparation_id is not None and record['preparation_id'] != preparation_id):
                raise Conflict('original local request action or target changed')
            row = prep.scoped(store,c,p,record['preparation_id'],read_only=True)
            if row['namespace'] != 'SYNTHETIC':raise Denied('local synthetic preparation required')
            payload = record['payload']
            if (payload.get('actor_id') != p['id'] or payload.get('action') != expected
                    or payload.get('preparation_id') != str(row['id'])
                    or payload.get('run_id') != str(row['run_id'])):
                raise Conflict('original local receipt binding changed')
            fp = record['fingerprint']
            if operation != 'CREATE_PREPARATION':
                # Compatibility with non-evidence handles written by the old
                # page. Only the exact persisted normalized reason can match;
                # missing original whitespace/body is never guessed.
                legacy = dict(action=operation,expected_revision=payload['revision']-1,reason=payload['reason'])
                result['request_binding']['legacy_page_fingerprint'] = digest(prep.canonical(legacy))
            result.update(event=payload,current_revision=row['revision'])
        result['status'] = 'COMMITTED'
        result['request_binding']['fingerprint'] = fp
        return result
