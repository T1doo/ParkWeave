"""Explicit separate local Mock factory; no identities/Grant/assignment writes."""
from pathlib import Path
import os
from parkweave.run_access_candidate import RunAccessConfig,RunAccessRepository,RunAccessEngine,NAMESPACE
from parkweave.run_access_candidate_api import create_run_access_candidate_app

def mock_config():
    validity={'valid_from':'2019-01-01T00:00:00+00:00','valid_until':'2099-01-01T00:00:00+00:00','timezone':'UTC'}
    scopes=[{'park_id':'park-a','org_id':'org-a','run_id':id} for id in ('mock-run-a','mock-run-b')]
    # Approval is explicit exact-Run Mock authority, never inferred from the role.
    roles={'mock-run-owner':'enterprise_operator','mock-run-access-approver':'park_specialist','prep-specialist-fixture-a':'park_specialist','mock-run-executor':'service_executor','mock-other-owner':'enterprise_operator','mock-other-executor':'service_executor','mock-resource-reader':'resource_admin'}
    personas=[{'id':id,'park_id':'park-a','org_id':'org-b' if id.startswith('mock-other') else 'org-a','role':role} for id,role in roles.items()]
    actions={'mock-run-owner':['STATUS','REQUEST','CANCEL','REVOKE'],'mock-run-access-approver':['STATUS','APPROVE','REJECT','REVOKE'],'prep-specialist-fixture-a':['STATUS'],'mock-run-executor':['STATUS','ACCESS'],'mock-resource-reader':['STATUS']}
    return RunAccessConfig.model_validate({'enabled_for_isolated_tests':True,'personas':personas,'read_facts':[{'principal_id':p['id'],'park_id':p['park_id'],'org_id':p['org_id'],'validity':validity} for p in personas],
        'permits':[{'id':'permit-'+actor+'-'+scope['run_id'],'principal_id':actor,'scope':scope,'actions':acts,'validity':validity} for actor,acts in actions.items() for scope in scopes],
        'runs':[{'scope':s,'owner_id':'mock-run-owner','revision':1,'source_ref':{'id':s['run_id'],'kind':'SYNTHETIC','revision':'1'},'snapshot':'SYNTHETIC '+s['run_id']+' read-only local fixture; not an actual product Run or receipt'} for s in scopes]})

def configured_mock_app():
    path=os.environ.get('PARKWEAVE_RUN_ACCESS_TEST_DB')
    if os.environ.get('PARKWEAVE_RUN_ACCESS_ENABLE_TESTS')!=NAMESPACE or not path:return create_run_access_candidate_app()
    return create_run_access_candidate_app(RunAccessEngine(mock_config(),RunAccessRepository(Path(path))))
