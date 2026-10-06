import importlib.util
import json
from pathlib import Path
import hashlib
import xml.etree.ElementTree as ET
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('parkweave_acceptance',ROOT/'scripts/run_acceptance.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def test_whole_acceptance_never_passes_and_missing_tests_are_incomplete(tmp_path):
    rows=[{'id':'AT-02','stage':'F1','gate':'LIVE_BLOCKED','engineering_selectors':['tests/test_intern_adapter.py::test_one','tests/test_intern_adapter.py::test_missing']}]
    junit=tmp_path/'result.xml'
    junit.write_text('<testsuites><testsuite><testcase classname="test_intern_adapter" name="test_one[x]"/></testsuite></testsuites>')
    result=runner.summarize(rows,junit,0)
    assert result['whole_AT_EX']=='NOT_RUN' and result['cases'][0]['whole_status']=='NOT_RUN'
    assert result['cases'][0]['engineering_subset']=='INCOMPLETE'
    rows[0]['engineering_selectors'].pop();result=runner.summarize(rows,junit,0)
    assert result['cases'][0]['engineering_subset']=='PARTIAL_PASS' and result['cases'][0]['whole_status']=='NOT_RUN'
    junit.write_text('<testsuites><testsuite><testcase classname="test_intern_adapter" name="test_one"><failure>secret-like-error</failure></testcase></testsuite></testsuites>')
    result=runner.summarize(rows,junit,1)
    assert result['cases'][0]['engineering_subset']=='FAIL' and 'secret-like-error' not in repr(result)


def test_fixed_bindings_complete_unique_and_safe():
    bindings=json.loads((ROOT/'docs/F1/ATBindings.json').read_text(encoding='utf-8'));spec=json.loads((ROOT/'docs/验收规格.json').read_text(encoding='utf-8'))
    rows=runner.validate_bindings(bindings,spec);assert len(rows)==42
    for row in rows:
        for selector in row['engineering_selectors']:
            file,name=selector.split('::')
            assert 'def '+name+'(' in (ROOT/file).read_text(encoding='utf-8'),selector
    bad={'cases':[dict(r) for r in rows]};bad['cases'][0]['whole_status']='PASS'
    with pytest.raises(ValueError):runner.validate_bindings(bad,spec)
    bad={'cases':[dict(r) for r in rows]};bad['cases'][0]['engineering_selectors']=['../secret::test_x']
    with pytest.raises(ValueError):runner.validate_bindings(bad,spec)


def test_sources_archive_integrity():
    records=json.loads((ROOT/'docs/sources/V1/manifest.json').read_text(encoding='utf-8'))
    assert len(records)==2
    for item in records:
        data=(ROOT/'docs/sources/V1'/item['name']).read_bytes()
        assert len(data)==item['size'] and len(data.splitlines())==item['lines'] and hashlib.sha256(data).hexdigest()==item['sha256']
        assert data.endswith(b'\n') and item['terminal_newline_restored'] is True
