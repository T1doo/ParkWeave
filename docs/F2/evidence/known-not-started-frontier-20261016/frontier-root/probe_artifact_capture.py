"""Metadata-only artifact routing probe, not a product test or score."""
from pathlib import Path
from uuid import uuid4
import importlib.util,os,json,hashlib
root=Path('/workspace/ParkWeave');dest=root/'.runtime/frontier-root/v1/artifact-route-probe';dest.mkdir(parents=True,exist_ok=True)
os.environ['LEGACY_ARTIFACT_DESTINATION']=str(dest)
path=root/'.runtime/frontier-root/v1/runner/legacy_artifact_capture.py';spec=importlib.util.spec_from_file_location('frontier_artifact_probe',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
config=type('ProbeConfig',(),{})();name='frontier-route-probe-'+uuid4().hex+'.private.json';original=root/'.runtime/plan-replacement-ui-fixture/artifacts'/name
assert not original.exists();module.pytest_configure(config)
try:
 original.parent.mkdir(parents=True,exist_ok=True)
 with os.fdopen(os.open(original,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:stream.write('[]\n')
 assert original.read_bytes()==b'[]\n'
 actual=dest/'artifacts/plan-replacement-ui-fixture/artifacts'/name
 assert actual.read_bytes()==b'[]\n' and actual.stat().st_mode&0o777==0o600
 assert not config._carry_original_exists(original)
finally:module.pytest_unconfigure(config)
assert not original.exists()
record={'scope':'ARTIFACT_CAPTURE_ONLY_NOT_PRODUCT_TEST','status':'PASS','product_logic_patched':False,'old_path_created':False,'mapped_private_mode':'0600','original':str(original.relative_to(root)),'actual':str(actual.relative_to(root)),'plugin_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(dest/'probe-result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
