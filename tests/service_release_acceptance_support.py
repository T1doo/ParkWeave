"""Independent observations for service release/instance acceptance.

These helpers do not manufacture release proofs, seed permissions, or call the
production compiler. Actual PostgreSQL fixture setup remains the original one.
"""
import hashlib
import json
import time
from uuid import UUID


AUTHORITY_TABLES = (
    'principals', 'capability_grants', 'action_grants', 'field_grants',
    'preparation_grants', 'synthetic_resource_grants', 'run_assignments',
)


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def table_snapshot(owner, tables):
    with owner.connect() as connection:
        return {table: connection.execute(
            'SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text'
        ).fetchall() for table in tables}


def authority_snapshot(owner):
    return table_snapshot(owner, AUTHORITY_TABLES)


def reviewed_source_descriptor(published):
    """Extract the original reviewed release references, without issuing trust."""
    assert published['state'] == 'PUBLISHED' and published['candidate_available']
    snapshot = published['snapshot']
    review = snapshot['review']
    source = snapshot['definition']['source']
    assert review['action'] == 'REVIEW'
    return dict(template_release_id=published['release_id'],
                template_release_sha256=published['release_sha256'],
                definition_sha256=snapshot['definition_sha256'],
                registry_sha256=snapshot['registry_sha256'],
                review_revision=review['revision'], review_action=review['action'],
                source_id=source['id'], source_revision=source['revision'],
                source_sha256=stable_hash(source), validity=source['validity'])


def case_history(owner, preparation_id):
    """Full records belonging to one Case, including retained capacity history."""
    with owner.connect() as connection:
        parent = connection.execute('SELECT * FROM preparations WHERE id=%s',
                                    (UUID(str(preparation_id)),)).fetchone()
        assert parent is not None
        predicates = {
            'preparations': ('id', parent['id']),
            'runs': ('id', parent['run_id']),
            'cases': ('id', parent['case_id']),
            'preparation_evidence': ('preparation_id', parent['id']),
            'preparation_events': ('preparation_id', parent['id']),
            'case_local_lifecycles': ('preparation_id', parent['id']),
            'case_local_events': ('preparation_id', parent['id']),
            'case_resource_links': ('case_id', parent['case_id']),
            'resource_case_claims': ('case_id', parent['case_id']),
            'service_dispatches': ('preparation_id', parent['id']),
            'service_receipt_steps': ('preparation_id', parent['id']),
            'run_assignments': ('run_id', parent['run_id']),
        }
        result = {table: connection.execute(
            'SELECT * FROM ' + table + ' WHERE ' + column + '=%s '
            'ORDER BY to_jsonb(' + table + ')::text', (value,)
        ).fetchall() for table, (column, value) in predicates.items()}
        result['service_dispatch_offers'] = connection.execute(
            'SELECT o.* FROM service_dispatch_offers o JOIN service_dispatches d '
            'ON d.id=o.dispatch_id WHERE d.preparation_id=%s ORDER BY o.id',
            (parent['id'],)).fetchall()
        result['service_dispatch_events'] = connection.execute(
            'SELECT e.* FROM service_dispatch_events e JOIN service_dispatches d '
            'ON d.id=e.dispatch_id WHERE d.preparation_id=%s ORDER BY e.id',
            (parent['id'],)).fetchall()
        for table in ('service_step_receipts', 'service_receipt_events'):
            result[table] = connection.execute(
                'SELECT x.* FROM ' + table + ' x JOIN service_receipt_steps s '
                'ON s.id=x.step_id WHERE s.preparation_id=%s ORDER BY x.id',
                (parent['id'],)).fetchall()
        result['synthetic_resource_holds'] = connection.execute(
            'SELECT DISTINCT h.* FROM synthetic_resource_holds h '
            'JOIN synthetic_resource_combination_members m ON m.hold_id=h.id '
            'JOIN resource_case_claims l ON l.combination_id=m.combination_id '
            'WHERE l.case_id=%s ORDER BY h.id', (parent['case_id'],)).fetchall()
        return result


def wait_for_pg_blocker(owner, blocker_pid, *, timeout=2):
    """Observe an actual PostgreSQL waiter; elapsed Python time is not proof."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with owner.connect() as connection:
            waiters = connection.execute(
                'SELECT pid,wait_event_type,wait_event FROM pg_stat_activity '
                'WHERE %s = ANY(pg_blocking_pids(pid)) ORDER BY pid',
                (blocker_pid,)).fetchall()
        if waiters:
            assert all(row['wait_event_type'] == 'Lock' for row in waiters)
            return waiters
        time.sleep(0.01)
    raise AssertionError('No PostgreSQL lock waiter observed for held publication lock')
