"""One bounded actual HTTP/PG future VERSION compatibility negative."""
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import json,pytest
from conftest import fixture,pg
from parkweave import registered_dependencies as deps
from parkweave.resource_holds import RESOURCE_ID
from parkweave.api import create_app
from test_service_case_steps import preparation_fixture,receipt_fixture,link_fixture,read,adopt,adopt_body,verified
from test_case_goal_results import complete,snapshot
from test_service_plan_manual_lock import stored
from test_service_plan_recovery import recover
from test_new_enterprise_local_chain import actual_http
OUT=Path('/workspace/ParkWeave/.runtime/independent-registered-local-revision-projection-final-review/evidence')

def test_valid_local_adoption_history_remains_readable_after_current_version_change(link_fixture,monkeypatch):
    with actual_http(create_app(link_fixture[0])) as (client,requests):
        f=(*link_fixture[:3],client);p,*_=complete(f);id=uuid4()
        with f[1].connect() as c:
            c.execute('INSERT INTO synthetic_resources(id,park_id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source) SELECT %s,park_id,%s,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE id=%s',(id,'SYNTHETIC independent version compatibility resource',RESOURCE_ID))
            c.execute('INSERT INTO synthetic_resource_grants(principal_id,resource_id,park_id,org_id,capability,active) SELECT principal_id,%s,park_id,org_id,capability,active FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s',(id,'fixture-a',RESOURCE_ID))
        view=read(f,p).json();body=adopt_body(f,{**p,'revision':view['preparation_revision']});body.update(expected_plan_revision=view['revision'],local_revision=True,reason='SYNTHETIC independent genuine local adoption');key=uuid4().hex
        response=adopt(f,p,body,key);assert response.status_code==201
        for adapter in ('P2','P3','P4'):verified(f,p,adapter)
        assert read(f,p).json()['state']=='VERIFIED' and recover(f,p,key).json()['status']=='COMMITTED'
        original=stored(f,p);before=snapshot(f);old_version=deps.VERSION
        # This private process-only replacement models future contract VERSION, not source edits.
        monkeypatch.setattr(deps,'VERSION',old_version+1)
        actual=read(f,p);recovery=recover(f,p,key);after=snapshot(f)
        accepted=actual.status_code==200
        expected_ids={s['id'] for s in original['steps']};actual_ids=set(actual.json()['change_impact']['affected']) if accepted else set()
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'technical-version-evidence.json').write_text(json.dumps(dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_http=True,pg=True,technical_future_version_simulation=True,source_files_not_modified=True,stored_original_and_local_adopt_successful=True,all_four_original_verifications_before_upgrade=True,old_version=old_version,simulated_current_version=deps.VERSION,ordinary_get_status=actual.status_code,recovery_status=recovery.status_code,expected_statuses=[200,200],expected_unknown_scope='THIS_CASE',actual_unknown_scope=actual.json()['change_impact']['unknown_scope'] if accepted else None,expected_affected_count=len(expected_ids),actual_affected_count=len(actual_ids),missed_invalidation=len(expected_ids-actual_ids) if accepted else None,wrong_invalidation=len(actual_ids-expected_ids) if accepted else None,business_and_history_row_values_unchanged=after==before,stored_plan_unchanged=stored(f,p)==original,source_write=False,model_calls=0),indent=2)+'\n')
        assert (actual.status_code,recovery.status_code)==(200,200)
        assert actual.json()['change_impact']['unknown_scope']=='THIS_CASE' and actual_ids==expected_ids
        assert recovery.json()['status']=='COMMITTED' and recovery.json()['read_only'] and not recovery.json()['automatically_replayed']
        assert stored(f,p)['events']==original['events'] and [s['contract'] for s in stored(f,p)['steps']]==[s['contract'] for s in original['steps']]
