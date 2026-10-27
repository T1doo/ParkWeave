from parkweave.model_config import resolve_intern_token


def test_project_token_priority_common_fallback_and_empty():
    token=resolve_intern_token({'PARKWEAVE_INTERN_API_TOKEN':'synthetic-project-token','INTERN_API_TOKEN':'synthetic-common-token'})
    assert token.get_secret_value()=='synthetic-project-token'
    assert 'synthetic-project-token' not in repr(token) and 'synthetic-project-token' not in str(token)
    assert resolve_intern_token({'INTERN_API_TOKEN':'synthetic-common-token'}).get_secret_value()=='synthetic-common-token'
    assert resolve_intern_token({'PARKWEAVE_INTERN_API_TOKEN':' ','INTERN_API_TOKEN':'synthetic-common-token'}).get_secret_value()=='synthetic-common-token'
    assert resolve_intern_token({}) is None and resolve_intern_token({'INTERN_API_TOKEN':''}) is None
