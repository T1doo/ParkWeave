"""Old default-closed Native DTO shape must keep the original POST fingerprint."""
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_native_run_access import native_fixture, body
from parkweave.run_access_candidate import RunCommand as PreWriterCommand
from parkweave import native_run_access as native
from uuid import UUID


def test_pre_writer_native_original_key_compatible_with_optional_confirmation(native_fixture):
    f,parent,bridge,_=native_fixture
    current=body(native_fixture,'REQUEST')
    historical=PreWriterCommand.model_validate(current.model_dump(mode='json',exclude={'confirm_request'}))
    original=bridge.command(f[2]['fixture-a'],UUID(parent['run_id']),'pre-writer-original',historical)
    assert original['fingerprint']==native._hash(dict(run_id=parent['run_id'],command=historical.model_dump(mode='json')))
    replay=bridge.command(f[2]['fixture-a'],UUID(parent['run_id']),'pre-writer-original',current)
    assert replay==original
