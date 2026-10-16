"""Independent pure strict-profile mutations of actual owned-PG proofs.

The two positive documents were captured by the parent core01 window. Their
embedded copy is a structural validation fixture only, not reusable PG evidence.
No DB, HTTP, credentials, grants, business writes or source monkeypatches.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import json
import pytest
from parkweave import p3_never_accepted_closure as closure, controlled_plans as cp

BASELINES=json.loads('[{"action": "DECLINE", "context": {"case_id": "f7e0e3d3-719c-47c3-be0e-873395fe0ca6", "org_id": "org-a", "owner_id": "fixture-a", "park_id": "park-a", "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d", "run_id": "b7f167d9-5c6d-4600-b898-379f7e33ea8c"}, "qualification": {"birth": {"birth_xid": "860", "case_id": "f7e0e3d3-719c-47c3-be0e-873395fe0ca6", "generation": "165e9cbc-f16a-4a39-aec7-2ead25bad477", "org_id": "org-a", "owner_id": "fixture-a", "park_id": "park-a", "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d", "run_id": "b7f167d9-5c6d-4600-b898-379f7e33ea8c", "schema": 1, "scope": "OWNED_SYNTHETIC_BUSINESS_FRONTIER_V1"}, "birth_sha256": "f4382cba97e94a05f4111f4c1362522fe108a9303c80d1cb8b62c4b7bbee93de", "case_id": "f7e0e3d3-719c-47c3-be0e-873395fe0ca6", "closure_state": "DECLINED", "collection_bound": 64, "collections": [{"complete": true, "count": 1, "known": true, "sha256": "0df3f5c1c6a398689eff240b9d31c5edc32bc855947d96d593111b760622acbb", "table": "service_dispatches"}, {"complete": true, "count": 2, "known": true, "sha256": "97e678d6aea596062deb97440b7655724a821b26224c32c8523e54262c625741", "table": "service_dispatch_offers"}, {"complete": true, "count": 4, "known": true, "sha256": "36ad49aac80fedaee9b6c7067057cafe44961d6c16d2bb72a0272eb11d1d8812", "table": "service_dispatch_events"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_receipt_steps"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_step_receipts"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_receipt_events"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "case_local_lifecycles"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "case_local_events"}], "dispatch": {"current_offer_id": "e52ebfdf-478f-445a-a946-d8317aeb7256", "events": [{"action": "OFFER", "actor_id": "prep-specialist-fixture-a", "business_frontier": {"epoch": 0, "generation": "165e9cbc-f16a-4a39-aec7-2ead25bad477", "plan_id": "50244fa8-1ff5-46db-8fda-207f97b443f6", "plan_revision": 3, "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d"}, "fingerprint": "44506158ab866936601d2523968fae289e12c4c53ca977258ebe02843c393ad3", "id": "57c13e74-56b0-475f-b0b1-a5c301d26444", "offer_id": "6f17b7be-71e2-4e5f-9864-0571473d771a", "payload_sha256": "5bf0667483939889ded5a28d4e11100166219b1ac543441ba606bde98b85ea16", "request_key": "08a2f8a3d33f4d6cb7fbe528064d06e3", "revision": 1, "transaction": "887"}, {"action": "DECLINE", "actor_id": "executor-a", "business_frontier": {"epoch": 3, "generation": "165e9cbc-f16a-4a39-aec7-2ead25bad477", "plan_id": "50244fa8-1ff5-46db-8fda-207f97b443f6", "plan_revision": 3, "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d"}, "fingerprint": "54b839b4d38bea2bf32ac190f41244b4106578856dc5c868028559d8fd83ec4a", "id": "1fc9147d-ae17-4ee9-b2b2-d4993b18c7bf", "offer_id": "6f17b7be-71e2-4e5f-9864-0571473d771a", "payload_sha256": "ceb76726d26f9c52e706a6e8259dd742f77ce49b761547d03fd746487c33ed85", "request_key": "33dcdfffcee14f2fbc65157e33dddc91", "revision": 2, "transaction": "889"}, {"action": "REOFFER", "actor_id": "prep-specialist-fixture-a", "business_frontier": {"epoch": 6, "generation": "165e9cbc-f16a-4a39-aec7-2ead25bad477", "plan_id": "50244fa8-1ff5-46db-8fda-207f97b443f6", "plan_revision": 3, "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d"}, "fingerprint": "95c5b8d5ba4e14132bb2163783cad79251cf20833669e07122c3e2083819ffbc", "id": "e83118fa-d5c0-4f91-bfe7-f9978296380c", "offer_id": "e52ebfdf-478f-445a-a946-d8317aeb7256", "payload_sha256": "dc63eab83afe680c6cdca6e7a9956478fcc7204332b5c2957fea68bf7a51fae0", "request_key": "59576042417b45de9ee52f07a9422203", "revision": 3, "transaction": "891"}, {"action": "DECLINE", "actor_id": "executor-a", "business_frontier": {"epoch": 9, "generation": "165e9cbc-f16a-4a39-aec7-2ead25bad477", "plan_id": "50244fa8-1ff5-46db-8fda-207f97b443f6", "plan_revision": 3, "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d"}, "fingerprint": "308123d8052611100e7bd443a5243c1ad3304fd5536abdf9898713089b43bc06", "id": "c640d5ed-b425-4b39-8c62-18ca02ef55bc", "offer_id": "e52ebfdf-478f-445a-a946-d8317aeb7256", "payload_sha256": "4735fb46733301e9dd6335666f61a6e1eb97945fce8a2b278a1db8de02fbd695", "request_key": "289f36bdf8b248eabcf634d38b88f3ed", "revision": 4, "transaction": "893"}], "events_count": 4, "history_sha256": "99a23e6a254c331b38faeac7ba5b587388b28c572bc2c3210f7ee680b23d0189", "id": "4dedc69f-c805-4c73-9178-a7f84d034c11", "offers_count": 2, "revision": 4, "state": "DECLINED"}, "epoch": 12, "ever_started": true, "marker_sha256": "157eb8a97f00e544670324bb41aa42d7a22bd6ef88115be69ad87f2f02235124", "preparation_id": "20da151a-dec5-444c-b36e-ec5fcf836e4d", "previous_plan_id": "50244fa8-1ff5-46db-8fda-207f97b443f6", "profile": "P3_NEVER_ACCEPTED_CLOSED_V1", "protocol_sha256": "18c2b3eb6fa86cc37ba618dd449755a74bb295b227ed7646a85e406259cf4da0", "run_id": "b7f167d9-5c6d-4600-b898-379f7e33ea8c", "schema": 1, "state": "CLOSED_WITHOUT_ACCEPTANCE", "tail": {"P3": "CLOSED_WITHOUT_ACCEPTANCE", "P4": "NO_RECEIPT_EFFECT", "P5": "NO_LOCAL_LIFECYCLE_EFFECT"}, "verified_prefix": [{"adapter_id": "P1", "event_id": "f3a776ac-6b11-4c23-ae73-0d0ac77781a5", "event_revision": 2, "event_sha256": "c8c55279e0630b834b6e9867a5cf43977b25aed7fea4ea811b42a2603ce62ab3", "source_sha256": "25c8f56e9eab0c812ee2c10ebb4c241b2be3ce088ee8e73d1f55e35d2c5db404", "step_id": "0cadbe80-5f95-4de2-8d0a-d81a5db6772e"}, {"adapter_id": "P2", "event_id": "e3c5f604-09f4-43fd-a38f-c1d066343251", "event_revision": 3, "event_sha256": "b43db7e9c19c6b40e81596c1d13ce3de4de63ebf90ab4bacd5b7b4e216ae9704", "source_sha256": "bf079af18deb5eaf66f04dbc9448e02e689effe85f4881ac55ada049bd28152f", "step_id": "d3e6777f-6df3-44a7-a0c2-6096cdad84ce"}]}}, {"action": "WITHDRAW", "context": {"case_id": "ecaf0428-f83a-4c6d-9436-5897d3d8d2e7", "org_id": "org-a", "owner_id": "fixture-a", "park_id": "park-a", "preparation_id": "3b893b96-2646-48b6-bf8a-40fc93b2c410", "run_id": "d3469285-5de0-4388-b3ff-a47fec3f3b2e"}, "qualification": {"birth": {"birth_xid": "754", "case_id": "ecaf0428-f83a-4c6d-9436-5897d3d8d2e7", "generation": "c05b27de-008f-4f41-817f-bd9af8ff9ca7", "org_id": "org-a", "owner_id": "fixture-a", "park_id": "park-a", "preparation_id": "3b893b96-2646-48b6-bf8a-40fc93b2c410", "run_id": "d3469285-5de0-4388-b3ff-a47fec3f3b2e", "schema": 1, "scope": "OWNED_SYNTHETIC_BUSINESS_FRONTIER_V1"}, "birth_sha256": "23ea1ffc7f067c73d5e0a14ac0883468665e0ca20233f78db07cc3fdcbf395f5", "case_id": "ecaf0428-f83a-4c6d-9436-5897d3d8d2e7", "closure_state": "WITHDRAWN", "collection_bound": 64, "collections": [{"complete": true, "count": 1, "known": true, "sha256": "b89e2669a3389a934ffdf3f7aa1a4a13733d2f741d3d58857e30510e6279d640", "table": "service_dispatches"}, {"complete": true, "count": 1, "known": true, "sha256": "05a0f87d6b8eace770a0ebb4bf725080e7a43e4253e23da7aad38f886a49c3f5", "table": "service_dispatch_offers"}, {"complete": true, "count": 2, "known": true, "sha256": "339af57dfc91ece2df2697b780e94d915384447a916a8fb9ab250571bd03b694", "table": "service_dispatch_events"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_receipt_steps"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_step_receipts"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "service_receipt_events"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "case_local_lifecycles"}, {"complete": true, "count": 0, "known": true, "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", "table": "case_local_events"}], "dispatch": {"current_offer_id": "9e7e58eb-ac57-4aaa-a7fd-59e2a44a5f59", "events": [{"action": "OFFER", "actor_id": "prep-specialist-fixture-a", "business_frontier": {"epoch": 0, "generation": "c05b27de-008f-4f41-817f-bd9af8ff9ca7", "plan_id": "5f1c7187-2a27-4ff6-9e69-82d4b36b89a9", "plan_revision": 3, "preparation_id": "3b893b96-2646-48b6-bf8a-40fc93b2c410"}, "fingerprint": "e119427c70da266ec7227e5f2e5a09f8f7342b574e962636f6f42f439150b5cb", "id": "830409f5-fdc2-41f2-abfe-f1dca11b0525", "offer_id": "9e7e58eb-ac57-4aaa-a7fd-59e2a44a5f59", "payload_sha256": "0f3148f3a316a83f475b37b009d282e63da54a855f8df283b9788d613876a576", "request_key": "e5bf83fdb5d44960a6d9924a39ddcb21", "revision": 1, "transaction": "781"}, {"action": "WITHDRAW", "actor_id": "prep-specialist-fixture-a", "business_frontier": {"epoch": 3, "generation": "c05b27de-008f-4f41-817f-bd9af8ff9ca7", "plan_id": "5f1c7187-2a27-4ff6-9e69-82d4b36b89a9", "plan_revision": 3, "preparation_id": "3b893b96-2646-48b6-bf8a-40fc93b2c410"}, "fingerprint": "64b14e081df3d052081b0b17d3a08733add2219ec40ace8c1133c075a352ef74", "id": "7c1e7fa6-2227-44ce-b883-cc99183c013f", "offer_id": "9e7e58eb-ac57-4aaa-a7fd-59e2a44a5f59", "payload_sha256": "d975320be82f5c41169f18c43ba656efb36ea937e06a593804db410d1a11294a", "request_key": "276de07b3304499ab0a1ff8d385052c6", "revision": 2, "transaction": "783"}], "events_count": 2, "history_sha256": "84e75ffba03ca31628377a0f3ef27a0e65f809fc67f8ae9284b8e1cc2f7cc9f5", "id": "f332cd49-31e9-4e78-9fa0-bd7d965712b5", "offers_count": 1, "revision": 2, "state": "WITHDRAWN"}, "epoch": 6, "ever_started": true, "marker_sha256": "3458fafc29fbc17cef1efda538fe0efa321399df088fe71b6ff8cfdab09eeed6", "preparation_id": "3b893b96-2646-48b6-bf8a-40fc93b2c410", "previous_plan_id": "5f1c7187-2a27-4ff6-9e69-82d4b36b89a9", "profile": "P3_NEVER_ACCEPTED_CLOSED_V1", "protocol_sha256": "4317cb0b8c3d78bd8bb231e22f7c4398e824649719a66e6a03d6b1aefead460b", "run_id": "d3469285-5de0-4388-b3ff-a47fec3f3b2e", "schema": 1, "state": "CLOSED_WITHOUT_ACCEPTANCE", "tail": {"P3": "CLOSED_WITHOUT_ACCEPTANCE", "P4": "NO_RECEIPT_EFFECT", "P5": "NO_LOCAL_LIFECYCLE_EFFECT"}, "verified_prefix": [{"adapter_id": "P1", "event_id": "a9be6e14-79f2-4b09-b976-20c70b07ecf9", "event_revision": 2, "event_sha256": "91a68ba91c9a5c3f0871a9e1dc8bc857df0db24f096731f86db1f8f51ba4fb81", "source_sha256": "af8deafff1c1f7d1bd8532512a4e0dde2dd7cbcb7b2c0502c3837b347b2d16f4", "step_id": "bc2e69df-aa72-45cd-92e5-09ac2cf69cbe"}, {"adapter_id": "P2", "event_id": "d8ad0773-522d-41e6-9380-1f95e268d37b", "event_revision": 3, "event_sha256": "ded5be6370634d42d5ab9861103617aae6be6bbb69143fabf8285ef78ec1c700", "source_sha256": "5dbd6dc685a4c23ec67fa1e64dcd886e67eecc5da426f1b99227e19f16eeb723", "step_id": "a0b56cdd-8fff-4721-8da5-e26fff4221dd"}]}}]')


FIELDS=[('birth','generation'),('verified_prefix',0,'step_id'),('verified_prefix',0,'event_id'),('verified_prefix',1,'step_id'),('verified_prefix',1,'event_id'),('dispatch','id'),('dispatch','current_offer_id'),('dispatch','events',0,'id'),('dispatch','events',0,'offer_id')]


def baseline():
 value=deepcopy(BASELINES[0]);q=value['qualification']
 return q,SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id'])),value['context']


def set_identifier(q,path,value):
 node=q
 for key in path[:-1]:node=node[key]
 node[path[-1]]=value
 if path==('birth','generation'):
  q['birth_sha256']=cp._hash(q['birth'])
  for event in q['dispatch']['events']:event['business_frontier']['generation']=value
 if path in (('dispatch','current_offer_id'),('dispatch','events',0,'offer_id')):
  q['dispatch']['current_offer_id']=value
  for event in q['dispatch']['events']:event['offer_id']=value


@pytest.mark.parametrize('index',[0,1],ids=['first-original-terminal','second-original-terminal'])
def test_actual_original_terminal_document_structure_is_accepted(index):
 value=deepcopy(BASELINES[index]);q=value['qualification']
 closure.validate_qualification(q,SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id'])),value['context'])


@pytest.mark.parametrize('path',FIELDS,ids=['birth-generation','p1-step','p1-event','p2-step','p2-event','dispatch-id','current-offer','event-id','offer-id'])
@pytest.mark.parametrize('mutation',['bool','float','none','list','dict','uppercase','hex','braced','urn'])
def test_nested_identifiers_require_exact_canonical_string(path,mutation):
 q,data,context=baseline();original=q
 for key in path:original=original[key]
 values=dict(bool=True,float=1.5,none=None,list=[original],dict={'id':original},uppercase=original.upper(),hex=UUID(original).hex,braced='{'+original+'}',urn='urn:uuid:'+original)
 assert values[mutation]!=original
 set_identifier(q,path,values[mutation])
 with pytest.raises(ValueError):closure.validate_qualification(q,data,context)


@pytest.mark.parametrize('mutation',['unknown','extra','schema-bool','epoch-bool','epoch-zero','ever-false','revision-bool','count-bool','missing-table','offered','accept'])
def test_closed_profile_cannot_downgrade_or_infer_unknown(mutation):
 q,data,context=baseline()
 if mutation=='unknown':q['state']='UNKNOWN'
 elif mutation=='extra':q['inferred_authority']=True
 elif mutation=='schema-bool':q['schema']=True
 elif mutation=='epoch-bool':q['epoch']=True
 elif mutation=='epoch-zero':q['epoch']=0;q['ever_started']=False
 elif mutation=='ever-false':q['ever_started']=False
 elif mutation=='revision-bool':q['dispatch']['revision']=True
 elif mutation=='count-bool':q['collections'][0]['count']=True
 elif mutation=='missing-table':q['collections'].pop()
 elif mutation=='offered':q['closure_state']='OFFERED'
 elif mutation=='accept':q['dispatch']['events'][-1]['action']='ACCEPT'
 with pytest.raises(ValueError):closure.validate_qualification(q,data,context)


def test_actual_product_module_loads_selected_source():
 root=Path(__file__).resolve()
 while not (root/'src/parkweave').is_dir():
  assert root!=root.parent
  root=root.parent
 assert Path(closure.__file__).resolve()==root/'src/parkweave/p3_never_accepted_closure.py'
