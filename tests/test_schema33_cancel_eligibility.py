"""Pure eligibility boundaries only: fake SQL responses are not PostgreSQL proof."""
import pytest
from parkweave import case_cancellation_before_receipt as cb, service_dispatches as sd
from parkweave.store import Store


class Result:
    def __init__(self, row):
        self.row = row
    def fetchone(self):
        return self.row


class SchemaConnection:
    def __init__(self, version=33, has29=True):
        self.version, self.has29 = version, has29
    def execute(self, query):
        if query == 'SELECT max(version) v FROM schema_version':
            return Result({'v': self.version})
        if query == 'SELECT 1 FROM schema_version WHERE version=29':
            return Result({'present': 1} if self.has29 else None)
        raise AssertionError(query)


@pytest.mark.parametrize('version', [None, 28, 29, 30, 31, 32, 33, 34, 999])
def test_only_exact_schema33_enters_the_additional_before_receipt_gate(version):
    assert cb._before_receipt_schema33_enabled(object.__new__(Store), SchemaConnection(version)) is (version == 33)


def test_schema33_still_requires_original_schema29_marker():
    assert not cb._before_receipt_schema33_enabled(object.__new__(Store), SchemaConnection(has29=False))


@pytest.mark.parametrize('attribute', [
    '_isolated_run_access', '_isolated_local_execution', '_isolated_execution_preview',
    '_isolated_resource_execution_preview', '_isolated_dispatch_execution_preview',
    '_isolated_receipt_execution_preview', '_isolated_lifecycle_execution_preview'])
def test_additional_schema33_gate_refuses_every_isolated_provider_attribute(attribute):
    store = object.__new__(Store)
    setattr(store, attribute, object())
    assert not cb._before_receipt_schema33_enabled(store, SchemaConnection())


@pytest.mark.parametrize('kind', ['subclass', 'untyped'])
def test_additional_schema33_gate_requires_exact_original_store_type(kind):
    class DerivedStore(Store):
        pass
    store = object.__new__(DerivedStore) if kind == 'subclass' else object()
    assert not cb._before_receipt_schema33_enabled(store, SchemaConnection())


def test_handoff_original_gate_remains_closed_for_schema33():
    assert not sd._handoff_enabled(object.__new__(Store), SchemaConnection())
