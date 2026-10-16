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
from .native_run_access import RunCommand as NativeRunCommand


def create_app(store: Store, *, summary_reader=None, proposal_planner=None, capability_catalog=None, selection_planner=None, instance_consumer=None, synthetic_rule_readiness=None, service_release_preflight=None) -> FastAPI:
    if synthetic_rule_readiness is not None:
        from .synthetic_rule_readiness import SyntheticRuleReadiness
        if type(synthetic_rule_readiness) is not SyntheticRuleReadiness or synthetic_rule_readiness.store is not store:
            raise Denied('explicit matching owned synthetic rule simulation required')
        with store.connect() as c: synthetic_rule_readiness._fixture(c)
    if capability_catalog is not None:
        from .service_capability_catalog import IsolatedServiceCapabilityCatalog
        if type(capability_catalog) is not IsolatedServiceCapabilityCatalog or capability_catalog.consumer.store is not store:
            raise Denied('explicit owned service capability catalog required')
        capability_catalog.consumer.validate_fixture()
        store._isolated_service_capability_catalog=capability_catalog
    if selection_planner is not None:
        from .service_selection_planner import OfflineSelectionPlanner
        if capability_catalog is None or type(selection_planner) is not OfflineSelectionPlanner:
            raise Denied('explicit owned catalog and offline selection planner required')
        selection_planner.require()
    if instance_consumer is not None:
        from .service_instance_consumer import ParkInstanceConsumer
        if type(instance_consumer) is not ParkInstanceConsumer or instance_consumer.catalog is not capability_catalog:
            raise Denied('explicit matching owned park instance consumer required')
    if service_release_preflight is not None:
        from .service_release_preflight import ServiceReleasePreflight
        if type(service_release_preflight) is not ServiceReleasePreflight or service_release_preflight.catalog is not capability_catalog or service_release_preflight.store is not store or (instance_consumer is not None and service_release_preflight.repository.path==instance_consumer.repository.path):
            raise Denied('explicit matching owned service release preflight required')
    if proposal_planner is not None:
        from .service_plan_planner import OfflineProposalPlanner
        if type(proposal_planner) is not OfflineProposalPlanner:raise Denied('explicit offline-only proposal planner required')
        proposal_planner.require()
    # A private writer context may only run in its separate transaction process.
    bridge = getattr(store, '_native_run_access', None)
    if bridge is not None and getattr(bridge, 'writer', None) is not None:
        from .native_run_access_writer import WriterClient
        if type(bridge.writer) is not WriterClient:
            raise Denied('API cannot hold private writer credentials or signing context')
    store._native_api_boundary = True
    app = FastAPI(title="ParkWeave synthetic foundation", version="0.1.0")
    from . import case_resource_delivery as delivery, resource_bundles as bundles

    from . import service_plan_approval as plan_approval

    def approval_candidate():
        candidate = getattr(store, '_isolated_plan_approval', None)
        if candidate is None: raise Denied('isolated plan Approval disabled')
        return candidate

    @app.get('/api/plan-approval/status')
    def approval_status(authorization: str | None=Header(default=None)):
        with store.connect() as c:
            p=store.auth(c,token(authorization),lock=True)
            store.check_capability(c,p,'READ')
        return dict(enabled=getattr(store,'_isolated_plan_approval',None) is not None,
            production_execution_enabled=False,formal_release=False,role=p['role'])

    @app.get('/api/preparations/{preparation_id}/plan-approval')
    def approval_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return approval_candidate().read(store,token(authorization),preparation_id)

    @app.post('/api/preparations/{preparation_id}/plan-approval/proposals',status_code=201)
    def approval_propose(preparation_id: UUID,data: plan_approval.Proposal,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return approval_candidate().propose(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.post('/api/preparations/{preparation_id}/plan-approval/commands')
    def approval_command(preparation_id: UUID,data: plan_approval.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return approval_candidate().command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/plan-approval/recovery/{request_key}')
    def approval_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return approval_candidate().read(store,token(authorization),preparation_id,resource_key(request_key))

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
    from . import plan_source_conflicts as note_conflicts
    from . import material_package_continuation as material_package
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler

    @app.exception_handler(RequestValidationError)
    async def material_package_request_validation(request: Request,error: RequestValidationError):
        route=request.scope.get('route')
        if getattr(route,'path',None)=='/api/preparations/{preparation_id}/plan-material-package/commands':
            # Bad UTF-8 input must not be echoed by the default error encoder.
            return JSONResponse(status_code=422,content={'detail':'invalid bounded material package request'})
        return await request_validation_exception_handler(request,error)

    @app.get('/api/preparations/{preparation_id}/plan-source-conflicts')
    def owner_note_read(preparation_id: UUID,card_id: UUID|None=None,authorization: str|None=Header(default=None)):
        return note_conflicts.read(store,token(authorization),preparation_id,card_id=card_id)

    @app.post('/api/preparations/{preparation_id}/plan-source-conflicts/commands')
    def owner_note_command(preparation_id: UUID,data: note_conflicts.Command,authorization: str|None=Header(default=None),idempotency_key: str=Header()):
        try:return note_conflicts.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
        except note_conflicts.DefinitiveConflict as error:return JSONResponse(status_code=409,content=error.proof)

    @app.get('/api/preparations/{preparation_id}/plan-source-conflicts/recovery/{request_key}')
    def owner_note_recovery(preparation_id: UUID,request_key: str,authorization: str|None=Header(default=None)):
        return note_conflicts.recover(store,token(authorization),preparation_id,resource_key(request_key))
    @app.get('/api/preparations/{preparation_id}/plan-material-package')
    def material_package_read(preparation_id: UUID,card_id: UUID|None=None,authorization: str|None=Header(default=None)):
        return material_package.read(store,token(authorization),preparation_id,card_id=card_id)

    @app.post('/api/preparations/{preparation_id}/plan-material-package/commands')
    def material_package_command(preparation_id: UUID,data: material_package.Command,authorization: str|None=Header(default=None),idempotency_key: str=Header()):
        try:return material_package.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
        except material_package.DefinitiveConflict as error:return JSONResponse(status_code=409,content=error.proof)

    @app.get('/api/preparations/{preparation_id}/plan-material-package/recovery/{request_key}')
    def material_package_recovery(preparation_id: UUID,request_key: str,authorization: str|None=Header(default=None)):
        return material_package.recover(store,token(authorization),preparation_id,resource_key(request_key))

    @app.get('/api/cases/worklist')
    def owner_case_worklist(limit: int=Query(default=20,ge=1,le=50),after: UUID|None=Query(default=None),
                            authorization: str|None=Header(default=None)):
        from . import case_worklist
        return case_worklist.read(store,token(authorization),limit=limit,after=after)
    @app.get('/api/preparations/{preparation_id}/opportunities')
    def opportunity_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return opportunities.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/opportunities/commands')
    def opportunity_command(preparation_id: UUID,data: opportunities.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return opportunities.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/opportunities/recovery/{request_key}')
    def opportunity_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return opportunities.recover(store,token(authorization),preparation_id,resource_key(request_key))
    # Preserve every existing recovery key before the dynamic card route.
    @app.get('/api/preparations/{preparation_id}/opportunities/{card_id}/plan-revision')
    def opportunity_plan_revision(preparation_id: UUID,card_id: UUID,authorization: str | None=Header(default=None)):
        from . import source_change_adoption
        return source_change_adoption.read(store,token(authorization),preparation_id,card_id)

    @app.get('/api/preparations/{preparation_id}/source-impact')
    def case_source_impact(preparation_id: UUID,authorization: str | None=Header(default=None)):
        from . import typed_source_impact
        return typed_source_impact.read(store,token(authorization),preparation_id)

    @app.get('/api/preparations/{preparation_id}/shared-source-cases')
    def shared_source_cases(preparation_id: UUID,
            source_kind: Literal['OWNER_RESOURCE_QUERY_SET','SERVICE_CATALOG_REFERENCE']='OWNER_RESOURCE_QUERY_SET',
            limit: int=Query(default=10,ge=1,le=20),
            cursor: str|None=Query(default=None,min_length=1,max_length=4096),
            authorization: str|None=Header(default=None)):
        from . import shared_source_cases as shared
        return shared.read(store,token(authorization),preparation_id,source_kind=source_kind,limit=limit,cursor=cursor)

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

    @app.get('/api/cases/{case_id}/preparations/{preparation_id}/history-summary/{stage}')
    def history_summary(case_id: UUID, preparation_id: UUID, stage: Literal['P4', 'P5'], request: Request,
                        request_key: str | None = Query(default=None),
                        authorization: str | None = Header(default=None)):
        from .history_summary import MemoryHistorySummaryReader
        session = token(authorization)
        if type(summary_reader) is not MemoryHistorySummaryReader or summary_reader.stage != stage:
            raise Denied('explicit matching history summary reader required')
        if len(request.query_params.getlist('request_key')) > 1:
            raise Denied('single original history key required')
        return summary_reader.read_case(store, session, case_id, preparation_id, request_key, stage=stage)

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

    @app.get('/api/runs')
    def local_records(authorization: str | None = Header(default=None),
                      limit: int = Query(default=20, ge=1, le=50),
                      after: UUID | None = Query(default=None)):
        return store.list_local_records(token(authorization), limit=limit, after=after)

    @app.get("/api/runs/{run_id}")
    def read(run_id: UUID, authorization: str | None = Header(default=None)):
        return store.read(token(authorization), run_id)

    def access_bridge():
        bridge = getattr(store, '_isolated_run_access', None)
        if bridge is not None and getattr(store, '_native_run_access', None) is not None:
            raise Denied('ambiguous ordinary and isolated access providers')
        if bridge is None:
            from .native_run_access import NativeRunAccess
            bridge = getattr(store, '_native_run_access', None)
            if bridge is None:
                bridge = NativeRunAccess(store)
            elif type(bridge) is not NativeRunAccess or bridge.store is not store:
                raise Denied('trusted native access provider required')
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
        return access_bridge().status(session)

    @app.get('/api/runs/{run_id}/access')
    def run_access_read(run_id: UUID, authorization: str | None = Header(default=None)):
        return access_bridge().read(token(authorization), run_id)

    @app.get('/api/runs/{run_id}/access/commands/{request_key}')
    def run_access_recover(run_id: UUID, request_key: str,
                           authorization: str | None = Header(default=None)):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request_key):
            raise HTTPException(422, 'invalid original request key')
        if getattr(store, '_isolated_run_access', None) is not None:
            raise Denied('native original-key recovery unavailable for isolated decisions')
        return access_bridge().recover(token(authorization), run_id, request_key)

    @app.post('/api/runs/{run_id}/access/commands')
    def run_access_command(run_id: UUID, data: RunCommand | NativeRunCommand,
                           authorization: str | None = Header(default=None),
                           idempotency_key: str = Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', idempotency_key):
            raise HTTPException(422, 'invalid request key')
        if getattr(store, '_isolated_run_access', None) is None:
            from .native_run_access import RunCommand as NativeCommand
            from pydantic import ValidationError
            try:
                data=NativeCommand.model_validate(data.model_dump())
            except ValidationError:
                raise HTTPException(422, 'invalid native UTC command')
        elif type(data) is NativeRunCommand:
            raise HTTPException(422, 'ordinary writer fields are unavailable for isolated commands')
        return access_bridge().command(token(authorization), run_id, idempotency_key, data)

    from .native_run_access_activation import Activate

    @app.post('/api/runs/{run_id}/access/activate')
    def run_access_activate(run_id: UUID, data: Activate,
                            authorization: str | None = Header(default=None),
                            idempotency_key: str = Header()):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',idempotency_key):
            raise HTTPException(422,'invalid original request key')
        if getattr(store,'_isolated_run_access',None) is not None:
            raise Denied('ordinary activation unavailable for isolated provider')
        return access_bridge().activate(token(authorization),run_id,idempotency_key,data)

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
    def preparation_tasks(authorization: str | None=Header(default=None),limit:int=Query(default=100,ge=1,le=100),before:UUID|None=Query(default=None)):
        return preparation.personal_tasks(store,token(authorization),limit=limit,before=before)

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

    @app.get('/api/preparations/{preparation_id}/handling-deadline')
    def handling_deadline_read(preparation_id: UUID,request: Request,authorization: str | None=Header(default=None)):
        from .handling_deadline import read
        if request.query_params:
            raise HTTPException(422, 'deadline observation uses server time only')
        return read(store,token(authorization),preparation_id)

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

    from . import case_fact_bundle as fact_bundle
    @app.get('/api/preparations/{preparation_id}/fact-bundle')
    def fact_bundle_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return fact_bundle.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/fact-bundle/commands')
    def fact_bundle_command(preparation_id: UUID,data: fact_bundle.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return fact_bundle.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/fact-bundle/recovery/{request_key}')
    def fact_bundle_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return fact_bundle.recover(store,token(authorization),preparation_id,resource_key(request_key))

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

    @app.post('/api/synthetic-resources/{resource_id}/alternative-times')
    def resource_alternative_times(resource_id: UUID,data: resources.AlternativeTimes,authorization: str | None=Header(default=None)):
        return resources.alternative_times(store,token(authorization),resource_id,data)

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
    @app.get('/api/preparations/{preparation_id}/service-case-plan/command-recovery')
    def service_case_plan_recover(preparation_id: UUID,authorization: str | None=Header(default=None),idempotency_key: str | None=Header(default=None)):
        return service_steps.recover(store,token(authorization),preparation_id,resource_key(idempotency_key) if idempotency_key is not None else None)
    @app.post('/api/preparations/{preparation_id}/service-case-plan',status_code=201)
    def service_case_plan_adopt(preparation_id: UUID,data: service_steps.Adopt,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return service_steps.adopt(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.post('/api/preparations/{preparation_id}/service-case-plan/commands')
    def service_case_plan_command(preparation_id: UUID,data: service_steps.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return service_steps.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    from . import service_plan_candidates as plan_candidates
    @app.get('/api/preparations/{preparation_id}/service-plan-candidates')
    def service_plan_candidates_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return plan_candidates.read(store,token(authorization),preparation_id)
    @app.get('/api/preparations/{preparation_id}/service-plan-candidates/recovery')
    def service_plan_candidates_recover(preparation_id: UUID,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return plan_candidates.read(store,token(authorization),preparation_id,key=resource_key(idempotency_key))
    @app.get('/api/preparations/{preparation_id}/service-plan-candidates/{candidate_id}/preview')
    def service_plan_candidate_preview(preparation_id: UUID,candidate_id: UUID,authorization: str | None=Header(default=None)):
        return plan_candidates.read(store,token(authorization),preparation_id,candidate_id)
    @app.post('/api/preparations/{preparation_id}/service-plan-candidates',status_code=201)
    def service_plan_candidate_generate(preparation_id: UUID,data: plan_candidates.bp.Capture,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return plan_candidates.generate(store,token(authorization),preparation_id,resource_key(idempotency_key),data,planner=proposal_planner)

    from . import service_selection_candidates as selections
    from .service_instance_consumer import ColdInput

    def selected_catalog():
        if capability_catalog is None:raise Denied('isolated service capability selection disabled')
        return capability_catalog

    @app.get('/api/preparations/{preparation_id}/service-capabilities')
    def service_capability_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        catalog=selected_catalog()
        with catalog.read_connection() as c:
            p,parent=selections.bp._context(store,c,token(authorization),preparation_id)
            current=selections.current(store,c,p,parent,catalog)
            return dict(**current,scope='SYNTHETIC_SERVICE_CAPABILITY_SELECTION_PREVIEW',actor_ref=selections.cp._hash(dict(actor_id=p['id'])),read_only=True,automatically_replayed=False)

    @app.post('/api/preparations/{preparation_id}/service-selections',status_code=201)
    def service_selection_generate(preparation_id: UUID,data: selections.Capture,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return selections.generate(store,token(authorization),preparation_id,resource_key(idempotency_key),data,catalog=selected_catalog(),planner=selection_planner)

    @app.get('/api/preparations/{preparation_id}/service-selections')
    def service_selection_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return selections.read(store,token(authorization),preparation_id,catalog=selected_catalog())

    @app.get('/api/preparations/{preparation_id}/service-selections/recovery')
    def service_selection_recovery(preparation_id: UUID,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return selections.read(store,token(authorization),preparation_id,key=resource_key(idempotency_key),catalog=selected_catalog())

    @app.get('/api/preparations/{preparation_id}/service-selections/{candidate_id}/preview')
    def service_selection_preview(preparation_id: UUID,candidate_id: UUID,authorization: str | None=Header(default=None)):
        return selections.read(store,token(authorization),preparation_id,candidate_id,catalog=selected_catalog())

    from .service_release_preflight import Record as ServiceReleasePreflightRecord

    def release_preflight():
        if service_release_preflight is None:raise Denied('isolated service release preflight disabled')
        return service_release_preflight

    @app.get('/api/preparations/{preparation_id}/service-release-preflight')
    def service_release_preflight_directory(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return release_preflight().directory(token(authorization),preparation_id)

    @app.get('/api/preparations/{preparation_id}/service-release-preflight/preview')
    def service_release_preflight_preview(preparation_id: UUID,original_release_id: str=Query(min_length=1,max_length=120),original_instance_id: str=Query(min_length=1,max_length=120),target_instance_id: str=Query(min_length=1,max_length=120),authorization: str | None=Header(default=None)):
        return release_preflight().preview(token(authorization),preparation_id,original_release_id=original_release_id,original_instance_id=original_instance_id,target_instance_id=target_instance_id)

    @app.post('/api/preparations/{preparation_id}/service-release-preflight',status_code=201)
    def service_release_preflight_record(preparation_id: UUID,data: ServiceReleasePreflightRecord,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return release_preflight().save(token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/service-release-preflight/recovery/{request_key}')
    def service_release_preflight_recovery(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return release_preflight().recover(token(authorization),preparation_id,resource_key(request_key))

    def cold_inputs():
        if instance_consumer is None:raise Denied('isolated park instance cold input disabled')
        return instance_consumer

    @app.get('/api/service-instance-configurations')
    def service_instance_configurations(authorization: str | None=Header(default=None)):
        return cold_inputs().configurations(token(authorization))

    @app.post('/api/service-instance-cold-inputs',status_code=201)
    def service_instance_prepare(data: ColdInput,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cold_inputs().prepare(token(authorization),resource_key(idempotency_key),data)

    @app.get('/api/service-instance-cold-inputs/recovery')
    def service_instance_recovery(authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cold_inputs().read(token(authorization),resource_key(idempotency_key))

    @app.post('/api/service-instance-cold-inputs/prepare-stage')
    def service_instance_stage(stage: Literal['CREATE_PREPARATION','SAVE_REQUEST','ADD_need_summary','ADD_material_outline'],authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cold_inputs().prepare_stage(token(authorization),resource_key(idempotency_key),stage)

    from . import bounded_planning as planning
    from . import case_goal_results
    @app.get('/api/preparations/{preparation_id}/goal-results')
    def goal_results_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_goal_results.read(store,token(authorization),preparation_id)

    from . import manual_goal_requests
    @app.get('/api/preparations/{preparation_id}/manual-goal-requests')
    def manual_goals_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return manual_goal_requests.read(store,token(authorization),preparation_id)
    @app.get('/api/preparations/{preparation_id}/manual-goal-requests/recovery/{request_key}')
    def manual_goals_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return manual_goal_requests.read(store,token(authorization),preparation_id,resource_key(request_key))
    @app.post('/api/preparations/{preparation_id}/manual-goal-requests')
    def manual_goals_command(preparation_id: UUID,data: manual_goal_requests.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return manual_goal_requests.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/planning-preview')
    def planning_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return planning.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/planning-preview')
    def planning_capture(preparation_id: UUID,data: planning.Capture,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return planning.capture(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    from . import isolated_execution_preview as execution_preview
    import sqlite3
    import psycopg

    def preview_executor():
        candidate=getattr(store,'_isolated_execution_preview',None)
        if type(candidate) is not execution_preview.IsolatedExecutionPreview:
            raise Denied('isolated execution preview disabled')
        return candidate

    def preview_call(action):
        try:return action()
        except (psycopg.Error,sqlite3.Error,OSError,execution_preview.Unavailable):
            raise HTTPException(503,'isolated preview outcome unavailable; read original key before an explicit new attempt') from None

    @app.get('/api/preparations/{preparation_id}/execution-preview')
    def execution_preview_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:preview_executor().read(store,token(authorization),preparation_id))

    @app.post('/api/preparations/{preparation_id}/execution-preview',status_code=201)
    def execution_preview_execute(preparation_id: UUID,data: execution_preview.Execute,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return preview_call(lambda:preview_executor().execute(store,token(authorization),preparation_id,resource_key(idempotency_key),data))

    @app.get('/api/preparations/{preparation_id}/execution-preview/recovery/{request_key}')
    def execution_preview_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:preview_executor().read(store,token(authorization),preparation_id,resource_key(request_key)))
    from . import resource_execution_preview as resource_preview
    def resource_preview_executor():
        candidate=getattr(store,'_isolated_resource_execution_preview',None)
        if type(candidate) is not resource_preview.ResourceExecutionPreview:
            raise Denied('isolated resource execution preview disabled')
        return candidate

    @app.get('/api/preparations/{preparation_id}/resource-execution-preview')
    def resource_execution_preview_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:resource_preview_executor().read(store,token(authorization),preparation_id))

    @app.post('/api/preparations/{preparation_id}/resource-execution-preview',status_code=201)
    def resource_execution_preview_execute(preparation_id: UUID,data: execution_preview.Execute,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return preview_call(lambda:resource_preview_executor().execute(store,token(authorization),preparation_id,resource_key(idempotency_key),data))

    @app.get('/api/preparations/{preparation_id}/resource-execution-preview/recovery/{request_key}')
    def resource_execution_preview_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:resource_preview_executor().read(store,token(authorization),preparation_id,resource_key(request_key)))
    from . import dispatch_execution_preview as dispatch_preview
    def dispatch_preview_executor():
        candidate=getattr(store,'_isolated_dispatch_execution_preview',None)
        if type(candidate) is not dispatch_preview.DispatchExecutionPreview:
            raise Denied('isolated dispatch execution preview disabled')
        return candidate

    @app.get('/api/preparations/{preparation_id}/dispatch-execution-preview')
    def dispatch_execution_preview_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:dispatch_preview_executor().read(store,token(authorization),preparation_id))

    @app.post('/api/preparations/{preparation_id}/dispatch-execution-preview',status_code=201)
    def dispatch_execution_preview_execute(preparation_id: UUID,data: dispatch_preview.Execute,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return preview_call(lambda:dispatch_preview_executor().execute(store,token(authorization),preparation_id,resource_key(idempotency_key),data))

    @app.get('/api/preparations/{preparation_id}/dispatch-execution-preview/recovery/{request_key}')
    def dispatch_execution_preview_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:dispatch_preview_executor().read(store,token(authorization),preparation_id,resource_key(request_key)))
    from . import receipt_execution_preview as receipt_preview
    def receipt_preview_executor():
        candidate=getattr(store,'_isolated_receipt_execution_preview',None)
        if type(candidate) is not receipt_preview.ReceiptExecutionPreview:
            raise Denied('isolated receipt execution preview disabled')
        return candidate

    @app.get('/api/preparations/{preparation_id}/receipt-execution-preview')
    def receipt_execution_preview_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:receipt_preview_executor().read(store,token(authorization),preparation_id))

    @app.post('/api/preparations/{preparation_id}/receipt-execution-preview',status_code=201)
    def receipt_execution_preview_execute(preparation_id: UUID,data: receipt_preview.Execute,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return preview_call(lambda:receipt_preview_executor().execute(store,token(authorization),preparation_id,resource_key(idempotency_key),data))

    @app.get('/api/preparations/{preparation_id}/receipt-execution-preview/recovery/{request_key}')
    def receipt_execution_preview_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:receipt_preview_executor().read(store,token(authorization),preparation_id,resource_key(request_key)))
    from . import lifecycle_execution_preview as lifecycle_preview
    def lifecycle_preview_executor():
        candidate=getattr(store,'_isolated_lifecycle_execution_preview',None)
        if type(candidate) is not lifecycle_preview.LifecycleExecutionPreview:
            raise Denied('isolated lifecycle execution preview disabled')
        return candidate

    @app.get('/api/preparations/{preparation_id}/lifecycle-execution-preview')
    def lifecycle_execution_preview_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:lifecycle_preview_executor().read(store,token(authorization),preparation_id))

    @app.post('/api/preparations/{preparation_id}/lifecycle-execution-preview',status_code=201)
    def lifecycle_execution_preview_execute(preparation_id: UUID,data: lifecycle_preview.Execute,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return preview_call(lambda:lifecycle_preview_executor().execute(store,token(authorization),preparation_id,resource_key(idempotency_key),data))

    @app.get('/api/preparations/{preparation_id}/lifecycle-execution-preview/recovery/{request_key}')
    def lifecycle_execution_preview_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:lifecycle_preview_executor().read(store,token(authorization),preparation_id,resource_key(request_key)))
    from . import case_cancellation as case_cancel
    @app.get('/api/preparations/{preparation_id}/case-cancellation')
    def case_cancellation_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return case_cancel.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/case-cancellation')
    def case_cancellation_submit(preparation_id: UUID,data: case_cancel.Cancel,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return case_cancel.cancel(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/case-cancellation/recovery/{request_key}')
    def case_cancellation_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return case_cancel.recover(store,token(authorization),preparation_id,resource_key(request_key))
    from . import case_cancellation_before_receipt as receipt_cancel
    @app.get('/api/preparations/{preparation_id}/case-cancellation-before-receipt')
    def case_cancellation_before_receipt_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return receipt_cancel.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/case-cancellation-before-receipt')
    def case_cancellation_before_receipt_submit(preparation_id: UUID,data: receipt_cancel.Cancel,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return receipt_cancel.cancel(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/case-cancellation-before-receipt/recovery/{request_key}')
    def case_cancellation_before_receipt_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return receipt_cancel.recover(store,token(authorization),preparation_id,resource_key(request_key))
    from . import case_cancellation_reconciliation as cancel_reconciliation
    @app.get('/api/preparations/{preparation_id}/case-cancellation-reconciliation')
    def case_cancellation_reconciliation_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return cancel_reconciliation.read(store,token(authorization),preparation_id)
    @app.post('/api/preparations/{preparation_id}/case-cancellation-reconciliation')
    def case_cancellation_reconciliation_command(preparation_id: UUID,data: cancel_reconciliation.Command,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return cancel_reconciliation.command(store,token(authorization),preparation_id,resource_key(idempotency_key),data)
    @app.get('/api/preparations/{preparation_id}/case-cancellation-reconciliation/recovery/{request_key}')
    def case_cancellation_reconciliation_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return cancel_reconciliation.recover(store,token(authorization),preparation_id,resource_key(request_key))
    from . import receipt_history_recovery as receipt_history
    def receipt_history_client():
        client=getattr(store,'_isolated_receipt_history',None)
        if type(client) is not receipt_history.ReceiptHistoryClient:
            raise Denied('isolated read-only receipt history disabled')
        return client

    @app.get('/api/preparations/{preparation_id}/receipt-execution-history')
    def receipt_execution_history_read(preparation_id: UUID,authorization: str | None=Header(default=None)):
        return preview_call(lambda:receipt_history_client().read(store,token(authorization),preparation_id))

    @app.get('/api/preparations/{preparation_id}/receipt-execution-history/recovery/{request_key}')
    def receipt_execution_history_recover(preparation_id: UUID,request_key: str,authorization: str | None=Header(default=None)):
        return preview_call(lambda:receipt_history_client().read(store,token(authorization),preparation_id,resource_key(request_key)))
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

    notice_navigation=notices.Navigation()
    app.state.notice_navigation=notice_navigation

    @app.get('/api/dispatch-notices')
    def notice_list(request: Request,response: Response,authorization: str | None=Header(default=None)):
        response.headers['Cache-Control']='no-store'
        cursors=request.query_params.getlist('cursor')
        if len(cursors)>1 or any(key!='cursor' for key in request.query_params):
            raise Denied('notice navigation unavailable; refresh required')
        return notices.list_items(store,token(authorization),cursor=cursors[0] if cursors else None,
                                  navigation=notice_navigation)

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

    @app.post('/api/service-dispatches/{dispatch_id}/reassign',status_code=201)
    def dispatch_reassign(dispatch_id: UUID,data: dispatches.Reassign,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return dispatches.reassign(store,token(authorization),dispatch_id,resource_key(idempotency_key),data)

    @app.get('/api/service-dispatches/{dispatch_id}/reassignment-recovery/{request_key}')
    def dispatch_reassignment_recovery(dispatch_id: UUID,request_key: str,response: Response,authorization: str | None=Header(default=None)):
        response.headers['Cache-Control']='no-store'
        return dispatches.recover_reassignment(store,token(authorization),dispatch_id,resource_key(request_key))

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

    from . import synthetic_rule_readiness as srr
    def simulation_adapter():
        if synthetic_rule_readiness is None:
            raise Denied('isolated synthetic rule simulation disabled')
        return synthetic_rule_readiness

    def simulation_context(binding_id,as_of):
        from pydantic import ValidationError
        try:return srr.Context(binding_id=binding_id,as_of=as_of)
        except ValidationError:raise HTTPException(422,'invalid synthetic rule context')

    @app.get('/api/preparations/{preparation_id}/synthetic-rule-readiness')
    def synthetic_rule_read(preparation_id: UUID,binding_id: str,as_of: str,authorization: str | None=Header(default=None)):
        return simulation_adapter().read(token(authorization),preparation_id,simulation_context(binding_id,as_of))

    @app.post('/api/preparations/{preparation_id}/synthetic-rule-readiness')
    def synthetic_rule_assess(preparation_id: UUID,data: srr.Assess,authorization: str | None=Header(default=None),idempotency_key: str=Header()):
        return simulation_adapter().assess(token(authorization),preparation_id,resource_key(idempotency_key),data)

    @app.get('/api/preparations/{preparation_id}/synthetic-rule-readiness/recovery/{request_key}')
    def synthetic_rule_recover(preparation_id: UUID,request_key: str,binding_id: str,as_of: str,authorization: str | None=Header(default=None)):
        return simulation_adapter().recover(token(authorization),preparation_id,resource_key(request_key),simulation_context(binding_id,as_of))

    from . import case_resources as case_resources
    from . import resource_plan_binding
    from . import resource_change_proposals
    @app.get('/api/preparations/{preparation_id}/resource-time-alternatives')
    def case_resource_time_alternatives(preparation_id: UUID,search_from: str,search_until: str,authorization: str | None=Header(default=None)):
        from pydantic import ValidationError
        import json
        try:
            data=resource_change_proposals.Search.model_validate_json(json.dumps(dict(search_from=search_from,search_until=search_until)))
        except ValidationError:raise HTTPException(422,'invalid bounded resource alternative search')
        return resource_change_proposals.read(store,token(authorization),preparation_id,data)

    @app.get('/api/resource-holds/recovery/{request_key}')
    def resource_hold_recover(request_key: str,expected_fingerprint: str | None=Query(default=None,pattern='^[a-f0-9]{64}$'),authorization: str | None=Header(default=None)):
        return resource_change_proposals.recover_resource(store,token(authorization),resource_key(request_key),'HOLD',expected_fingerprint)

    @app.get('/api/resource-combinations/recovery/{request_key}')
    def resource_combination_recover(request_key: str,expected_fingerprint: str | None=Query(default=None,pattern='^[a-f0-9]{64}$'),authorization: str | None=Header(default=None)):
        return resource_change_proposals.recover_resource(store,token(authorization),resource_key(request_key),'COMBINATION',expected_fingerprint)

    @app.get('/api/preparations/{preparation_id}/resource-link/recovery/{request_key}')
    def resource_link_recover(preparation_id: UUID,request_key: str,expected_fingerprint: str | None=Query(default=None,pattern='^[a-f0-9]{64}$'),authorization: str | None=Header(default=None)):
        return resource_change_proposals.recover_link(store,token(authorization),preparation_id,resource_key(request_key),expected_fingerprint)

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
