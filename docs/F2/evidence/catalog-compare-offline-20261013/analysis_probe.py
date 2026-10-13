from pathlib import Path
import ast,json,subprocess,sys
sys.path[:0]=['src','tests']
import test_linux_trial_catalog as t
from parkweave import native_run_access_preflight as p
root=Path('.runtime/catalog-compare-offline-20261013');baseline='4649970278e29b999a2a4f332ba7380f20795a3f'
old=subprocess.check_output(['git','show',baseline+':scripts/linux_trial/worker.py'],text=True)
setup=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='setup')
block=next(n for n in setup.body if isinstance(n,ast.With) and isinstance(n.items[0].context_expr,ast.Call) and n.items[0].context_expr.args and isinstance(n.items[0].context_expr.args[0],ast.Constant) and n.items[0].context_expr.args[0].value=='ROLE_CREATE')
acl=t.BuiltinFunctionACL()
exec(compile(ast.Module(body=[block],type_ignores=[]),'frozen_original_worker_acl','exec'),dict(
    owner=t.SimpleNamespace(connect=lambda:acl),observation=t.Observation(),sql=t.sql,runtime=t.runtime,
    db='fixture_'+'a'*32,config={'passwords':{'pwci_app':'SYNTHETIC_ONLY','pwci_writer':'SYNTHETIC_ONLY'}}))
observations=[]
for label,state in [('ORIGINAL_SOURCE_DEFAULT_FUNCTION_ACL',acl),('FIXED_SOURCE_DEFAULT_FUNCTION_ACL',t.apply_actual_acl())]:
    spec,catalog=t.trial_inputs()
    catalog['privileges']['app:control_system_execute']=state.can_execute('pwci_app')
    catalog['privileges']['writer:EXECUTE:pg_control_system():']=state.can_execute('pwci_writer')
    catalog=p.CatalogSnapshot.model_validate(catalog).model_dump()
    report=p.analyze(p.InstallationSpec.model_validate(spec.model_dump()).model_dump(),catalog)
    observations.append(dict(label=label,analyzer='RETURNED',status=report['status'],change_count=len(report['changes']),
        nonpass_checks=[{'check':r['check'],'status':r['status']} for r in report['checks'] if r['status']!='PASS'],
        app_execute=state.can_execute('pwci_app'),writer_execute=state.can_execute('pwci_writer'),
        scope='One-function ACL DI; all other catalog facts synthetic'))
spec,catalog=t.trial_inputs();del catalog['columns']['runs.native_run_access_protocol']
catalog=p.CatalogSnapshot.model_validate(catalog).model_dump();r=p.analyze(spec.model_dump(),catalog)
observations.append(dict(label='MISSING_COLUMN_CONTROL',analyzer='RETURNED',status=r['status'],change_count=len(r['changes'])))
spec,catalog=t.trial_inputs();v=spec.model_dump();v['policy']['generations']={'synthetic_non_json':object()}
spec=p.InstallationSpec.model_validate(v)
try:p.analyze(spec.model_dump(),catalog)
except TypeError:observations.append(dict(label='NON_JSON_GENERATIONS_CONTROL',analyzer='RAISED',exception_class='TypeError',
    real_worker_relevance='Worker uses text-valued generation rows; branch control, not proposed VM cause'))
assert [v.get('status') for v in observations[:3]]==['REFUSED','PASS','APPROVAL_REQUIRED']
record=dict(baseline=baseline,fix_source='e7c3cdd050465a2cf66cfd3cde5ad303a3dc7b6f',
    qualification='OFFLINE_SYNTHETIC_ONLY; does not identify disposed VM report or its sole root cause',
    observations=observations,actual_PG_connections=0,actual_privilege_changes=0,ci_triggers=0)
(root/'analysis-outcomes.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
