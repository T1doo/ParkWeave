"""Observe an unsupported direct administrator corruption; not a product PASS claim."""
from copy import deepcopy
import json
from pathlib import Path
from psycopg.types.json import Jsonb
from test_graph_schema_probes import actual_owned_case,link_fixture,receipt_fixture,preparation_fixture,pg,fixture
from test_shared_source_cases_independent import one_step
from test_service_plan_manual_lock import stored
from test_case_goal_results import snapshot
from test_preparation import headers

OUT=Path('/workspace/ParkWeave/.runtime/shared-source-cases-review')

def test_observe_valid_header_missing_steps_fails_closed_without_repair(actual_owned_case):
    f,traffic=actual_owned_case;p=one_step(f);q=one_step(f)
    good=deepcopy(stored(f,q));bad=deepcopy(good);bad.pop('steps');original_p=deepcopy(stored(f,p))
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(bad),q['preparation_id']))
    before=snapshot(f);calls=len(traffic)
    try:
        response=f[3].get('/api/preparations/'+p['preparation_id']+'/shared-source-cases',headers=headers(f[2]))
        result={'scope':'OBSERVATION_ONLY_UNSUPPORTED_DIRECT_DB_ADMIN_CORRUPTION','source_sha':'bc4f384fa32817ddf3b332f898d59b5b994bfe2f','damage':'Original valid plan object and valid id/revision retained; steps key removed by direct owner-role SQL, impossible through supported plan commands','http_status':response.status_code,'response_is_generic_internal_error':response.text=='Internal Server Error','items_or_plan_contents_exposed':('items' in response.text or good['id'] in response.text),'business_snapshot_unchanged':snapshot(f)==before,'anchor_original_plan_unchanged':stored(f,p)==original_p,'damaged_plan_not_auto_repaired':stored(f,q)==bad,'request_methods':[r['method'] for r in traffic[calls:]],'not_a_product_positive_validation':True}
        assert result['business_snapshot_unchanged'] and result['anchor_original_plan_unchanged'] and result['damaged_plan_not_auto_repaired']
        assert not result['items_or_plan_contents_exposed'] and result['request_methods']==['GET']
    finally:
        with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(good),q['preparation_id']))
    restored=f[3].get('/api/preparations/'+p['preparation_id']+'/shared-source-cases',headers=headers(f[2]))
    result['restored_original_by_test_owner_then_http_status']=restored.status_code
    assert restored.status_code==200 and stored(f,q)==good
    (OUT/'admin-corruption-observation.json').write_text(json.dumps(result,indent=2)+'\n')
