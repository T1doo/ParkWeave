"""The original same-service catalog query, including unselected versions.

Only its bounded fingerprint enters the original dependency journal. No source
rows, present-day values or publication authority are added to old history.
"""
from . import controlled_plans as cp, case_opportunities as opportunities
from .catalog_publication import proof

LIMIT = 32


def collection(c, parent):
    # Same park/service/order/33rd-row guard and eligibility filter as the
    # original opportunity query. Original publication proof adds withdrawal
    # currentness even when that version is not the Case's selected version.
    # Optional journal columns remain compatible with the original schema.
    # to_jsonb(r) constructs a row inside PostgreSQL; this narrows returned
    # columns, not database internals or an asserted per-row byte bound.
    rows = c.execute('SELECT r.park_id,r.service_id,r.version,r.name,r.source,r.namespace,r.qualification,'
                     "to_jsonb(r)->'candidate_catalog_revisions' AS candidate_catalog_revisions,"
                     "to_jsonb(r)->'candidate_catalog_head' AS candidate_catalog_head "
                     'FROM preparation_catalog r WHERE r.park_id=%s '
                     'AND r.service_id=%s ORDER BY version LIMIT 33',
                     (parent['park_id'], parent['service_id'])).fetchall()
    values = []
    for row in rows:
        if (row['namespace'] == 'SYNTHETIC' and row['qualification'] == 'NOT_EVALUATED'
                and isinstance(row['source'], dict) and row['source'].get('kind') == 'SYNTHETIC'):
            values.append(dict(service_id=row['service_id'], version=row['version'], name=row['name'],
                source_sha256=opportunities.sha(row['source']), publication_head=proof(row)))
    return dict(known=len(rows) <= LIMIT, count=len(values) if len(rows) <= LIMIT else LIMIT + 1,
                sha256=cp._hash(cp._normal(values)))
