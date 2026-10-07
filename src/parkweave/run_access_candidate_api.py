"""Standalone offline candidate only; not mounted in the deployment API."""
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from pydantic import ValidationError
from .run_access_candidate import RunScope,RunCommand,AccessProbe,RunAccessEngine,Denied,Conflict

def create_run_access_candidate_app(engine=None):
    engine=engine or RunAccessEngine();app=FastAPI(title='Isolated single Run READ access candidate')
    @app.exception_handler(Denied)
    async def denied(request,exc):return JSONResponse({'detail':str(exc),'candidate_read_allowed':False,'actual_run_access':False,'deployment_enabled':False},status_code=403)
    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':str(exc),'candidate_read_allowed':False,'deployment_enabled':False},status_code=409)
    @app.get('/',response_class=HTMLResponse)
    def page():return Path(__file__).with_name('run_access_candidate_web.html').read_text()
    @app.get('/api/run-access/status')
    def status():return engine.status()
    def scope(park,org,run):
        try:return RunScope(park_id=park,org_id=org,run_id=run)
        except ValidationError as e:raise HTTPException(422,'invalid candidate scope') from e
    @app.get('/api/run-access/{park}/{org}/{run}')
    def read(park:str,org:str,run:str,x_mock_actor:str|None=Header(default=None)):return engine.read(x_mock_actor,scope(park,org,run))
    @app.post('/api/run-access/{park}/{org}/{run}/commands')
    def command(park:str,org:str,run:str,data:RunCommand,x_mock_actor:str|None=Header(default=None),idempotency_key:str=Header(min_length=1,max_length=100)):return engine.command(x_mock_actor,scope(park,org,run),idempotency_key,data)
    @app.post('/api/run-access/{park}/{org}/{run}/probe')
    def probe(park:str,org:str,run:str,data:AccessProbe,x_mock_actor:str|None=Header(default=None)):return engine.access(x_mock_actor,scope(park,org,run),data)
    return app
