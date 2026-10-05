import os
import re
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from .domain import Intake, FactInput, ClarificationInput, V1ServiceSpec, V1ServicePlan, FieldName
from .store import Store, Denied, Conflict


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="ParkWeave synthetic foundation", version="0.1.0")

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        # Count actual bytes as well as declared Content-Length; limit before JSON parsing.
        if request.method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    return JSONResponse({"detail": "request exceeds 16 KiB"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        if "Content-Security-Policy" not in response.headers:response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Denied)
    async def denied(request, exc):
        authorization=request.headers.get('authorization','')
        if authorization.startswith('Bearer '):store.audit_denial(authorization[7:])
        return JSONResponse({"detail": "record unavailable or authorization denied"}, status_code=403)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    def token(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "session required")
        return authorization[7:]

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("web.html").read_text()

    @app.get("/health")
    def health():
        with store.connect() as c:
            version = c.execute("SELECT max(version) version FROM schema_version").fetchone()["version"]
        return {"status": "ok", "project":"ParkWeave", "process_id":os.getpid(), "schema": version, "model": "MODEL_MOCK", "data": "SYNTHETIC", "execution_mode": store.mode}

    @app.post("/api/runs", status_code=202)
    def submit(data: Intake, authorization: str | None = Header(default=None),
               idempotency_key: str = Header()):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", idempotency_key):
            raise HTTPException(422, "invalid request key")
        if data.action == "fault.record" and store.mode != "FAULT_INJECTION":
            raise HTTPException(422, "fixture adapter disabled")
        return {"run_id": store.submit(token(authorization), idempotency_key, data)}

    @app.get("/api/runs/{run_id}")
    def read(run_id: UUID, authorization: str | None = Header(default=None)):
        return store.read(token(authorization), run_id)

    @app.get("/api/runs/{run_id}/plan-revisions")
    def plan_revisions(run_id: UUID, authorization: str | None = Header(default=None)):
        return {'revisions':store.read_plan_revisions(token(authorization),run_id)}

    @app.get('/api/runs/{run_id}/fact-review')
    def fact_review(run_id: UUID,authorization: str | None=Header(default=None)):
        from .fact_review_store import read
        return read(store,token(authorization),run_id)

    @app.post('/api/runs/{run_id}/clarifications',status_code=202)
    def clarification(run_id: UUID,data: ClarificationInput,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        from .fact_review_store import followup
        return followup(store,token(authorization),run_id,idempotency_key,data)

    @app.post("/api/runs/{run_id}/{intent}")
    def control(run_id: UUID, intent: Literal["pause", "cancel", "resume", "reconcile"],
                authorization: str | None = Header(default=None)):
        store.control(token(authorization), run_id, intent)
        return {"intent": intent, "external_reversal": False}

    @app.post('/api/facts',status_code=201)
    def save_fact(data: FactInput, authorization: str | None=Header(default=None), idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return {'fact_id':store.save_fact(token(authorization),idempotency_key,data),'source':'USER_ASSERTED_SYNTHETIC'}

    @app.get('/api/facts')
    def facts(fields: list[FieldName]=Query(), authorization: str | None=Header(default=None)):
        if not 1<=len(fields)<=3 or len(set(fields))!=len(fields):raise HTTPException(422,'explicit unique fields required')
        return {'facts':store.read_facts(token(authorization),fields)}

    @app.get('/api/facts/{fact_id}')
    def fact(fact_id: UUID, authorization: str | None=Header(default=None)):
        return {'facts':store.read_facts(token(authorization),[],fact_id=fact_id)}

    @app.post('/api/contracts/service')
    def service_contract(data: V1ServiceSpec, authorization: str | None=Header(default=None)):
        with store.connect() as c:store.auth(c,token(authorization),lock=True)
        return {'schema_version':data.schema_version,'validation_scope':'STRUCTURE_ONLY','published':False}

    @app.post('/api/contracts/plan')
    def plan_contract(data: V1ServicePlan, authorization: str | None=Header(default=None)):
        with store.connect() as c:store.auth(c,token(authorization),lock=True)
        return {'schema_version':data.schema_version,'validation_scope':'STRUCTURE_ONLY','executed':False}

    @app.get('/api/messages/{event_id}')
    def message(event_id: UUID, authorization: str | None=Header(default=None)):
        return store.read_delivery(token(authorization),event_id)

    @app.get('/api/files/{file_id}')
    def file(file_id: UUID, authorization: str | None=Header(default=None)):
        data=store.read_file(token(authorization),file_id)
        return Response(data,media_type='text/plain',headers={
            'Content-Disposition':f'attachment; filename="{file_id}.txt"',
            'Content-Security-Policy':"default-src 'none'; sandbox"})

    return app


def configured_app():
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        raise RuntimeError("PARKWEAVE_DSN required; no credential discovery")
    return create_app(Store(dsn, mode=os.environ.get("PARKWEAVE_MODE", "LOCAL"),file_root=os.environ.get("PARKWEAVE_FILE_ROOT")))
