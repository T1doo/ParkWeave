"""Fixed P4/P5 summary policy and memory-only reader; no production registration.

Old proof is checked as document data, never issued as execution authority.
The caller's server-owned baselines are independent of the untrusted records.
There is deliberately no file loader, provider attachment or HTTP entry point.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from . import isolated_execution_preview as ep, receipt_execution_preview as p4
from . import lifecycle_execution_preview as p5, catalog_publication as catalog
from . import controlled_plans as plans, resource_holds as resources
from . import resource_execution_preview as resource_preview, preparation as prep
from .receipt_history_recovery import _key
from .store import Conflict, Denied

ROW_FIELDS = ('owner', 'preparation', 'request_key', 'fingerprint', 'document', 'proof')


class _P4Checks:
    # Only document checks, without inheriting execution/read/attach methods.
    storage_scope = p4.SCOPE
    execution_contract = p4.CONTRACT
    document_version = 2
    proof_fields = p4.PROOF_FIELDS
    _document = p4.ReceiptExecutionPreview._document
    _request_body = p4.ReceiptExecutionPreview._request_body
    _upstream_complete = p4.ReceiptExecutionPreview._upstream_complete
    _p4_document = p4.ReceiptExecutionPreview._p4_document

    def __init__(self, namespace):
        self.namespace = namespace


class _P5Checks(_P4Checks):
    storage_scope = p5.SCOPE
    execution_contract = p5.CONTRACT
    document_version = 3
    proof_fields = p5.PROOF_FIELDS
    _request_body = p5.LifecycleExecutionPreview._request_body
    _upstream_complete = p5.LifecycleExecutionPreview._upstream_complete
    _p4_document = p5.LifecycleExecutionPreview._p4_document
    _check_resources = p5.LifecycleExecutionPreview._check_resources


def _checks(stage, namespace):
    if stage == 'P4':
        return _P4Checks(namespace)
    if stage == 'P5':
        return _P5Checks(namespace)
    raise Denied('supported history stage required')


@dataclass(frozen=True)
class ReadContext:
    owner: str
    park: str
    org: str
    preparation: str
    case: str
    run: str
    database: tuple[str, str, str]
    source_sha256: str
    now: datetime


@dataclass(frozen=True)
class RecordAnchor:
    id: str
    key: str
    row_sha256: str
    source_sha256: str


@dataclass(frozen=True)
class TrustedBaseline:
    stage: str
    scope: str
    namespace: str
    version: int
    contract: str
    owner: str
    park: str
    org: str
    preparation: str
    case: str
    run: str
    database: tuple[str, str, str]
    valid_from: datetime
    valid_until: datetime
    revoked: bool
    records: tuple[RecordAnchor, ...]


def row_sha256(row):
    """Integrity helper only; computing this never enrolls or authorizes a row."""
    if type(row) is not dict or set(row.keys()) != set(ROW_FIELDS) or any(type(row[k]) is not str for k in ROW_FIELDS):
        raise Denied('original bounded history row required')
    if any(len(row[k].encode()) > (65536 if k in ('document', 'proof') else 200) for k in ROW_FIELDS):
        raise Denied('original bounded history row required')
    return ep._sha({k: row[k] for k in ROW_FIELDS})


def _baseline(baseline, context, stage):
    if type(baseline) is not TrustedBaseline or type(context) is not ReadContext:
        raise Denied('independent trusted history baseline required')
    checks = _checks(stage, baseline.namespace)
    times = (baseline.valid_from, baseline.valid_until, context.now)
    if any(type(t) is not datetime or t.tzinfo is None or t.utcoffset() != timezone.utc.utcoffset(t) for t in times):
        raise Denied('absolute UTC history validity required')
    if (type(baseline.revoked) is not bool or baseline.revoked or
            not baseline.valid_from <= context.now < baseline.valid_until or
            baseline.stage != stage or baseline.scope != checks.storage_scope or
            type(baseline.version) is not int or baseline.version != checks.document_version or
            baseline.contract != checks.execution_contract or
            type(baseline.namespace) is not str or not baseline.namespace or len(baseline.namespace) > 200 or
            any(getattr(baseline, k) != getattr(context, k) for k in
                ('owner', 'park', 'org', 'preparation', 'case', 'run', 'database')) or
            type(baseline.records) is not tuple or len(baseline.records) > 16):
        raise Denied('current scoped history baseline required')
    return checks


def summaries(stage, baseline, context, rows, key=None):
    """Pure projection. Context must already have passed current READ checks."""
    key = _key(key)
    checks = _baseline(baseline, context, stage)
    if type(rows) is not tuple or len(rows) > 128:
        raise Denied('bounded history required')
    anchors = {}
    ids = set()
    for anchor in baseline.records:
        if (type(anchor) is not RecordAnchor or type(anchor.key) is not str or type(anchor.id) is not str or
                anchor.key in anchors or anchor.id in ids or
                _key(anchor.key) is None or any(type(h) is not str or len(h) != 64 or
                any(c not in '0123456789abcdef' for c in h) for h in (anchor.row_sha256, anchor.source_sha256))):
            raise Denied('unique independent record anchors required')
        try:
            UUID(anchor.id)
        except (ValueError, TypeError, AttributeError):
            raise Denied('original history record identity required') from None
        anchors[anchor.key] = anchor
        ids.add(anchor.id)
    relevant = []
    seen = set()
    for row in rows:
        fingerprint = row_sha256(row)
        if row['owner'] != context.owner or row['preparation'] != context.preparation:
            raise Denied('exact owner preparation history required')
        anchor = anchors.get(row['request_key'])
        if anchor is None or row['request_key'] in seen or fingerprint != anchor.row_sha256:
            raise Denied('independent history integrity required')
        seen.add(row['request_key'])
        try:
            doc = checks._document(row)
            if (doc['id'] != anchor.id or any(doc['binding'][k] != getattr(context, name)
                    for k, name in (('case_id', 'case'), ('run_id', 'run')))):
                raise ValueError()
        except (Conflict, ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
            raise Denied('original history document unavailable') from None
        a = doc['artifact']
        final = a.get('lifecycle_final') if stage == 'P5' else None
        def events(values, allowed):
            if any(type(e) is not dict or e.get('action') not in allowed or type(e.get('revision')) is not int or
                    not 1 <= e['revision'] <= 3 for e in values):
                raise Denied('supported bounded historical event required')
            return [dict(action=e['action'], revision=e['revision']) for e in values]
        if final and (final['case_state'] not in ('WAITING_CONFIRMATION', 'REOPENED') or
                type(final['cycle']) is not int or final['cycle'] not in (1, 2) or
                type(final['verification_current']) is not bool):
            raise Denied('supported historical lifecycle summary required')
        summary = dict(id=doc['id'], request_key=doc['request_key'], stage=stage,
            state=doc['state'], p4_state=a['p4_state'], review_decision=doc['review_decision'],
            receipt_events=events(a['p4_events'], ('CREATE', 'SUBMIT', 'ACKNOWLEDGE', 'REQUEST_CHANGES')),
            namespace='SYNTHETIC', qualification='NOT_EVALUATED', formal_writes=0,
            case_goal_completed=False, external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE')
        if stage == 'P5':
            summary.update(p5_state=a['p5_state'], lifecycle_sequence=doc['lifecycle_sequence'],
                lifecycle_events=events(a['lifecycle_events'], ('REVALIDATE', 'CLOSE_LOCAL_RECORD', 'REOPEN')),
                past_case_state=final['case_state'] if final else None,
                past_cycle=final['cycle'] if final else None,
                verification_at_execution=final['verification_current'] if final else None)
        relevant.append(dict(summary=summary, source_state='SNAPSHOT_MATCH'
            if anchor.source_sha256 == context.source_sha256 else 'STALE'))
    if seen != set(anchors):
        raise Denied('complete anchored history required')
    result = dict(scope=baseline.scope, namespace=baseline.namespace,
        preparation_id=context.preparation, history=relevant, summary_only=True, read_only=True,
        execution_available=False, execution_qualification='NOT_EVALUATED', automatically_replayed=False,
        formal_writes=0, new_grants=False, case_goal_completed=False, source_atomicity=False,
        source_consistency='COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON')
    if key is not None:
        hits = [r['summary'] for r in relevant if r['summary']['request_key'] == key]
        result.update(request_key=key, status='COMMITTED' if hits else 'NOT_OBSERVED', result=hits[0] if hits else None)
    return result


def current_context(store, c, token, preparation_id):
    """Existing capabilities only; no bridge, assignment, EXECUTE or PREPARE."""
    p = store.auth(c, token, lock=True)
    store.check_capability(c, p, 'READ')
    if p['role'] != 'enterprise_operator':
        raise Denied('owner history scope required')
    parent = c.execute('SELECT id,owner_id,park_id,org_id,run_id,case_id,namespace,service_id,service_version,revision,request_intent,fact_clarifications FROM preparations WHERE id=%s AND owner_id=%s AND park_id=%s AND org_id=%s',
        (preparation_id, p['id'], p['park_id'], p['org_id'])).fetchone()
    if parent is None or parent['namespace'] != 'SYNTHETIC':
        raise Denied('own synthetic preparation required')
    run = store.scoped_run(c, p, parent['run_id'])
    case = c.execute('SELECT id,run_id,park_id,org_id,source FROM cases WHERE id=%s', (parent['case_id'],)).fetchone()
    if (run['namespace'] != 'SYNTHETIC' or case is None or
            any(case[k] != parent[k] for k in ('run_id', 'park_id', 'org_id')) or case['source'] != 'SYNTHETIC'):
        raise Denied('current own synthetic Case Run required')
    # Declared fact purposes need a separate current READ-only source contract;
    # do not call their issued execution gate or infer authority from old proof.
    if prep.fact_enabled(c, parent):
        raise Denied('declared fact history source unsupported')
    catalog.lock(c, catalog.key_of(parent))
    source = catalog.snapshot(c, parent)
    if not plans.binding_catalog_known(source):
        raise Denied('current known synthetic catalog required')
    rules = []
    for id in sorted(resource_preview.RESOURCES, key=str):
        resources._lock(c, id, shared=True)
        r = resources._scope(c, p, id, write=False)
        if (r['enabled'] is not True or r['namespace'] != 'SYNTHETIC' or r['authority'] != 'LOCAL_AUTHORITY' or
                not isinstance(r['source'], dict) or r['source'].get('kind') != 'SYNTHETIC' or
                not r['source'].get('id') or not r['source'].get('revision')):
            raise Denied('current known synthetic resource required')
        rules.append(ep._normal({k: r[k] for k in ('id','revision','capacity','buffer_seconds','open_from','open_until','enabled','timezone','namespace','authority','source')}))
    # Return only metadata and a server-computed integrity boolean, no material
    # body/label. Built-in PostgreSQL hashing needs no extension or new grant.
    materials = c.execute("SELECT DISTINCT ON(slot) id,slot,version,source_kind,source_sha256,actor_id,source_sha256=encode(sha256(convert_to(text,'UTF8')),'hex') AS source_intact FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC", (parent['id'],)).fetchall()
    if (len(materials) != len(prep.SLOTS) or {m['slot'] for m in materials} != set(prep.SLOTS) or
            any(m['source_intact'] is not True or m['actor_id'] != p['id'] or
                type(m['version']) is not int or m['version'] < 1 or
                m['source_kind'] not in ('USER_STATEMENT', 'DOCUMENT_EXCERPT') or
                type(m['source_sha256']) is not str or len(m['source_sha256']) != 64 or
                any(ch not in '0123456789abcdef' for ch in m['source_sha256']) for m in materials)):
        raise Denied('current complete intact own material sources required')
    identity = c.execute(ep.IDENTITY_SQL).fetchone()
    source_sha = ep._sha(ep._normal(dict(preparation_revision=parent['revision'], request_intent=parent['request_intent'], catalog=source, resources=rules, materials=materials)))
    return ReadContext(p['id'], p['park_id'], p['org_id'], str(parent['id']), str(parent['case_id']),
        str(parent['run_id']), tuple(identity[k] for k in ('name','oid','system_identifier')),
        source_sha, c.execute('SELECT clock_timestamp() now').fetchone()['now'])


class MemoryHistorySummaryReader:
    """Explicit test/server memory adapter, never attached to existing API routes.

    Mappings remain server-owned so expiry/revocation is consulted on every call.
    Rows and baselines are copied for each projection and rechecked before return.
    """
    def __init__(self, stage, baselines, records):
        _checks(stage, '')
        self.stage, self.baselines, self.records = stage, baselines, records

    def _rows(self, preparation_id):
        rows = self.records.get(str(preparation_id), ())
        if type(rows) not in (tuple, list) or len(rows) > 128 or any(type(r) is not dict for r in rows):
            raise Denied('bounded original memory history rows required')
        return tuple(dict(r) for r in rows)

    def read(self, store, token, preparation_id, key=None):
        key = _key(key)
        with store.connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            c.execute("SET LOCAL statement_timeout='3s'")
            c.execute("SET LOCAL lock_timeout='3s'")
            before = current_context(store, c, token, preparation_id)
            baseline = self.baselines.get(str(preparation_id))
            rows = self._rows(preparation_id)
            result = summaries(self.stage, baseline, before, rows, key)
            after = current_context(store, c, token, preparation_id)
            if (before != ReadContext(after.owner, after.park, after.org, after.preparation, after.case,
                    after.run, after.database, after.source_sha256, before.now) or
                    baseline != self.baselines.get(str(preparation_id)) or
                    rows != self._rows(preparation_id)):
                raise Denied('history read context changed')
            _baseline(baseline, after, self.stage)
            return result
