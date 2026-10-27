"""Separate mock-only app, deliberately not mounted in the deployment API."""
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import Field, ValidationError
from .domain import Contract
from .rule_publication_candidate import CandidateEngine, Scope, Command
from .store import Denied, Conflict

class Assess(Contract):
    expected_revision: int=Field(ge=0,le=64)
    expected_source_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')

def create_candidate_app(engine=None):
    engine=engine or CandidateEngine()
    app=FastAPI(title='ParkWeave isolated candidate; deployment disabled')
    @app.exception_handler(Denied)
    async def denied(request,exc):return JSONResponse({'detail':str(exc),'deployment_enabled':False},status_code=403)
    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':str(exc)},status_code=409)
    @app.get('/',response_class=HTMLResponse)
    def page():return Path(__file__).with_name('rule_publication_candidate_web.html').read_text()
    @app.get('/api/candidate/status')
    def status():return engine.status()
    def scope(park,org,service):
        try:return Scope(park_id=park,org_id=org,service_id=service)
        except ValidationError as e:raise HTTPException(422,'invalid candidate scope') from e
    @app.get('/api/candidate/{park}/{org}/{service}')
    def read(park:str,org:str,service:str,x_mock_actor:str|None=Header(default=None)):
        return engine.read(x_mock_actor,scope(park,org,service))
    @app.post('/api/candidate/{park}/{org}/{service}/commands')
    def command(park:str,org:str,service:str,data:Command,x_mock_actor:str|None=Header(default=None),idempotency_key:str=Header(min_length=1,max_length=100)):
        return engine.command(x_mock_actor,scope(park,org,service),idempotency_key,data)
    @app.post('/api/candidate/{park}/{org}/{service}/assessments')
    def assess(park:str,org:str,service:str,data:Assess,x_mock_actor:str|None=Header(default=None)):
        return engine.assess(x_mock_actor,scope(park,org,service),data.expected_revision,data.expected_source_sha256)
    return app
