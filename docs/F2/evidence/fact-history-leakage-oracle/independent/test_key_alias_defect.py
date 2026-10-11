import importlib.util
import json
import pytest

spec=importlib.util.spec_from_file_location('historical_c78_oracle','/tmp/parkweave-oracle-independent-review/frozen_c78c4922_oracle.py')
oracle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)

def test_oracle_rejects_private_str_key_alias():
    class PrivateKey(str):
        def __hash__(self):return hash('qualification')
        def __eq__(self,other):return other=='qualification'
    result=oracle.public_projection('a'*64)
    value=result.pop('qualification')
    result[PrivateKey('PRIVATE_EXCERPT_KEY')]=value
    assert 'PRIVATE_EXCERPT_KEY' in json.dumps(result)
    with pytest.raises(AssertionError):
        oracle.assert_public_projection_only(result,'a'*64)

def test_input_nonmutation_rejects_equal_float_replacement(monkeypatch):
    def equal_value_mutation(*args):
        row=next(row for row in args[3] if row['field_name']=='employees')
        assert type(row['value']) is int
        row['value']=17.0
        return {}
    monkeypatch.setattr(oracle.read,'project',equal_value_mutation)
    with pytest.raises(AssertionError):
        oracle.test_projection_does_not_mutate_input_independently_of_output_assertions()
