import os
import re
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from .domain import Intake
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
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Denied)
    async def denied(request, exc):
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
            version = c.execute("SELECT version FROM schema_version").fetchone()["version"]
        return {"status": "ok", "schema": version, "model": "MODEL_MOCK", "data": "SYNTHETIC"}

    @app.post("/api/runs", status_code=202)
    def submit(data: Intake, authorization: str | None = Header(default=None),
               idempotency_key: str = Header()):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", idempotency_key):
            raise HTTPException(422, "invalid request key")
        return {"run_id": store.submit(token(authorization), idempotency_key, data)}

    @app.get("/api/runs/{run_id}")
    def read(run_id: UUID, authorization: str | None = Header(default=None)):
        return store.read(token(authorization), run_id)

    @app.post("/api/runs/{run_id}/{intent}")
    def control(run_id: UUID, intent: Literal["pause", "cancel", "resume"],
                authorization: str | None = Header(default=None)):
        store.control(token(authorization), run_id, intent)
        return {"intent": intent, "external_reversal": False}

    return app


def configured_app():
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        raise RuntimeError("PARKWEAVE_DSN required; no credential discovery")
    return create_app(Store(dsn))
