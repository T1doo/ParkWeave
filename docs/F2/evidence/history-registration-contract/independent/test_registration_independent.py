"""Independent pure synthetic observations; no application, PG or execution use."""
from dataclasses import replace, asdict
from datetime import datetime, timedelta, timezone, tzinfo
from uuid import UUID
import ast
import builtins
import inspect
import json
import pytest
from parkweave import history_registration_contract as rc

START=datetime(2026,10,11,tzinfo=timezone.utc)
NOW=START+timedelta(minutes=30)

def declaration(stage='P4',count=1,key='Independent.Exact-Key:42_'):
    # Each call constructs separate explicit fixture data. No declaration hash,
    # proof or file is used to discover observation fields or trust labels.
    installation=rc.InstallationBinding(UUID(int=101),19,'/SYNTHETIC/independent-root','owner-install')
    db=rc.DatabaseBinding('synthetic-independent-db','400','111222333','/SYNTHETIC/independent-pg','owner-db')
    pinned=rc.P4_DOCUMENT if stage=='P4' else rc.P5_DOCUMENT
    history=rc.HistoryBinding('synthetic-independent-person','park-probe','org-probe',
        UUID(int=201),UUID(int=202),UUID(int=203),stage,pinned[0],'probe-namespace',pinned[1],pinned[2])
    anchors=tuple(rc.OriginalAnchor(UUID(int=300+i),key if count==1 else f'Independent-Key:{i}',
        'a'*64,'b'*64) for i in range(count))
    return rc.RegistrationDeclaration(rc.DECLARATION_KIND,1,rc.PURPOSE,UUID(int=501),8,
        rc.MaintainerBinding('owner-install','owner-db','application-select-only'),
        'independent-synthetic-approval','c'*64,installation,db,history,anchors,
        START,START+timedelta(hours=3),False,None)

def observation(stage='P4',count=1,key='Independent.Exact-Key:42_',now=NOW):
    # Independently assemble current observed values, never inspect a candidate.
    current=declaration(stage,count,key)
    return rc.IndependentObservation(rc.OBSERVATION_KIND,True,True,True,current,
        rc.InstallationBinding(UUID(int=101),19,'/SYNTHETIC/independent-root','owner-install'),
        rc.DatabaseBinding('synthetic-independent-db','400','111222333','/SYNTHETIC/independent-pg','owner-db'),
        rc.HistoryBinding('synthetic-independent-person','park-probe','org-probe',UUID(int=201),
            UUID(int=202),UUID(int=203),stage,rc.P4_DOCUMENT[0] if stage=='P4' else rc.P5_DOCUMENT[0],
            'probe-namespace',2 if stage=='P4' else 3,rc.P4_DOCUMENT[2] if stage=='P4' else rc.P5_DOCUMENT[2]),
        tuple(rc.OriginalAnchor(UUID(int=300+i),key if count==1 else f'Independent-Key:{i}','a'*64,'b'*64)
            for i in range(count)), 'c'*64,8,False,True,True,now)

def check(d=None,b=None,a=None):
    return rc.check_history_registration_contract(declaration() if d is None else d,
        observation() if b is None else b,observation(now=NOW+timedelta(seconds=1)) if a is None else a,
        enabled_for_synthetic_checks=True)

@pytest.mark.parametrize('enabled',[False,None,0,1,'true',[],{}])
def test_default_disabled_does_not_inspect_inputs(enabled):
    class Poison:
        def __getattribute__(self,name):raise AssertionError('default inspected input')
    result=rc.check_history_registration_contract(Poison(),Poison(),Poison(),enabled_for_synthetic_checks=enabled)
    assert asdict(result)=={'classification':'UNKNOWN','reason':'DEFAULT_DISABLED'}

@pytest.mark.parametrize('stage',['P4','P5'])
@pytest.mark.parametrize('count',[1,16])
def test_exact_consistency_is_data_without_permission(stage,count):
    d=declaration(stage,count);b=observation(stage,count);a=observation(stage,count,now=NOW+timedelta(seconds=1))
    originals=(asdict(d),asdict(b),asdict(a));result=check(d,b,a)
    assert asdict(result)=={'classification':'MATCH','reason':'SYNTHETIC_DECLARATION_CONSISTENT_ONLY'}
    assert originals==(asdict(d),asdict(b),asdict(a))
    with pytest.raises(TypeError):bool(result)
    assert set(asdict(result))=={'classification','reason'}
    for private in ('probe','owner-db','proof','lease','grant','Independent-Key'):
        assert private not in json.dumps(asdict(result))

@pytest.mark.parametrize('field',['complete','generation_known','maintenance_isolated','registration',
    'installation','database','history','anchors','approved_manifest_sha256','minimum_revision',
    'ever_revoked','current_read','sources_current','now'])
@pytest.mark.parametrize('position',['before','after'])
def test_missing_independent_observation_never_inferred(field,position):
    d=declaration();b=observation();a=observation(now=NOW+timedelta(seconds=1))
    if position=='before':b=replace(b,**{field:None})
    else:a=replace(a,**{field:None})
    assert check(d,b,a).classification=='UNKNOWN'

@pytest.mark.parametrize('field,value',[('generation_known',1),('maintenance_isolated','true'),
    ('minimum_revision',True),('ever_revoked',0),('current_read',1),('sources_current','true')])
def test_observation_scalar_types_are_exact(field,value):
    assert check(a=replace(observation(),**{field:value})).classification=='UNKNOWN'

@pytest.mark.parametrize('binding,field,value',[
    ('installation','generation',20),('installation','root_ref','/SYNTHETIC/other-root'),
    ('database','system_identifier','111222334'),('database','data_directory_ref','/SYNTHETIC/other-pg'),
    ('database','oid','401'),('history','owner','other-person'),('history','org','other-org'),
    ('history','case',UUID(int=222)),('history','run',UUID(int=223)),('history','preparation',UUID(int=224))])
def test_independent_binding_change_detected_before_and_during(binding,field,value):
    b=observation();a=observation(now=NOW+timedelta(seconds=1))
    changed=replace(getattr(b,binding),**{field:value})
    assert check(b=replace(b,**{binding:changed}),a=replace(a,**{binding:changed})).classification=='MISMATCH'
    assert check(b=b,a=replace(a,**{binding:changed})).reason=='OBSERVATION_CHANGED'

@pytest.mark.parametrize('change',['terminal_seen','revocation_rollback','revoked_current','floor_rollback',
    'declaration_revision_rollback','observed_revision_rollback','expired_after','before_start','clock_regression'])
def test_terminal_revision_and_absolute_time_guards(change):
    d=declaration();b=observation();a=observation(now=NOW+timedelta(seconds=1))
    if change=='terminal_seen':b=replace(b,ever_revoked=True);a=replace(a,ever_revoked=True)
    elif change=='revocation_rollback':b=replace(b,ever_revoked=True)
    elif change=='revoked_current':
        withdrawn=replace(b.registration,revoked=True,revoked_at=NOW)
        b=replace(b,registration=withdrawn);a=replace(a,registration=withdrawn)
    elif change=='floor_rollback':a=replace(a,minimum_revision=7)
    elif change=='declaration_revision_rollback':d=replace(d,revision=7)
    elif change=='observed_revision_rollback':a=replace(a,registration=replace(a.registration,revision=7))
    elif change=='expired_after':a=replace(a,now=d.valid_until)
    elif change=='before_start':b=replace(b,now=d.valid_from-timedelta(microseconds=1))
    else:a=replace(a,now=NOW-timedelta(microseconds=1))
    assert check(d,b,a).classification=='MISMATCH'

@pytest.mark.parametrize('change',['bool_revision','same_app_owner','oid_leading_zero','sid_overflow',
    'root_parent','relative_db','anchor_key_129','anchor_duplicate','too_many_anchors','utc_naive'])
def test_structurally_invalid_declaration_cannot_match(change):
    d=declaration()
    if change=='bool_revision':d=replace(d,revision=True)
    elif change=='same_app_owner':d=replace(d,maintainer=replace(d.maintainer,application_role='owner-db'))
    elif change=='oid_leading_zero':d=replace(d,database=replace(d.database,oid='0400'))
    elif change=='sid_overflow':d=replace(d,database=replace(d.database,system_identifier=str(2**64)))
    elif change=='root_parent':d=replace(d,installation=replace(d.installation,root_ref='C:\\synthetic\\..\\root'))
    elif change=='relative_db':d=replace(d,database=replace(d.database,data_directory_ref='relative'))
    elif change=='anchor_key_129':d=replace(d,anchors=(replace(d.anchors[0],key='K'*129),))
    elif change=='anchor_duplicate':d=replace(d,anchors=d.anchors*2)
    elif change=='too_many_anchors':d=replace(d,anchors=declaration(count=17).anchors)
    else:d=replace(d,valid_from=d.valid_from.replace(tzinfo=None))
    assert check(d).reason=='INVALID_DECLARATION'

def test_exact_anchor_key_128_and_p5_mismatch():
    d=declaration(key='K'*128);b=observation(key='K'*128);a=observation(key='K'*128,now=NOW+timedelta(seconds=1))
    assert check(d,b,a).classification=='MATCH'
    different=observation('P5')
    assert check(declaration(),replace(b,history=different.history),replace(a,history=different.history)).classification=='MISMATCH'

def test_untrusted_tzinfo_callbacks_are_not_invoked():
    class CallbackTZ(tzinfo):
        def utcoffset(self,dt):raise AssertionError('caller tz callback invoked')
    unsafe=datetime(2026,10,11,tzinfo=CallbackTZ())
    assert check(a=replace(observation(),now=unsafe)).classification=='UNKNOWN'
    assert check(replace(declaration(),valid_until=unsafe)).classification=='MISMATCH'

def test_exact_models_reject_dict_and_subclass():
    assert check(asdict(declaration())).classification=='MISMATCH'
    result=rc.check_history_registration_contract(declaration(),asdict(observation()),observation(),enabled_for_synthetic_checks=True)
    assert result.classification=='UNKNOWN'
    class Child(rc.InstallationBinding):pass
    bad=Child(UUID(int=101),19,'/SYNTHETIC/independent-root','owner-install')
    assert check(replace(declaration(),installation=bad)).classification=='MISMATCH'

def test_matching_hash_and_same_sid_do_not_supply_missing_current_generation():
    b=replace(observation(),generation_known=None)
    assert check(b=b).classification=='UNKNOWN'
    for label in ('SAME_SID_FILE','LEGACY_PROOF','DECLARATION_SELF_REPORT'):
        assert check(b=replace(observation(),kind=label)).classification=='UNKNOWN'

def test_complete_indistinguishable_replay_remains_unprovable():
    # Replayed old inputs include time/revocation/floor/generation observations.
    # No pure data comparison can establish they are independently current.
    d=declaration();b=observation();a=observation(now=NOW+timedelta(seconds=1))
    assert check(d,b,a).classification=='MATCH'
    assert check(d,replace(b,generation_known=False),a).classification=='UNKNOWN'
    later=observation(now=d.valid_until)
    assert check(d,later,later).classification=='MISMATCH'

def test_no_io_discovery_or_production_call_graph(monkeypatch):
    tree=ast.parse(inspect.getsource(rc))
    imports={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    imports|={a.name for node in ast.walk(tree) if isinstance(node,ast.Import) for a in node.names}
    assert imports <= {'dataclasses','datetime','pathlib','re','uuid'}
    d=declaration();b=observation();a=observation()
    import os,socket,sqlite3
    from pathlib import Path
    def forbidden(*args,**kwargs):raise AssertionError('I/O/discovery attempted')
    with monkeypatch.context() as guard:
        for target,name in [(builtins,'open'),(os,'open'),(os,'getenv'),(socket,'socket'),
            (sqlite3,'connect'),(Path,'open'),(Path,'read_text'),(Path,'write_text')]:
            guard.setattr(target,name,forbidden)
        assert check(d,b,a).classification=='MATCH'
