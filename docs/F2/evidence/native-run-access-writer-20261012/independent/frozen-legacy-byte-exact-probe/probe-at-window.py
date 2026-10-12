"""Use byte-exact prior Native source to create a genuine pre-writer receipt."""
import sys
import types
from pathlib import Path
from uuid import UUID
from test_preparation import preparation_fixture, filled, command as material
from test_executor_receipts import receipt_fixture
from test_native_run_access import APPROVER
from parkweave import native_run_access as current


def test_pre_writer_receipt_original_key_survives_new_optional_field(receipt_fixture):
    source=Path(__file__).with_name('pre-writer-native.py.txt')
    module=types.ModuleType('parkweave._independent_pre_writer_native')
    module.__package__='parkweave';module.__file__=str(source)
    sys.modules[module.__name__]=module
    exec(compile(source.read_bytes(),str(source),'exec'),module.__dict__)
    f=receipt_fixture;parent=filled(f)
    parent=material(f,parent,'REVIEW',APPROVER,reason='SYNTHETIC original review').json()
    parent=material(f,parent,'CONFIRM',reason='SYNTHETIC original owner confirmation').json()
    module.install_owned_test_storage(f[1],f[1]._case_fact_fixture_receipt)
    prior_permit=module.issue_decision_test_permit(f[1],f[1]._case_fact_fixture_receipt,approver_ids={APPROVER})
    prior=module.NativeRunAccess(f[0],test_permit=prior_permit)
    from datetime import datetime,timedelta,timezone
    view=prior.read(f[2]['fixture-a'],UUID(parent['run_id']));now=datetime.now(timezone.utc)
    fields=dict(action='REQUEST',expected_revision=view['revision'],expected_run_revision=view['run_revision'],
        expected_authority_sha256=view['authority_sha256'],reason='SYNTHETIC original request',
        target_id='executor-a',target_role='service_executor',capability='READ',
        requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(seconds=120)).isoformat(),timezone='UTC'))
    old_data=module.RunCommand.model_validate(fields)
    original=prior.command(f[2]['fixture-a'],UUID(parent['run_id']),'byte-exact-prior-key',old_data)
    assert original['fingerprint']==module._hash(dict(run_id=parent['run_id'],command=old_data.model_dump(mode='json')))
    new_permit=current.issue_decision_test_permit(f[1],f[1]._case_fact_fixture_receipt,approver_ids={APPROVER})
    bridge=current.NativeRunAccess(f[0],test_permit=new_permit)
    replay=bridge.command(f[2]['fixture-a'],UUID(parent['run_id']),'byte-exact-prior-key',current.RunCommand.model_validate(fields))
    assert replay==original
