"""Independent synthetic oracle controls; no DB, API or execution path."""
from copy import deepcopy
from uuid import UUID
import json
import pytest
import test_fact_history_read_source as oracle

EXPECTED='1ab214b54e972ae2231da520785615e66a899c101a448b4c8b963508627d5717'

def explicit_result(digest=EXPECTED):
    return {'contract':'SYNTHETIC_CASE_FACT_HISTORY_READ_V1','purpose':'SERVICE_PREPARATION',
        'fields':['region','employees','service_need'],'source_sha256':digest,'read_only':True,
        'execution_available':False,'qualification':'NOT_EVALUATED',
        'authenticity':'USER_ASSERTED_UNVERIFIED','proof_available':False}

def deterministic_input():
    values=iter(UUID(int=1003+i) for i in range(11))
    return oracle.sample(uuid_factory=lambda:next(values))

@pytest.mark.parametrize('digest',[EXPECTED,'17'+'a'*62])
def test_legal_complete_hash_containing_17_passes(digest):
    assert '17' in digest
    oracle.assert_public_projection_only(explicit_result(digest),digest)

def test_actual_deterministic_projection_matches_external_digest():
    args=deterministic_input();before=deepcopy(args)
    result=oracle.read.project(*args)
    assert result==explicit_result()
    assert result['source_sha256']==EXPECTED
    assert oracle.expected_source_digest(args)==EXPECTED
    assert type(next(row['value'] for row in args[3] if row['field_name']=='employees')) is int
    oracle.assert_public_projection_only(result,EXPECTED)
    assert args==before

@pytest.mark.parametrize('secret',[17,'PRIVATE_EXCERPT_FRAGMENT','00000000-0000-0000-0000-0000000003f1'])
@pytest.mark.parametrize('position',['unknown','scalar_append','fields_append','hash'])
def test_private_content_injected_anywhere_is_rejected(secret,position):
    result=explicit_result()
    if position=='unknown':result['hidden_private']=secret
    elif position=='scalar_append':result['qualification']+=':'+str(secret)
    elif position=='fields_append':result['fields'].append(secret)
    else:result['source_sha256']=secret
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)

@pytest.mark.parametrize('field',['contract','purpose','source_sha256','qualification','authenticity'])
def test_allowed_scalar_embedded_excerpt_is_rejected(field):
    result=explicit_result();result[field]='PRIVATE_EXCERPT_FRAGMENT:'+result[field]
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)

@pytest.mark.parametrize('replacement',['b'*64,'A'*64,'1'*64,EXPECTED[::-1]])
def test_hash_slot_cannot_accept_other_legal_hash_or_private_hex(replacement):
    result=explicit_result();result['source_sha256']=replacement
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)

@pytest.mark.parametrize('field',['read_only','execution_available','proof_available'])
@pytest.mark.parametrize('value',[0,1,0.0,1.0])
def test_flag_numeric_equality_never_replaces_boolean(field,value):
    result=explicit_result();result[field]=value
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)

@pytest.mark.parametrize('kind',['str','int'])
def test_key_alias_cannot_hide_private_output_key(kind):
    if kind=='str':
        class Alias(str):
            def __hash__(self):return hash('qualification')
            def __eq__(self,other):return other=='qualification'
        key=Alias('PRIVATE_EXCERPT_KEY')
    else:
        class Alias(int):
            def __hash__(self):return hash('qualification')
            def __eq__(self,other):return other=='qualification'
        key=Alias(17)
    result=explicit_result();value=result.pop('qualification');result[key]=value
    encoded=json.dumps(result)
    assert ('PRIVATE_EXCERPT_KEY' if kind=='str' else '"17"') in encoded
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)

def test_subclass_values_list_items_and_results_rejected():
    class Pretend(str):
        def __eq__(self,other):return True
    result=explicit_result();result['qualification']=Pretend('PRIVATE_FRAGMENT')
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)
    result=explicit_result();result['fields'][0]=Pretend('PRIVATE_FRAGMENT')
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(result,EXPECTED)
    class Child(dict):pass
    with pytest.raises(AssertionError):oracle.assert_public_projection_only(Child(explicit_result()),EXPECTED)

@pytest.mark.parametrize('kind',['equal_float','equal_bool','equal_revision','new_row','new_excerpt','key_alias'])
def test_input_assertion_rejects_mutation_even_when_values_compare_equal(monkeypatch,kind):
    def mutation(*args):
        if kind=='equal_float':next(row for row in args[3] if row['field_name']=='employees')['value']=17.0
        elif kind=='equal_bool':args[1]['active']=1
        elif kind=='equal_revision':args[0]['revision']=3.0
        elif kind=='new_row':args[3].append(deepcopy(args[3][0]))
        elif kind=='new_excerpt':args[3][0]['source_excerpt']='MUTATED_PRIVATE_EXCERPT'
        else:
            class Alias(str):
                def __hash__(self):return hash('source_excerpt')
                def __eq__(self,other):return other=='source_excerpt'
            value=args[3][0].pop('source_excerpt')
            args[3][0][Alias('MUTATED_PRIVATE_KEY')]=value
        return explicit_result()
    monkeypatch.setattr(oracle.read,'project',mutation)
    with pytest.raises(AssertionError):oracle.test_projection_does_not_mutate_input_independently_of_output_assertions()

def test_finally_executes_input_check_after_project_raises(monkeypatch):
    def mutate_and_raise(*args):
        args[1]['active']=1
        raise RuntimeError('synthetic projector failure')
    monkeypatch.setattr(oracle.read,'project',mutate_and_raise)
    with pytest.raises(AssertionError):oracle.test_projection_does_not_mutate_input_independently_of_output_assertions()

def test_no_mutation_preserves_original_project_exception(monkeypatch):
    def raise_only(*args):raise RuntimeError('synthetic projector failure')
    monkeypatch.setattr(oracle.read,'project',raise_only)
    with pytest.raises(RuntimeError,match='synthetic projector failure'):
        oracle.test_projection_does_not_mutate_input_independently_of_output_assertions()

def test_input_assertion_runs_independently_of_invalid_output(monkeypatch):
    def invalid_output(*args):return {'proof':'SYNTHETIC PRIVATE PROOF'}
    monkeypatch.setattr(oracle.read,'project',invalid_output)
    with pytest.raises(AssertionError):oracle.test_exact_projection_no_values_or_proof()
    oracle.test_projection_does_not_mutate_input_independently_of_output_assertions()
