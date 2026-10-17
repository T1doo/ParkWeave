"""Current assigned specialist's exact historical REVIEW versus current text.

Read-only projection of existing material rows and the original snapshot hash.
No review, fact adoption, history repair or authority is produced by this reader.
"""
from itertools import product
import re
from uuid import UUID

from psycopg.errors import LockNotAvailable

from . import preparation as prep
from .store import Conflict, Denied, digest

SCOPE = 'SYNTHETIC_ASSIGNED_MATERIAL_REVIEW_COMPARISON'
FIELDS = ('id', 'slot', 'version', 'text', 'source_kind', 'source_label', 'source_sha256', 'authenticity')
HISTORY_LIMIT = 64


def material(row):
    item = {k: str(row[k]) if isinstance(row[k], UUID) else row[k] for k in FIELDS}
    if (item['slot'] not in prep.SLOTS or type(item['version']) is not int or item['version'] < 1 or
            not isinstance(item['text'], str) or not 1 <= len(item['text']) <= 4000 or
            item['source_kind'] not in ('USER_STATEMENT', 'DOCUMENT_EXCERPT') or
            not isinstance(item['source_label'], str) or not 1 <= len(item['source_label']) <= 200 or
            item['authenticity'] != 'UNVERIFIED' or digest(item['text']) != item['source_sha256']):
        raise ValueError('unverified material source')
    UUID(item['id'])
    return item


def restore(parent, history, review):
    """Match existing eight-field snapshots; never infer a temporal baseline."""
    if len(history) > HISTORY_LIMIT:
        return 'UNVERIFIED', None
    if review is None:
        return 'NO_PREVIOUS_REVIEW', None
    payload = review['payload']
    if (not isinstance(payload, dict) or
            type(review['revision']) is not int or not 1 <= review['revision'] <= parent['revision'] or
            any(payload.get(k) != str(parent[v]) for k, v in
                (('preparation_id', 'id'), ('case_id', 'case_id'), ('run_id', 'run_id'))) or
            payload.get('revision') != review['revision'] or payload.get('actor_id') != review['actor_id'] or
            payload.get('action') != 'REVIEW' or payload.get('state') != 'REVIEWED' or
            payload.get('scope') != 'SYNTHETIC_LOCAL_PREPARATION_ONLY' or
            not isinstance(payload.get('snapshot_sha256'), str) or
            not re.fullmatch('[a-f0-9]{64}', payload['snapshot_sha256'])):
        return 'UNVERIFIED', None
    try:
        items = [material(row) for row in history]
    except (ValueError, TypeError, KeyError):
        return 'UNVERIFIED', None
    groups = [[m for m in items if m['slot'] == slot] for slot in sorted(prep.SLOTS)]
    matches = []
    for pair in product(*groups):
        if prep.snapshot(parent, pair) == payload['snapshot_sha256']:
            matches.append(list(pair))
            if len(matches) > 1:
                return 'UNVERIFIED', None
    return ('MATCHED', matches[0]) if len(matches) == 1 else ('UNVERIFIED', None)


def read(store, token, id):
    try:
        with store.connect() as c:
            c.execute("SET LOCAL lock_timeout='3s'")
            actor = store.auth(c, token, lock=True)
            if actor['role'] != 'park_specialist':
                raise Denied('current assigned material reviewer required')
            parent = prep.scoped(store, c, actor, id)
            # Original parent SHARE lock serializes all ordinary material writers.
            # Original exact synthetic catalog/current reviewer checks remain.
            entry, _ = prep.entry_context(store, c, actor, id)
            if entry['revision'] != parent['revision']:
                raise Conflict('material review source changed; reread original preparation')
            # Existing local MVCC rows identify same-value rewrites/assignment ABA.
            # Only their opaque digest leaves this current authorized reader.
            epochs = c.execute("""SELECT jsonb_build_object(
                'principal',a.xmin::text,'read',jsonb_build_array(g.revision,g.xmin::text),
                'assigned_grant',pg.xmin::text,'assignment',pr.xmin::text,
                'catalog',jsonb_build_array(cat.source,cat.xmin::text)) AS source
                FROM principals a
                JOIN capability_grants g ON g.principal_id=a.id AND g.capability='READ' AND g.active AND g.park_id=a.park_id AND g.org_id=a.org_id
                JOIN preparation_grants pg ON pg.principal_id=a.id AND pg.capability='REVIEW_ASSIGNED' AND pg.active AND pg.park_id=a.park_id AND pg.org_id=a.org_id
                JOIN preparations pr ON pr.id=%s AND pr.reviewer_id=a.id AND pr.park_id=a.park_id AND pr.org_id=a.org_id
                JOIN preparation_catalog cat ON cat.park_id=pr.park_id AND cat.service_id=pr.service_id AND cat.version=pr.service_version
                WHERE a.id=%s AND a.active AND a.role='park_specialist' AND cat.namespace='SYNTHETIC' AND cat.source->>'kind'='SYNTHETIC'""",
                (id, actor['id'])).fetchone()
            if epochs is None:
                raise Conflict('current material review reader source changed')
            current = [material(m) for m in prep.latest(c, id)]
            history = c.execute('SELECT id,slot,version,text,source_kind,source_label,source_sha256,authenticity '
                                'FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version LIMIT %s',
                                (id, HISTORY_LIMIT + 1)).fetchall()
            review = c.execute("SELECT id,actor_id,revision,payload,created_at FROM preparation_events "
                               "WHERE preparation_id=%s AND action='REVIEW' ORDER BY revision DESC LIMIT 1", (id,)).fetchone()
            state, baseline = restore(parent, history, review)
            review_sha = review['payload'].get('snapshot_sha256') if review and isinstance(review['payload'], dict) else None
            if not isinstance(review_sha, str) or not re.fullmatch('[a-f0-9]{64}', review_sha):
                review_sha = None
            event = None if review is None else dict(id=str(review['id']), revision=review['revision'],
                actor_id=review['actor_id'], created_at=review['created_at'].isoformat(),
                snapshot_sha256=review_sha)
            by_old = {m['slot']: m for m in baseline or []}
            by_current = {m['slot']: m for m in current}
            result = dict(scope=SCOPE, read_only=True, role=actor['role'], reviewer_id=actor['id'],
                preparation_id=str(id), case_id=str(parent['case_id']), run_id=str(parent['run_id']),
                preparation_revision=parent['revision'], service_id=parent['service_id'], service_version=parent['service_version'],
                reader_source_sha256=digest(prep.canonical(epochs['source'])),
                current_snapshot_sha256=prep.snapshot(parent, current), baseline_state=state, review_event=event,
                slots=[dict(slot=slot, baseline=by_old.get(slot), current=by_current.get(slot)) for slot in prep.SLOTS],
                qualification='NOT_EVALUATED', authenticity='UNVERIFIED', external_acceptance='NOT_SUBMITTED',
                offline_fulfillment='NO_EVIDENCE', case_goal_completed=False, review_performed=False,
                correction_sufficiency='NOT_EVALUATED', facts_adopted=False)
            result['comparison_sha256'] = digest(prep.canonical(result))
            return result
    except LockNotAvailable as exc:
        raise Conflict('material review source busy; retry original read') from exc
    except ValueError as exc:
        raise Conflict('current material source cannot be verified') from exc
