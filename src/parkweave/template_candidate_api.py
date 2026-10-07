"""Standalone isolated template app. The deployment API never mounts this app."""
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .template_candidate import TemplateEngine, Scope, Command
from .store import Denied, Conflict


def create_template_candidate_app(engine=None,consumer=None):
    engine=engine or TemplateEngine()
    app=FastAPI(title='ParkWeave isolated template candidate; business publication disabled')

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        response=None
        if request.method in ('POST','PUT','PATCH'):
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>16384:
                    response=JSONResponse({'detail':'request exceeds 16 KiB'},status_code=413);break
            if response is None:request._body=bytes(body)
        if response is None:response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.exception_handler(Denied)
    async def denied(request,exc):return JSONResponse({'detail':str(exc),'business_publication':False,'deployment_enabled':False},status_code=403)

    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':str(exc)},status_code=409)

    @app.get('/',response_class=HTMLResponse)
    def page():return Path(__file__).with_name('template_candidate_web.html').read_text(encoding='utf-8')

    @app.get('/api/template-candidate/status')
    def status():return engine.status()

    def scope(park,template):
        try:return Scope(park_id=park,template_id=template)
        except ValidationError as e:raise HTTPException(422,'invalid isolated template scope') from e

    @app.get('/api/template-candidate/{park}/{template}')
    def read(park:str,template:str,x_isolated_template_actor:str|None=Header(default=None)):
        return engine.read(x_isolated_template_actor,scope(park,template))

    @app.post('/api/template-candidate/{park}/{template}/commands')
    def command(park:str,template:str,data:Command,x_isolated_template_actor:str|None=Header(default=None),idempotency_key:str=Header(min_length=1,max_length=100)):
        return engine.command(x_isolated_template_actor,scope(park,template),idempotency_key,data)

    if consumer is not None:
        if not engine.config.enabled_for_isolated_tests or not consumer.config.enabled_for_isolated_tests:raise ValueError('explicit isolated template and consumer contracts required for consumer routes')
        if consumer.template_engine is not engine:raise ValueError('consumer must use this exact isolated template engine')
        engine.status()
        consumer.validate_fixture()
        from .template_consumer import install_routes
        install_routes(app,consumer)
    return app
