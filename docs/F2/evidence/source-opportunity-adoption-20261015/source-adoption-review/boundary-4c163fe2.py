"""Independent physical-file checks for the bounded static diagnostics list."""
import importlib.util
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path('/workspace/ParkWeave')
file=ROOT/'scripts/windows_ci/diagnostics.py'
spec=importlib.util.spec_from_file_location('source_adoption_independent_diagnostics',file)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
original_file=m.__file__
limit=524288
known='tests/test_lifecycle.py::test_config_write_is_exclusive_and_no_secret_fields'
poison='SYNTHETIC_PRIVATE_ALLOWLIST_BOUNDARY_SENTINEL'
observations=[]
real=m._allowed_tests()
assert len(real)==2612 and known in real
observations.append(dict(case='committed_2612_ids_load',result='PASS',bytes=file.with_name('diagnostic-test-ids.json').stat().st_size))
with tempfile.TemporaryDirectory(prefix='pw-source-allowlist-independent-',dir='/tmp') as td:
    root=Path(td);path=root/'diagnostic-test-ids.json';m.__file__=str(root/'diagnostics.py')
    raw=json.dumps({'schema':1,'test_ids':[known]},separators=(',',':')).encode()
    path.write_bytes(raw+b' '*(limit-len(raw)))
    assert path.stat().st_size==limit and m._allowed_tests()==frozenset([known])
    observations.append(dict(case='physical_exact_512KiB',result='PASS',bytes=path.stat().st_size))
    with path.open('ab') as stream:stream.write(b' ')
    try:m._allowed_tests()
    except ValueError as error:assert str(error)=='diagnostic input too large'
    else:raise AssertionError('oversized actual file was accepted')
    runtime=root/'.runtime';runtime.mkdir();private=runtime/('pytest-'+'b'*32+'.xml')
    suite=ET.Element('testsuite');case=ET.SubElement(suite,'testcase',classname='test_lifecycle',name=known.split('::')[-1]);ET.SubElement(case,'failure',message=poison).text=poison
    private.write_bytes(ET.tostring(suite))
    response=m.failure_tests(root,str(private.relative_to(root)))
    assert response=={'state':'ALLOWLIST_UNAVAILABLE','failed_test_ids':[],'test_cases_seen':0,'failed_cases':0,'unknown_failed_cases':0,'ids_truncated':False}
    assert poison not in json.dumps(response)
    observations.append(dict(case='physical_512KiB_plus_one_and_public_no_echo',result='PASS',bytes=path.stat().st_size,response=response))
    for label,value in [('count_3001',{'schema':1,'test_ids':['tests/test_guard.py::test_bound_'+str(i) for i in range(3001)]}),('duplicate',{'schema':1,'test_ids':[known,known]}),('schema_changed',{'schema':2,'test_ids':[known]})]:
        path.write_text(json.dumps(value))
        assert path.stat().st_size<limit
        try:m._allowed_tests()
        except ValueError as error:assert str(error)=='invalid allowlist'
        else:raise AssertionError(label+' unexpectedly accepted')
        observations.append(dict(case=label,result='PASS',bytes=path.stat().st_size))
m.__file__=original_file
result={'tested_sha':'4c163fe23d8a841ece7b796e40e35511d70a0797','scope':'ACTUAL_TEMPORARY_FILES_AND_ORIGINAL_LOADER_PUBLIC_FAILURE_PROJECTION_NO_MODELS_NO_BROWSER','literal_cap_bytes':limit,'checks':len(observations),'observations':observations}
(ROOT/'.runtime/source-adoption-review/boundary-4c163fe2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'checks':len(observations),'result':'PASS','literal_cap_bytes':limit}))
