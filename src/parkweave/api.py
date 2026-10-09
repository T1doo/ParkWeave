import os
import re
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from psycopg.errors import LockNotAvailable
from .domain import Intake, FactInput, ClarificationInput, V1ServiceSpec, V1ServicePlan, FieldName
from .store import Store, Denied, Conflict
from .run_access_candidate import RunCommand


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="ParkWeave synthetic foundation", version="0.1.0")
    from . import case_resource_delivery as delivery, resource_bundles as bundles

    @app.post('/api/preparations/{preparation_id}/resource-delivery/preview')
    def delivery_preview(preparation_id: UUID,data: bundles.Bundle,authorization: str | None=Header(default=None)):
        return delivery.preview(store,token(authorization),preparation_id,data)

    @app.post('/api/preparations/{preparation_id}/resource-delivery',status_code=201)
    def delivery_submit(preparation_id: UUID,data: delivery.Deliver,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return delivery.deliver(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/resource-delivery/recovery/{request_key}')
    def delivery_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return delivery.recover(store,token(authorization),preparation_id,resource_key(request_key))

    from . import case_opportunities as opportunities
    @app.get('/api/preparations/{preparation_id}/opportunities')
    def opportunity_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return opportunities.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/opportunities/commands')
    def opportunity_command(preparation_id: UUID,data: opportunities.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return opportunities.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/opportunities/recovery/{request_key}')
    def opportunity_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return opportunities.recover(store,token(authorization),preparation_id,resource_key(request_key))

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
        payload = {"detail": str(exc)}
        if getattr(exc, 'decision_committed', False) is True:
            payload.update(decision_committed=True, projection_pending=True)
        return JSONResponse(payload, status_code=409)

    def token(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "session required")
        return authorization[7:]

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("web.html").read_text(encoding='utf-8')

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

    def access_bridge():
        bridge = getattr(store, '_isolated_run_access', None)
        if bridge is None:
            raise Denied('isolated access decisions disabled')
        return bridge

    from . import material_preparation_drafts as material_drafts

    @app.get('/api/preparations/{preparation_id}/material-draft')
    def material_draft_read(preparation_id: UUID, authorization: str | None = Header(default=None)):
        return material_drafts.read(store, token(authorization), preparation_id)

    @app.post('/api/preparations/{preparation_id}/material-draft', status_code=201)
    def material_draft_save(preparation_id: UUID, data: material_drafts.Save,
                            authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', idempotency_key):
            raise HTTPException(422, 'invalid request key')
        return material_drafts.save(store, token(authorization), preparation_id, idempotency_key, data)

    @app.get('/api/run-access/status')
    def run_access_status(authorization: str | None = Header(default=None)):
        session = token(authorization)
        bridge = getattr(store, '_isolated_run_access', None)
        if bridge is None:
            with store.connect() as c:
                p = store.auth(c, session, lock=True)
                store.check_capability(c, p, 'READ')
            return {'enabled': False, 'role': p['role'], 'can_approve': False,
                    'can_revoke': False, 'deployment_enabled': False}
        return bridge.status(session)

    @app.get('/api/runs/{run_id}/access')
    def run_access_read(run_id: UUID, authorization: str | None = Header(default=None)):
        return access_bridge().read(token(authorization), run_id)

    @app.post('/api/runs/{run_id}/access/commands')
    def run_access_command(run_id: UUID, data: RunCommand,
                           authorization: str | None = Header(default=None),
                           idempotency_key: str = Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', idempotency_key):
            raise HTTPException(422, 'invalid request key')
        return access_bridge().command(token(authorization), run_id, idempotency_key, data)

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

    from . import preparation
    @app.get('/api/preparation-catalog')
    def preparation_catalog(authorization: str | None=Header(default=None)):
        return preparation.catalog(store,token(authorization))

    @app.get('/api/preparation-tasks')
    def preparation_tasks(authorization: str | None=Header(default=None)):
        return preparation.personal_tasks(store,token(authorization))

    @app.get('/api/preparations')
    def preparations(authorization: str | None=Header(default=None)):
        return preparation.list_items(store,token(authorization))

    @app.post('/api/preparations',status_code=201)
    def create_preparation(data: preparation.CreatePreparation,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return preparation.create(store,token(authorization),idempotency_key,data)

    @app.get('/api/preparations/{preparation_id}')
    def preparation_record(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preparation.read(store,token(authorization),preparation_id)

    @app.get('/api/preparations/{preparation_id}/command-recovery')
    def preparation_command_recovery(preparation_id: UUID,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',idempotency_key):raise HTTPException(422,'invalid recovery handle')
        return preparation.recover_evidence_command(store,token(authorization),preparation_id,idempotency_key)

    @app.post('/api/preparations/{preparation_id}/commands')
    def preparation_command(preparation_id: UUID,data: preparation.PreparationCommand,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return preparation.command(store,token(authorization),preparation_id,idempotency_key,data)

    from . import material_reuse
    @app.get('/api/preparations/{preparation_id}/material-reuse')
    def material_reuse_candidates(preparation_id: UUID,source_evidence_id: UUID | None=Query(default=None),authorization: str | None=Header(default=None)):
        return material_reuse.candidates(store,token(authorization),preparation_id,source_evidence_id)

    @app.post('/api/preparations/{preparation_id}/material-reuse',status_code=201)
    def material_reuse_copy(preparation_id: UUID,data: material_reuse.MaterialReuse,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return material_reuse.reuse(store,token(authorization),preparation_id,idempotency_key,data)

    from . import case_fact_clarifications
    @app.get('/api/preparations/{preparation_id}/fact-clarifications')
    def fact_clarifications(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_fact_clarifications.read(store,token(authorization),preparation_id)

    @app.post('/api/preparations/{preparation_id}/fact-clarifications/declare')
    def declare_fact_purpose(preparation_id: UUID,data: case_fact_clarifications.Declare,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return case_fact_clarifications.declare(store,token(authorization),preparation_id,idempotency_key,data)

    @app.post('/api/preparations/{preparation_id}/fact-clarifications/confirm')
    def confirm_fact_purpose(preparation_id: UUID,data: case_fact_clarifications.Confirm,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):raise HTTPException(422,'invalid request key')
        return case_fact_clarifications.confirm(store,token(authorization),preparation_id,idempotency_key,data)

    from . import resource_holds as resources
    def resource_key(key):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',key):raise HTTPException(422,'invalid request key')
        return key

    @app.get('/api/synthetic-resources')
    def resource_catalog(authorization: str | None=Header(default=None)):
        return resources.catalog(store,token(authorization))

    @app.post('/api/synthetic-resources/{resource_id}/preview')
    def resource_preview(resource_id: UUID,data: resources.Preview,authorization: str | None=Header(default=None)):
        return resources.preview(store,token(authorization),resource_id,data)

    @app.post('/api/synthetic-resources/{resource_id}/holds',status_code=201)
    def resource_hold(resource_id: UUID,data: resources.Hold,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return resources.create(store,token(authorization),resource_id,resource_key(idempotency_key),data)

    @app.get('/api/resource-holds')
    def my_resource_holds(authorization: str | None=Header(default=None)):
        return resources.list_holds(store,token(authorization))

    @app.get('/api/resource-holds/{hold_id}')
    def resource_hold_state(hold_id: UUID,authorization: str | None=Header(default=None)):
        return resources.read(store,token(authorization),hold_id)

    @app.post('/api/resource-holds/{hold_id}/confirm')
    def resource_hold_confirm(hold_id: UUID,data: resources.Confirm,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return resources.confirm(store,token(authorization),hold_id,resource_key(idempotency_key),data)

    @app.post('/api/resource-holds/{hold_id}/release')
    def resource_hold_release(hold_id: UUID,data: resources.Release,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return resources.release(store,token(authorization),hold_id,resource_key(idempotency_key))

    from . import resource_combinations as combinations
    from . import resource_bundles as bundles
    @app.post('/api/resource-bundles',status_code=201)
    def bundle_confirm(data: bundles.Bundle,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return bundles.confirm(store,token(authorization),resource_key(idempotency_key),data)

    @app.get('/api/resource-bundles')
    def bundle_list(authorization: str | None=Header(default=None)):
        return bundles.list_items(store,token(authorization))

    @app.get('/api/resource-bundles/recovery/{request_key}')
    def bundle_recovery(request_key: str,authorization: str | None=Header(default=None)):
        return bundles.recover(store,token(authorization),resource_key(request_key))

    @app.get('/api/resource-bundles/{bundle_id}')
    def bundle_read(bundle_id: UUID,authorization: str | None=Header(default=None)):
        return bundles.read(store,token(authorization),bundle_id)

    @app.post('/api/resource-bundles/{bundle_id}/cancel')
    def bundle_cancel(bundle_id: UUID,data: resources.Release,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return bundles.cancel(store,token(authorization),bundle_id,resource_key(idempotency_key))

    @app.post('/api/resource-combinations',status_code=201)
    def resource_combination_confirm(data: combinations.Combination,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return combinations.confirm(store,token(authorization),resource_key(idempotency_key),data)

    @app.get('/api/resource-combinations')
    def resource_combination_list(authorization: str | None=Header(default=None)):
        return combinations.list_combinations(store,token(authorization))

    @app.get('/api/resource-combinations/{combination_id}')
    def resource_combination_read(combination_id: UUID,authorization: str | None=Header(default=None)):
        return combinations.read(store,token(authorization),combination_id)

    @app.post('/api/resource-combinations/{combination_id}/cancel')
    def resource_combination_cancel(combination_id: UUID,data: resources.Release,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return combinations.cancel(store,token(authorization),combination_id,resource_key(idempotency_key))

    from . import dispatch_notices as notices
    from . import controlled_plans as cp
    from . import request_intents as intents
    from . import material_objections
    @app.get('/api/preparations/{preparation_id}/material-objections')
    def material_objections_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return material_objections.read(store,token(authorization),preparation_id)
    @app.get('/api/preparations/{preparation_id}/material-objections/recovery/{request_key}')
    def material_objections_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return material_objections.recover(store,token(authorization),preparation_id,resource_key(request_key))
    @app.post('/api/preparations/{preparation_id}/material-objections')
    def material_objections_command(preparation_id: UUID,data: material_objections.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return material_objections.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    from . import material_corrections
    @app.get('/api/preparations/{preparation_id}/material-corrections')
    def material_corrections_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return material_corrections.read(store,token(authorization),preparation_id)

    from . import service_case_steps as service_steps
    @app.get('/api/preparations/{preparation_id}/service-case-plan')
    def service_case_plan_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return service_steps.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/service-case-plan',status_code=201)
    def service_case_plan_adopt(preparation_id: UUID,data: service_steps.Adopt,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return service_steps.adopt(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.post('/api/preparations/{preparation_id}/service-case-plan/commands')
    def service_case_plan_command(preparation_id: UUID,data: service_steps.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return service_steps.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    from . import bounded_planning as planning
    @app.get('/api/preparations/{preparation_id}/planning-preview')
    def planning_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return planning.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/planning-preview')
    def planning_capture(preparation_id: UUID,data: planning.Capture,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return planning.capture(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    from . import case_path
    @app.get('/api/preparations/{preparation_id}/case-path')
    def case_record_path(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_path.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/request-intent')
    def save_request_intent(preparation_id: UUID,data: intents.Save,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return intents.save(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/controlled-plans/template')
    def fixed_template(authorization: str | None=Header(default=None)):
        return cp.template(store,token(authorization))
    @app.get('/api/preparations/{preparation_id}/controlled-plan')
    def fixed_plan(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return cp.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/controlled-plan',status_code=201)
    def fixed_plan_create(preparation_id: UUID,data: cp.Create,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cp.create(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.post('/api/preparations/{preparation_id}/controlled-plan/preview')
    def fixed_plan_preview(preparation_id: UUID,data: cp.Preview,authorization: str | None=Header(default=None)):
        return cp.preview(store,token(authorization),preparation_id,data)
    @app.post('/api/preparations/{preparation_id}/controlled-plan/commands')
    def fixed_plan_command(preparation_id: UUID,data: cp.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cp.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/dispatch-notices')
    def notice_list(authorization: str | None=Header(default=None)):
        return notices.list_items(store,token(authorization))

    @app.get('/api/dispatch-notices/{event_id}')
    def notice_read(event_id: UUID,authorization: str | None=Header(default=None)):
        return notices.read(store,token(authorization),event_id)

    @app.post('/api/dispatch-notices/{event_id}/commands')
    def notice_command(event_id: UUID,data: notices.Command,authorization: str | None=Header(default=None)):
        return notices.command(store,token(authorization),event_id,data)

    from . import case_lifecycle
    from . import readiness
    @app.get('/api/preparations/{preparation_id}/readiness')
    def material_readiness(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return readiness.read(store,token(authorization),preparation_id)

    @app.post('/api/preparations/{preparation_id}/readiness')
    def material_assess(preparation_id: UUID,data: readiness.Assess,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return readiness.assess(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/local-case')
    def local_case_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_lifecycle.read(store,token(authorization),preparation_id)

    @app.get('/api/preparations/{preparation_id}/local-case/recovery/{request_key}')
    def local_case_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return case_lifecycle.recover(store,token(authorization),preparation_id,resource_key(request_key))

    @app.post('/api/preparations/{preparation_id}/local-case/commands')
    def local_case_command(preparation_id: UUID,data: case_lifecycle.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return case_lifecycle.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    from . import service_dispatches as dispatches
    @app.get('/api/service-dispatches/catalog')
    def dispatch_catalog(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return dispatches.catalog(store,token(authorization),preparation_id)

    @app.get('/api/service-dispatches')
    def dispatch_list(authorization: str | None=Header(default=None)):
        return dispatches.list_items(store,token(authorization))

    @app.get('/api/preparations/{preparation_id}/dispatch')
    def dispatch_preparation(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return dispatches.read_preparation(store,token(authorization),preparation_id)

    @app.post('/api/preparations/{preparation_id}/dispatch',status_code=201)
    def dispatch_offer(preparation_id: UUID,data: dispatches.Offer,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return dispatches.offer(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/service-dispatches/{dispatch_id}')
    def dispatch_read(dispatch_id: UUID,authorization: str | None=Header(default=None)):
        return dispatches.read(store,token(authorization),dispatch_id)

    @app.post('/api/service-dispatches/{dispatch_id}/commands')
    def dispatch_command(dispatch_id: UUID,data: dispatches.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return dispatches.command(store,token(authorization),dispatch_id,resource_key(idempotency_key),data)

    from . import executor_receipts as executor_receipts
    @app.get('/api/executor-receipts/catalog')
    def executor_receipt_catalog(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return executor_receipts.catalog(store,token(authorization),preparation_id)

    @app.get('/api/executor-receipts')
    def executor_receipt_list(authorization: str | None=Header(default=None)):
        return executor_receipts.list_steps(store,token(authorization))

    @app.post('/api/executor-receipts',status_code=201)
    def executor_receipt_create(data: executor_receipts.Create,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return executor_receipts.create(store,token(authorization),resource_key(idempotency_key),data)

    @app.get('/api/executor-receipts/{step_id}')
    def executor_receipt_read(step_id: UUID,authorization: str | None=Header(default=None)):
        return executor_receipts.read(store,token(authorization),step_id)

    @app.post('/api/executor-receipts/{step_id}/commands')
    def executor_receipt_command(step_id: UUID,data: executor_receipts.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        try:return executor_receipts.command(store,token(authorization),step_id,resource_key(idempotency_key),data)
        except LockNotAvailable as e:raise Conflict('receipt authorization or record busy; retry same key') from e

    from .isolated_local_execution import ExecuteLocal
    @app.post('/api/executor-receipts/{step_id}/execute-local')
    def executor_receipt_execute_local(step_id: UUID,data: ExecuteLocal,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return executor_receipts.command(store,token(authorization),step_id,resource_key(idempotency_key),data)

    from . import case_resources as case_resources
    from . import resource_plan_binding
    @app.get('/api/preparations/{preparation_id}/resource-plan-binding')
    def case_resource_plan_binding(preparation_id: UUID,candidate_combination_id: UUID | None=None,authorization: str | None=Header(default=None)):
        return resource_plan_binding.read(store,token(authorization),preparation_id,candidate_combination_id)

    @app.post('/api/preparations/{preparation_id}/resource-plan-binding/confirm',status_code=201)
    def case_resource_plan_confirm(preparation_id: UUID,data: resource_plan_binding.Confirm,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return case_resources.bind(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/resource-link')
    def case_resource_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_resources.read(store,token(authorization),preparation_id)

    @app.get('/api/preparations/{preparation_id}/resource-link-candidates')
    def case_resource_candidates(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_resources.candidates(store,token(authorization),preparation_id)

    @app.post('/api/preparations/{preparation_id}/resource-link',status_code=201)
    def case_resource_bind(preparation_id: UUID,data: case_resources.Bind,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return case_resources.bind(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    return app


def configured_app():
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        raise RuntimeError("PARKWEAVE_DSN required; no credential discovery")
    return create_app(Store(dsn, mode=os.environ.get("PARKWEAVE_MODE", "LOCAL"),file_root=os.environ.get("PARKWEAVE_FILE_ROOT")))
