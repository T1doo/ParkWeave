"""Finite source diagnostics only; no token APIs or identity mutation."""
import json
from pathlib import Path
import pytest
from scripts.windows_ci.native_failure_diagnostics import detail,SourceSites
from scripts.windows_portable import restricted_token_candidate as token

PRIVATE='PRIVATE_TOKEN_SID_ACL_MUST_NOT_BE_LOGGED'


def test_token_failure_exposes_only_fixed_phase_and_numeric_error():
    error=token.TokenFailure(PRIVATE,PRIVATE,'QUERY_3',5)
    error.private_value=PRIVATE
    result=detail(error,'TokenFailure')
    assert result['category']=='TOKEN_OPERATION'
    assert result['restricted_token']==dict(phase='QUERY_3',winerror=5)
    assert PRIVATE not in json.dumps(result)


@pytest.mark.parametrize('phase,code',[(PRIVATE,5),('DERIVE',PRIVATE),('DERIVE',True),('DERIVE',-1),('DERIVE',2**32)])
def test_arbitrary_token_fields_are_not_serialized(phase,code):
    result=detail(token.TokenFailure(PRIVATE,None,phase,code),'TokenFailure')
    assert result['restricted_token']==dict(details='UNAVAILABLE')
    assert PRIVATE not in json.dumps(result)


def test_token_predicate_traceback_resolves_fixed_source_without_native_calls():
    sites=SourceSites(Path(__file__).resolve().parents[1],'a'*40)
    with pytest.raises(token.TokenRefused) as caught:token._need(False)
    result=detail(caught.value,'TokenRefused',sites)
    assert result['source_sites']['status']=='MATCHED'
    assert result['source_sites']['frames'][-1]['function']=='_need'
    assert result['source_sites']['frames'][-1]['module']==token.__name__
