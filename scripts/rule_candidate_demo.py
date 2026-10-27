"""Explicit isolated mock app; no deployment Store, grants, identities or credentials.
Run only via the local test harness. Without BOTH explicit flags the factory is disabled.
"""
import os
from pathlib import Path
from parkweave.rule_publication_candidate import CandidateConfig,CandidatePermit,MockPrincipal,Scope,CandidateRepository,CandidateEngine,NAMESPACE
from parkweave.rule_publication_candidate_api import create_candidate_app

def mock_config():
    scope=Scope(park_id='park-a',org_id='org-a',service_id='candidate-intake')
    validity={'valid_from':'2019-01-01T00:00:00+00:00','valid_until':'2099-01-01T00:00:00+00:00','timezone':'UTC'}
    # These are mock persona labels, not principals persisted in any deployment DB.
    roles={'fixture-a':'enterprise_operator','prep-specialist-fixture-a':'park_specialist','mock-publisher':'resource_admin','mock-executor':'service_executor','mock-other-org':'enterprise_operator'}
    actions={'fixture-a':['READ','SAVE','SUBMIT','RETURN_DRAFT'],'prep-specialist-fixture-a':['READ','REVIEW','REJECT'],'mock-publisher':['READ','PUBLISH','WITHDRAW'],'mock-executor':['READ'],'mock-other-org':['READ','SAVE']}
    return CandidateConfig(enabled_for_isolated_tests=True,principals=[MockPrincipal(id=id,role=role) for id,role in roles.items()],permits=[CandidatePermit(id='candidate-permit-'+id,principal_id=id,scope=scope if id!='mock-other-org' else Scope(park_id='park-a',org_id='org-b',service_id='candidate-intake'),actions=actions[id],validity=validity) for id in roles])

def configured_mock_app():
    path=os.environ.get('PARKWEAVE_CANDIDATE_TEST_DB')
    if os.environ.get('PARKWEAVE_CANDIDATE_ENABLE_TESTS')!=NAMESPACE or not path:return create_candidate_app()
    return create_candidate_app(CandidateEngine(mock_config(),CandidateRepository(Path(path))))
