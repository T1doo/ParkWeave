"""Pure anchored summaries: old hashes are data, never current authorization."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
import pytest
from parkweave import history_summary as hs, isolated_execution_preview as ep
from parkweave import preparation as prep
from parkweave.store import Denied


def seal(doc, checks):
    doc['fingerprint'] = ep._sha(dict(preparation_id=doc['binding']['preparation_id'], **checks._request_body(doc)))
    doc['sha256'] = ep._sha({k: v for k, v in doc.items() if k != 'sha256'})
    return dict(owner=doc['actor_id'], preparation=doc['binding']['preparation_id'],
        request_key=doc['request_key'], fingerprint=doc['fingerprint'], document=prep.canonical(doc),
        proof=prep.canonical({k: doc[k] for k in checks.proof_fields}))


def sample(stage='P4'):
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    context = hs.ReadContext('synthetic-owner', 'park-a', 'org-a', str(uuid4()), str(uuid4()),
        str(uuid4()), ('synthetic-db', '1', '2'), 'a'*64, now)
    checks = hs._checks(stage, 'synthetic-namespace')
    # Failed, unexecuted old documents cannot imply successful simulated work.
    artifact = dict(error='SYNTHETIC PRIVATE ERROR', roles='SIMULATED_ROLES_ONLY',
        capacity_scope='EMPTY_ISOLATED_SPACE_ONLY', namespace='PREVIEW_EXECUTION',
        p1=dict(preparation_id=str(uuid4()), case_id=str(uuid4()), run_id=str(uuid4())),
        holds=[], prechecks=[], receipts=[], links=[], offers=[], dispatch_events=[], steps=[],
        receipt_events=[], outbox=[], notices=[], p2_state='NOT_EXECUTED', p3_state='NOT_EXECUTED',
        p4_state='NOT_EXECUTED', p4_steps=[], p4_receipts=[], p4_events=[], access_events=[])
    doc = dict(id=str(uuid4()), scope=checks.storage_scope, version=checks.document_version,
        namespace=checks.namespace, actor_id=context.owner, request_key='synthetic-key',
        execution_contract_sha256=checks.execution_contract, state='FAILED', decision='ACCEPT',
        review_decision='ACKNOWLEDGE', formal_writes=0, new_grants=False, case_goal_completed=False,
        qualification='NOT_EVALUATED', external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE',
        binding=dict(preparation_id=context.preparation, case_id=context.case, run_id=context.run,
            preparation_revision=1, request_revision=1, source_sha256='b'*64),
        required_goals=[], goal_coverage=[], not_previewed=['P2','P3','P4','P5'], coverage_state='PARTIAL_PREVIEW',
        artifact=artifact)
    if stage == 'P5':
        doc['lifecycle_sequence'] = 'REVALIDATE_CLOSE_REOPEN'
        artifact.update(p5_state='NOT_EXECUTED', lifecycle_attempts=[], lifecycle_events=[], lifecycle_ledger=[], lifecycle_final=None)
    row = seal(doc, checks)
    anchor = hs.RecordAnchor(doc['id'], doc['request_key'], hs.row_sha256(row), context.source_sha256)
    baseline = hs.TrustedBaseline(stage, checks.storage_scope, checks.namespace, checks.document_version,
        checks.execution_contract, context.owner, context.park, context.org, context.preparation,
        context.case, context.run, context.database, now-timedelta(hours=1), now+timedelta(hours=1), False, (anchor,))
    return context, baseline, row, checks


@pytest.mark.parametrize('stage', ['P4','P5'])
def test_old_exact_version_summary_key_envelope_and_no_private_fields(stage):
    c,b,r,checks = sample(stage)
    result = hs.summaries(stage,b,c,(r,),'synthetic-key')
    assert result['status']=='COMMITTED' and result['result']==result['history'][0]['summary']
    assert result['result']['state']=='FAILED' and not result['execution_available']
    assert not result['automatically_replayed'] and not result['new_grants']
    raw = json.dumps(result)
    for private in ('PRIVATE ERROR', 'synthetic-owner', 'proof', 'artifact', 'binding', 'managed_access', c.case, c.run):
        assert private not in raw
    missing = hs.summaries(stage,b,c,(r,),'missing')
    assert missing['status']=='NOT_OBSERVED' and missing['result'] is None
    assert not hasattr(checks,'execute') and not hasattr(checks,'read') and not hasattr(checks,'attach_store')


@pytest.mark.parametrize('change', ['missing','revoked','expired','future','naive','db','owner','park','org','preparation','case','run','scope','stage','version','contract','namespace','duplicate_anchor','malformed_key','malformed_id'])
def test_independent_baseline_exact_scope_validity_and_uniqueness(change):
    c,b,r,_=sample()
    if change=='missing':b=None
    elif change=='revoked':b=replace(b,revoked=True)
    elif change=='expired':b=replace(b,valid_until=c.now)
    elif change=='future':b=replace(b,valid_from=c.now+timedelta(seconds=1))
    elif change=='naive':b=replace(b,valid_until=c.now.replace(tzinfo=None))
    elif change=='db':b=replace(b,database=('replacement','1','2'))
    elif change=='duplicate_anchor':b=replace(b,records=b.records*2)
    elif change=='malformed_key':b=replace(b,records=(replace(b.records[0],key=[]),))
    elif change=='malformed_id':b=replace(b,records=(replace(b.records[0],id='invalid'),))
    elif change=='version':b=replace(b,version=99)
    else:b=replace(b,**{change:'wrong'})
    with pytest.raises(Denied):hs.summaries('P4',b,c,(r,))


@pytest.mark.parametrize('field', hs.ROW_FIELDS)
def test_self_rehashed_modified_row_cannot_replace_external_anchor(field):
    c,b,r,checks=sample()
    if field in ('document','proof','fingerprint'):
        d=json.loads(r['document']);d['artifact']['error']='DIFFERENT PRIVATE';r=seal(d,checks)
    else:r={**r,field:'changed'}
    with pytest.raises(Denied):hs.summaries('P4',b,c,(r,))


@pytest.mark.parametrize('change',['version','contract','case','run','malformed','private_event','oversize','extra_column','missing_row','duplicate_row','unknown_row','too_many','nonmapping'])
def test_bounded_original_document_semantics_checked_after_external_anchor(change):
    c,b,r,checks=sample('P5');d=json.loads(r['document'])
    if change=='version':d['version']=99
    elif change=='contract':d['execution_contract_sha256']='0'*64
    elif change in ('case','run'):d['binding'][change+'_id']=str(uuid4())
    elif change=='private_event':d['artifact']['p4_events']=[dict(action='PRIVATE BODY',revision=1)]
    if change in ('version','contract','case','run','private_event'):r=seal(d,checks)
    elif change=='malformed':r={**r,'document':'{'}
    elif change=='oversize':r={**r,'proof':'x'*65537}
    elif change=='extra_column':r={**r,'extra':'private'}
    rows=(r,)
    if change not in ('oversize','extra_column'):
        b=replace(b,records=(replace(b.records[0],row_sha256=hs.row_sha256(r)),))
    if change=='missing_row':rows=()
    elif change=='duplicate_row':rows=(r,r)
    elif change=='unknown_row':rows=({**r,'request_key':'unknown'},)
    elif change=='too_many':rows=(r,)*129
    elif change=='nonmapping':rows=(42,)
    with pytest.raises(Denied):hs.summaries('P5',b,c,rows)


def test_known_current_version_change_is_stale_and_not_fresh_verification():
    c,b,r,_=sample('P5')
    result=hs.summaries('P5',b,replace(c,source_sha256='c'*64),(r,))
    assert result['history'][0]['source_state']=='STALE'
    assert result['history'][0]['summary']['verification_at_execution'] is None


@pytest.mark.parametrize('key',['','x'*129,'private/route',42])
def test_same_old_bounded_key_semantics(key):
    c,b,r,_=sample()
    with pytest.raises(Denied):hs.summaries('P4',b,c,(r,),key)
