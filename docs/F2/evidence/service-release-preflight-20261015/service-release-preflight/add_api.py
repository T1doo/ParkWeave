from pathlib import Path
p=Path('src/parkweave/api.py');s=p.read_text().replace('instance_consumer=None, synthetic_rule_readiness=None)', 'instance_consumer=None, synthetic_rule_readiness=None, service_release_preflight=None)',1)
needle='    if proposal_planner is not None:\n'
s=s.replace(needle,"""    if service_release_preflight is not None:
        from .service_release_preflight import ServiceReleasePreflight
        if type(service_release_preflight) is not ServiceReleasePreflight or service_release_preflight.catalog is not capability_catalog or service_release_preflight.store is not store:
            raise Denied('explicit matching owned service release preflight required')
"""+needle,1)
needle='    def cold_inputs():\n'
s=s.replace(needle,"""    from .service_release_preflight import Record as ServiceReleasePreflightRecord

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

"""+needle,1);p.write_text(s)
