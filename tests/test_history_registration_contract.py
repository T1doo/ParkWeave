"""Pure synthetic declaration checks, never persistent enrollment fixtures."""
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
import ast
import inspect
import json

import pytest
from parkweave import history_registration_contract as rc


def sample_contract(stage='P4'):
    install = rc.InstallationBinding(UUID(int=1), 7, '/SYNTHETIC/install', 'synthetic-install-owner')
    database = rc.DatabaseBinding('synthetic-db', '42', '123456789', '/SYNTHETIC/pg', 'synthetic-db-owner')
    scope, version, contract = rc.P4_DOCUMENT if stage == 'P4' else rc.P5_DOCUMENT
    history = rc.HistoryBinding('synthetic-person', 'synthetic-park', 'synthetic-org', UUID(int=2),
                               UUID(int=3), UUID(int=4), stage, scope, 'synthetic-namespace', version, contract)
    anchor = rc.OriginalAnchor(UUID(int=5), 'Synthetic.Original_Key:1-', 'a'*64, 'b'*64)
    start = datetime(2026, 10, 11, tzinfo=timezone.utc);end = start + timedelta(days=1)
    declaration = rc.RegistrationDeclaration(rc.DECLARATION_KIND, 1, rc.PURPOSE, UUID(int=6), 3,
        rc.MaintainerBinding('synthetic-install-owner', 'synthetic-db-owner', 'synthetic-app-role'),
        'synthetic-parent-review', 'c'*64, install, database, history, (anchor,), start, end, False, None)
    # Observations are supplied separately; checker never derives them from a declaration.
    observed = replace(declaration)
    before = rc.IndependentObservation(rc.OBSERVATION_KIND, True, True, True, observed,
        replace(install), replace(database), replace(history), (replace(anchor),), 'c'*64, 3,
        False, True, True, start + timedelta(hours=1))
    after = replace(before, registration=replace(observed), now=before.now+timedelta(seconds=1))
    return declaration, before, after


def check(declaration, before, after):
    return rc.check_history_registration_contract(declaration, before, after, enabled_for_synthetic_checks=True)


@pytest.mark.parametrize('stage', ['P4', 'P5'])
def test_explicit_complete_synthetic_match_is_data_classification_only(stage):
    declaration, before, after = sample_contract(stage)
    result = check(declaration, before, after)
    assert asdict(result) == {'classification':'MATCH', 'reason':'SYNTHETIC_DECLARATION_CONSISTENT_ONLY'}
    with pytest.raises(TypeError, match='not an access permission'):bool(result)
    raw = json.dumps(asdict(result))
    for private in ('synthetic-person', 'Original_Key', '/SYNTHETIC', 'proof', 'grant', 'access_allowed'):
        assert private not in raw
    assert not hasattr(result, 'read') and not hasattr(result, 'authorize_migration')


@pytest.mark.parametrize('enabled', [False, None, 1, 'true', {}, []])
def test_default_is_closed_without_inspecting_inputs(enabled):
    result = rc.check_history_registration_contract(object(), object(), object(), enabled_for_synthetic_checks=enabled)
    assert result.classification == 'UNKNOWN' and result.reason == 'DEFAULT_DISABLED'
    assert rc.check_history_registration_contract(object()).classification == 'UNKNOWN'


@pytest.mark.parametrize('field', ['complete', 'generation_known', 'maintenance_isolated'])
@pytest.mark.parametrize('value', [None, False, 1, 'true'])
def test_unavailable_independent_generation_or_isolation_is_unknown(field, value):
    declaration, before, after = sample_contract()
    assert check(declaration, replace(before, **{field:value}), after).classification == 'UNKNOWN'


@pytest.mark.parametrize('field', ['registration', 'installation', 'database', 'history', 'anchors',
    'approved_manifest_sha256', 'minimum_revision', 'ever_revoked', 'current_read', 'sources_current', 'now'])
def test_incomplete_current_observation_cannot_be_replaced_by_self_report(field):
    declaration, before, after = sample_contract()
    result = check(declaration, before, replace(after, **{field:None}))
    assert result.classification == 'UNKNOWN'
    assert check(declaration, None, after).classification == 'UNKNOWN'


@pytest.mark.parametrize('kind', ['DECLARATION_SELF_REPORT', 'SAME_SID_FILE', 'LEGACY_PROOF', '', 1])
def test_hash_or_same_sid_or_legacy_proof_never_supply_missing_provenance(kind):
    declaration, before, after = sample_contract()
    # All hashes match. A label for a self-reported or old proof source does not help.
    assert check(declaration, replace(before, kind=kind), replace(after, kind=kind)).classification == 'UNKNOWN'


@pytest.mark.parametrize('field,value', [('kind','PRODUCTION'), ('schema_version',True), ('schema_version',2),
    ('purpose','EXECUTE'), ('enrollment_id',str(UUID(int=6))), ('revision',True), ('revision',0),
    ('revision',rc.MAX_REVISION+1), ('approval_ref',''), ('approval_ref','x'*201),
    ('approved_manifest_sha256','C'*64), ('approved_manifest_sha256','x'*64), ('revoked',1)])
def test_declaration_types_versions_and_bounded_metadata(field, value):
    declaration, before, after = sample_contract()
    assert check(replace(declaration, **{field:value}), before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('field,value', [('id',str(UUID(int=1))), ('generation',True), ('generation',0),
    ('generation',rc.MAX_REVISION+1), ('root_ref','relative'), ('root_ref','/a/../b'),
    ('root_ref','//network/share'), ('root_ref','/a\x00b'), ('owner_ref','*')])
def test_installation_field_shapes_and_paths(field, value):
    declaration, before, after = sample_contract()
    declaration = replace(declaration, installation=replace(declaration.installation, **{field:value}))
    assert check(declaration, before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('field,value', [('name',''), ('oid','042'), ('oid',42), ('oid',str(2**32)),
    ('system_identifier','0'), ('system_identifier',str(2**64)), ('data_directory_ref','relative'),
    ('data_directory_ref','C:\\a\\..\\b'), ('owner_role','other-owner')])
def test_database_canonical_identity_and_owner_fields(field, value):
    declaration, before, after = sample_contract()
    declaration = replace(declaration, database=replace(declaration.database, **{field:value}))
    assert check(declaration, before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('field,value', [('owner','*'), ('park',''), ('org','x'*201), ('preparation','not-uuid'),
    ('stage','P3'), ('document_version',True), ('document_version',3), ('scope','unknown'),
    ('document_contract_sha256','0'*64), ('namespace','x'*201)])
def test_history_exact_scope_stage_and_original_document_contract(field, value):
    declaration, before, after = sample_contract()
    declaration = replace(declaration, history=replace(declaration.history, **{field:value}))
    assert check(declaration, before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('change', ['list','empty','17','duplicate_id','duplicate_key','unknown_type','key_129',
    'key_empty','key_slash','key_unicode','bad_hash','id_string'])
def test_original_anchors_are_bounded_unique_and_exact(change):
    declaration, before, after = sample_contract();anchor = declaration.anchors[0];anchors = declaration.anchors
    if change == 'list':anchors = list(anchors)
    elif change == 'empty':anchors = ()
    elif change == '17':anchors = tuple(replace(anchor, id=UUID(int=20+i), key=str(i)) for i in range(17))
    elif change == 'duplicate_id':anchors += (replace(anchor, key='different'),)
    elif change == 'duplicate_key':anchors += (replace(anchor, id=UUID(int=20)),)
    elif change == 'unknown_type':anchors = ({'id':str(anchor.id)},)
    elif change == 'bad_hash':anchors = (replace(anchor, row_sha256='A'*64),)
    elif change == 'id_string':anchors = (replace(anchor, id=str(anchor.id)),)
    else:
        key = {'key_129':'x'*129, 'key_empty':'', 'key_slash':'private/key', 'key_unicode':'私密'}[change]
        anchors = (replace(anchor, key=key),)
    assert check(replace(declaration, anchors=anchors), before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('key', ['A', 'A'*128, 'A0._:-z'])
def test_valid_original_anchor_key_boundaries(key):
    declaration, before, after = sample_contract();anchors = (replace(declaration.anchors[0], key=key),)
    declaration = replace(declaration, anchors=anchors)
    before = replace(before, registration=replace(declaration), anchors=anchors)
    after = replace(after, registration=replace(declaration), anchors=anchors)
    assert check(declaration, before, after).classification == 'MATCH'


@pytest.mark.parametrize('change', ['naive','nonzero_timezone','same_end','reverse','revoked_without_time','active_with_time'])
def test_explicit_absolute_utc_and_revocation_time_shapes(change):
    declaration, before, after = sample_contract()
    edits = {'naive':{'valid_from':declaration.valid_from.replace(tzinfo=None)},
             'nonzero_timezone':{'valid_from':declaration.valid_from.astimezone(timezone(timedelta(hours=1)))},
             'same_end':{'valid_until':declaration.valid_from}, 'reverse':{'valid_until':declaration.valid_from-timedelta(seconds=1)},
             'revoked_without_time':{'revoked':True}, 'active_with_time':{'revoked_at':before.now}}
    assert check(replace(declaration, **edits[change]), before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('change', ['before_start','at_end','after_end','clock_regressed'])
def test_absolute_expiry_and_clock_boundaries(change):
    declaration, before, after = sample_contract()
    if change == 'before_start':before = replace(before, now=declaration.valid_from-timedelta(microseconds=1))
    elif change == 'at_end':after = replace(after, now=declaration.valid_until)
    elif change == 'after_end':after = replace(after, now=declaration.valid_until+timedelta(microseconds=1))
    else:after = replace(after, now=before.now-timedelta(microseconds=1))
    assert check(declaration, before, after).classification == 'MISMATCH'
    before = replace(before, now=declaration.valid_from);after = replace(after, now=declaration.valid_from)
    assert check(declaration, before, after).classification == 'MATCH'


@pytest.mark.parametrize('change', ['declaration_revoked','ever_revoked','revocation_rollback','revision_rollback',
    'revision_floor_rollback','below_known_revision'])
def test_terminal_revocation_and_known_revision_floors(change):
    declaration, before, after = sample_contract()
    if change == 'declaration_revoked':declaration = replace(declaration, revoked=True, revoked_at=before.now)
    elif change == 'ever_revoked':before = replace(before, ever_revoked=True);after = replace(after, ever_revoked=True)
    elif change == 'revocation_rollback':before = replace(before, ever_revoked=True)
    elif change == 'revision_rollback':after = replace(after, registration=replace(after.registration, revision=2))
    elif change == 'revision_floor_rollback':after = replace(after, minimum_revision=2)
    else:before = replace(before, minimum_revision=4);after = replace(after, minimum_revision=4)
    assert check(declaration, before, after).classification == 'MISMATCH'


@pytest.mark.parametrize('field,value', [('minimum_revision',True), ('ever_revoked',1), ('current_read',1),
    ('now',datetime(2026,10,11)), ('now',datetime(2026,10,11,tzinfo=timezone(timedelta(hours=1))))])
def test_malformed_observations_are_unknown(field, value):
    declaration, before, after = sample_contract()
    assert check(declaration, before, replace(after, **{field:value})).classification == 'UNKNOWN'


@pytest.mark.parametrize('field', ['installation','database','history','anchors','approved_manifest_sha256','registration'])
def test_independent_current_binding_mismatch_and_mid_observation_changes(field):
    declaration, before, after = sample_contract()
    replacements = {'installation':replace(before.installation, generation=8),
                    'database':replace(before.database, oid='43'),
                    'history':replace(before.history, org='another-enterprise'),
                    'anchors':(replace(before.anchors[0], row_sha256='d'*64),),
                    'approved_manifest_sha256':'e'*64, 'registration':replace(before.registration, revision=4)}
    # Both observations disagree with declaration; or the observation changed during the read.
    assert check(declaration, replace(before, **{field:replacements[field]}), replace(after, **{field:replacements[field]})).classification == 'MISMATCH'
    assert check(declaration, before, replace(after, **{field:replacements[field]})).classification == 'MISMATCH'


@pytest.mark.parametrize('binding,field,value', [
    ('installation', 'id', UUID(int=10)),
    ('installation', 'generation', 8),
    ('installation', 'root_ref', '/SYNTHETIC/other-install'),
    ('installation', 'owner_ref', 'other-install-owner'),
    ('database', 'name', 'other-db'),
    ('database', 'oid', '43'),
    ('database', 'system_identifier', '123456790'),
    ('database', 'data_directory_ref', '/SYNTHETIC/other-pg'),
    ('database', 'owner_role', 'other-db-owner'),
    ('history', 'owner', 'other-person'),
    ('history', 'park', 'other-park'),
    ('history', 'org', 'other-org'),
    ('history', 'preparation', UUID(int=11)),
    ('history', 'case', UUID(int=12)),
    ('history', 'run', UUID(int=13)),
    ('history', 'namespace', 'other-namespace'),
])
def test_each_exact_binding_change_is_detected_in_both_observation_positions(binding, field, value):
    declaration, before, after = sample_contract()
    changed = replace(getattr(before, binding), **{field: value})
    before_changed = replace(before, **{binding: changed})
    after_changed = replace(after, **{binding: changed})
    assert check(declaration, before_changed, after_changed).reason == 'BINDING_MISMATCH'
    assert check(declaration, before_changed, after).reason == 'OBSERVATION_CHANGED'
    assert check(declaration, before, after_changed).reason == 'OBSERVATION_CHANGED'


def test_valid_other_stage_and_other_original_anchor_cannot_replace_bound_history():
    declaration, before, after = sample_contract()
    _, p5_before, p5_after = sample_contract('P5')
    assert check(declaration, replace(before, history=p5_before.history),
                 replace(after, history=p5_after.history)).reason == 'BINDING_MISMATCH'
    for edits in ({'id': UUID(int=10)}, {'key': 'other-original'},
                  {'row_sha256': 'd'*64}, {'source_sha256': 'e'*64}):
        anchors = (replace(declaration.anchors[0], **edits),)
        assert check(declaration, replace(before, anchors=anchors),
                     replace(after, anchors=anchors)).reason == 'BINDING_MISMATCH'


@pytest.mark.parametrize('edits', [
    {'installation_owner_ref': 'other-install-owner'},
    {'database_owner_role': 'other-db-owner'},
    {'application_role': 'synthetic-db-owner'},
    {'application_role': '*'},
])
def test_maintainer_bindings_are_consistent_and_database_owner_is_separate_from_app(edits):
    declaration, before, after = sample_contract()
    changed = replace(declaration, maintainer=replace(declaration.maintainer, **edits))
    assert check(changed, before, after).reason == 'INVALID_DECLARATION'


@pytest.mark.parametrize('count', [1, 16])
def test_supported_anchor_count_boundaries_require_complete_independent_observations(count):
    declaration, before, after = sample_contract()
    anchors = tuple(replace(declaration.anchors[0], id=UUID(int=20+i), key=f'original-{i}')
                    for i in range(count))
    declaration = replace(declaration, anchors=anchors)
    before = replace(before, registration=replace(declaration), anchors=anchors)
    after = replace(after, registration=replace(declaration), anchors=anchors)
    assert check(declaration, before, after).classification == 'MATCH'
    assert check(declaration, before, replace(after, anchors=None)).classification == 'UNKNOWN'


@pytest.mark.parametrize('field', ['current_read', 'sources_current'])
def test_current_read_and_source_observation_do_not_become_permissions(field):
    declaration, before, after = sample_contract()
    assert check(declaration, replace(before, **{field:False}), replace(after, **{field:False})).classification == 'MISMATCH'


def test_restart_and_new_read_do_not_extend_expiry_or_revive_revocation():
    declaration, before, after = sample_contract()
    new_process_time = declaration.valid_until
    assert check(declaration, replace(before, now=new_process_time), replace(after, now=new_process_time)).classification == 'MISMATCH'
    attempted_renewal = replace(declaration, valid_from=new_process_time, valid_until=new_process_time+timedelta(hours=8))
    assert check(attempted_renewal, before, after).classification == 'MISMATCH'
    before = replace(before, ever_revoked=True, current_read=True)
    after = replace(after, ever_revoked=True, current_read=True)
    assert check(declaration, before, after).classification == 'MISMATCH'


def test_complete_indistinguishable_replay_is_not_claimed_to_be_defended():
    declaration, before, after = sample_contract()
    # A pure function cannot tell these consistent fixture inputs from a whole
    # restored snapshot whose external markers are also replayed or falsely labelled.
    assert check(declaration, before, after).classification == 'MATCH'
    assert check(declaration, replace(before, generation_known=None), after).classification == 'UNKNOWN'
    with pytest.raises(TypeError):bool(check(declaration, before, after))


def test_models_are_exact_immutable_types_and_unknown_objects_fail_closed():
    declaration, before, after = sample_contract()
    with pytest.raises(FrozenInstanceError):declaration.revision = 10
    with pytest.raises(TypeError):rc.RegistrationDeclaration(**asdict(declaration), unexpected=True)
    assert check(asdict(declaration), before, after).classification == 'MISMATCH'
    assert check(declaration, asdict(before), after).classification == 'UNKNOWN'
    class Other(rc.IndependentObservation):pass
    child = Other(*[getattr(before, f) for f in before.__dataclass_fields__])
    assert check(declaration, child, after).classification == 'UNKNOWN'


def test_pure_checker_does_not_use_io_environment_or_clock_discovery(monkeypatch):
    declaration, before, after = sample_contract()
    import builtins, os, socket, sqlite3
    def forbidden(*args, **kwargs):raise AssertionError('I/O or environment discovery attempted')
    for obj, name in [(builtins,'open'),(os,'getenv'),(os,'open'),(socket,'socket'),(sqlite3,'connect'),
                      (Path,'open'),(Path,'read_text'),(Path,'write_text')]:monkeypatch.setattr(obj, name, forbidden)
    assert check(declaration, before, after).classification == 'MATCH'


def test_module_imports_only_pure_stdlib_and_original_contracts_are_compatible():
    tree = ast.parse(inspect.getsource(rc))
    imports = {node.module if isinstance(node,ast.ImportFrom) else node.names[0].name
               for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))}
    assert imports <= {'dataclasses','datetime','pathlib','re','uuid'}
    from parkweave import history_summary as hs
    for stage, pinned in [('P4',rc.P4_DOCUMENT),('P5',rc.P5_DOCUMENT)]:
        checks = hs._checks(stage, 'synthetic')
        assert pinned == (checks.storage_scope, checks.document_version, checks.execution_contract)


def test_classification_has_no_api_registration_or_loading_effect():
    from fastapi.testclient import TestClient
    from parkweave.api import create_app
    class NoDatabaseStore:
        def __init__(self):self.audits = []
        def connect(self):raise AssertionError('pure contract attempted database access')
        def audit_denial(self, token):self.audits.append(token)
    declaration, before, after = sample_contract();result = check(declaration, before, after)
    store = NoDatabaseStore();store.summary_reader = result
    route = f'/api/cases/{declaration.history.case}/preparations/{declaration.history.preparation}/history-summary/P4'
    for kwargs in ({}, {'summary_reader':result}):
        with TestClient(create_app(store, **kwargs)) as client:
            assert client.get(route, headers={'Authorization':'Bearer synthetic-only'}).status_code == 403
    assert store.audits == ['synthetic-only','synthetic-only']
