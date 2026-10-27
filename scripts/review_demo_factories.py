"""Factories for three owned local-only review servers. No product Store/PG."""
from pathlib import Path
import os
from parkweave.review_demo import create_review_app
from parkweave.rule_publication_candidate import CandidateEngine,CandidateRepository
from parkweave.rule_publication_candidate_api import create_candidate_app
from parkweave.run_access_candidate import RunAccessEngine,RunAccessRepository
from parkweave.run_access_candidate_api import create_run_access_candidate_app
from scripts.rule_candidate_demo import mock_config as rule_config
from scripts.run_access_candidate_demo import mock_config as access_config

NAMESPACE='ISOLATED_SYNTHETIC_REVIEW_DEMO'
def enabled():return os.environ.get('PARKWEAVE_REVIEW_MODE')==NAMESPACE
def root():return Path(os.environ['PARKWEAVE_REVIEW_EVIDENCE_ROOT'])
def _health(app,kind):
    @app.get('/__review_health')
    def health():return {'instance_id':os.environ['PARKWEAVE_REVIEW_INSTANCE'],'kind':kind,'isolated_mock_enabled':enabled()}
    return app
def hub_app():return create_review_app(root(),enabled(),int(os.environ['PARKWEAVE_REVIEW_BASE_PORT']),os.environ['PARKWEAVE_REVIEW_INSTANCE'])
def rules_app():
    if not enabled():return _health(create_candidate_app(),'rules')
    path=Path(os.environ['PARKWEAVE_REVIEW_STATE'])/'rules.candidate.sqlite3'
    return _health(create_candidate_app(CandidateEngine(rule_config(),CandidateRepository(path))),'rules')
def access_app():
    if not enabled():return _health(create_run_access_candidate_app(),'access')
    cfg=access_config();cfg.runs=cfg.runs[:1];scope=cfg.runs[0].scope;cfg.permits=[p for p in cfg.permits if p.scope==scope]
    path=Path(os.environ['PARKWEAVE_REVIEW_STATE'])/'access.run-access.candidate.sqlite3'
    return _health(create_run_access_candidate_app(RunAccessEngine(cfg,RunAccessRepository(path))),'access')
