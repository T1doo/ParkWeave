from pathlib import Path
import json
b=Path('.runtime/service-release-preflight')
old=Path('.runtime/shared-source-cases')
for name in ['run_window.py','shared_capture.py']:
 s=(old/name).read_text().replace('.runtime/shared-source-cases','.runtime/service-release-preflight').replace('/tmp/parkweave-shared-','/tmp/parkweave-release-preflight-')
 (b/name).write_text(s)
for name in ['root-1-modules.json','root-2-modules.json']:(b/name).write_bytes((old/name).read_bytes())
review=json.loads(Path('.runtime/shared-source-cases-review/assigned-extra-modules.json').read_text())
independent=['tests/test_typed_source_impact.py','tests/test_typed_source_impact_independent.py','tests/test_shared_source_cases.py','tests/test_shared_source_cases_independent.py','tests/test_service_release_preflight.py','tests/test_service_release_preflight_independent.py']
(b/'review-modules.json').write_text(json.dumps(review,indent=2)+'\n');(b/'independent-modules.json').write_text(json.dumps(independent,indent=2)+'\n')
allmods=sum([json.loads((b/name).read_text()) for name in ['root-1-modules.json','root-2-modules.json','review-modules.json','independent-modules.json']],[])
assert len(allmods)==len(set(allmods))==66
(b/'planned-regression.json').write_text(json.dumps(dict(complete_modules=allmods,module_count=len(allmods),whole_repository_run=False,reason='New exact dependency and routes in shared create_app plus original HTML; original service selection/catalog/compiler/consumer/upgrade/history/authority/native boundaries, source adoption/typed impact/worklist and existing UI modules retained in full; two new modules added. Previous scores not reused.'),ensure_ascii=False,indent=2)+'\n')
print(len(allmods))
