"""Safe identifiers only: poisoned private XML/metadata never become public output."""
import ast
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import pytest
from test_windows_ci_preparation import module

ROOT=Path(__file__).resolve().parents[1]
KNOWN='tests/test_lifecycle.py::test_config_write_is_exclusive_and_no_secret_fields'
POISON='SYNTHETIC_PRIVATE_MESSAGE_PATH_TOKEN_MATERIAL'


def junit(tmp_path,entries):
    runtime=tmp_path/'.runtime';runtime.mkdir(exist_ok=True)
    file=runtime/('pytest-'+'a'*32+'.xml');root=ET.Element('testsuites');suite=ET.SubElement(root,'testsuite')
    for classname,name,kind in entries:
        case=ET.SubElement(suite,'testcase',classname=classname,name=name)
        if kind:ET.SubElement(case,kind,message=POISON).text=POISON
        ET.SubElement(case,'system-out').text=POISON
    file.write_bytes(ET.tostring(root,encoding='utf-8'));return file,str(file.relative_to(tmp_path))


def test_failure_ids_use_exact_allowlist_drop_parameters_and_private_xml(tmp_path):
    m=module('diagnostics');path,reference=junit(tmp_path,[('tests.test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields['+POISON+']','failure'),('test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields[second]','error'),(POISON,POISON,'failure'),('test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields','')])
    result=m.failure_tests(tmp_path,reference.replace('/','\\'))
    assert result['failed_test_ids']==[KNOWN] and result['failed_cases']==3 and result['unknown_failed_cases']==1 and result['test_cases_seen']==4
    assert POISON not in json.dumps(result) and len(json.dumps(result))<1000


@pytest.mark.parametrize('reference',[None,'../../'+POISON,'.runtime/../outside.xml','C:\\'+POISON,'/tmp/'+POISON,'.runtime/'+POISON+'.xml',123,{'token':POISON},'.runtime/pytest-'+'a'*32+'.xml'+POISON])
def test_junit_path_reference_refused_without_echo(tmp_path,reference):
    m=module('diagnostics');result=m.failure_tests(tmp_path,reference);assert result['state']=='JUNIT_PATH_REFUSED' and not result['failed_test_ids'] and POISON not in json.dumps(result)


@pytest.mark.parametrize('payload',[b'<unclosed>',b'<!DOCTYPE testsuite [<!ENTITY x "PRIVATE">]><testsuite/>',b'<private/>'])
def test_malformed_xml_entities_or_unknown_root_are_refused(tmp_path,payload):
    m=module('diagnostics');path,reference=junit(tmp_path,[]);path.write_bytes(payload);result=m.failure_tests(tmp_path,reference)
    assert result['state'] in ('JUNIT_INVALID','JUNIT_FORMAT_REFUSED') and not result['failed_test_ids'] and POISON not in json.dumps(result)


def test_missing_oversize_and_case_limits_are_visible(tmp_path,monkeypatch):
    m=module('diagnostics');path,reference=junit(tmp_path,[]);path.unlink();assert m.failure_tests(tmp_path,reference)['state']=='JUNIT_MISSING'
    monkeypatch.setattr(m,'MAX_JUNIT_BYTES',128);path.write_bytes(b'x'*129);assert m.failure_tests(tmp_path,reference)['state']=='JUNIT_UNREADABLE_OR_OVERSIZE'
    monkeypatch.setattr(m,'MAX_JUNIT_BYTES',4096);monkeypatch.setattr(m,'MAX_TEST_CASES',2)
    junit(tmp_path,[('test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields','failure')]*3)
    result=m.failure_tests(tmp_path,reference);assert result['state']=='JUNIT_CASE_LIMIT' and result['test_cases_seen']==2 and result['ids_truncated'] and result['failed_cases']==2


def test_truncated_allowlisted_ids_preserve_failure_counts(tmp_path):
    m=module('diagnostics');ids=sorted(m._allowed_tests())[:m.MAX_FAILURE_IDS+3]
    entries=[]
    for id in ids:
        file,name=id.split('::');entries.append((Path(file).stem,name+'['+POISON+']','failure'))
    path,ref=junit(tmp_path,entries);result=m.failure_tests(tmp_path,ref)
    assert result['failed_cases']==len(ids) and len(result['failed_test_ids'])==m.MAX_FAILURE_IDS and result['ids_truncated'] and result['unknown_failed_cases']==0 and POISON not in json.dumps(result)


def test_exception_categories_phases_and_cleanup_are_allowlisted_bounded():
    m=module('diagnostics');error=type(POISON,(Exception,),{})(POISON);error.add_note(POISON);error.parkweave_diagnostic_phase=POISON;error.parkweave_owned_browser_cleanup=['TimeoutExpired',POISON]*50
    row=m.exception_row(POISON,error,POISON)
    assert row['case']=='suite_exception' and row['phase']=='UNKNOWN' and row['category']=='OTHER' and len(row['owned_browser_cleanup_failures'])==6 and row['cleanup_failures_count']==100 and row['cleanup_categories_truncated']
    assert POISON not in json.dumps(row)
    error.parkweave_owned_browser_cleanup={'token':POISON};assert m.exception_row([],error,[])['cleanup_diagnostics']=='INVALID_METADATA'
    assert m.exception_row('lifecycle_exception',RuntimeError(POISON),'api_case_wait')['phase']=='api_case_wait'


@pytest.mark.parametrize('counts',[{'PASS':POISON,'FAIL':0,'SKIP':0},{'PASS':True,'FAIL':0,'SKIP':0},{'PASS':10001,'FAIL':0,'SKIP':0},{'PASS':1,'FAIL':0,'SKIP':0,POISON:POISON}])
def test_counts_refuse_unsafe_types_extra_keys_and_bounds(tmp_path,counts):
    m=module('diagnostics');path=tmp_path/'report.json';path.write_text(json.dumps({'engineering_total_counts':counts,'whole_AT_EX':'NOT_RUN'}),encoding='utf-8')
    with pytest.raises(ValueError):m.read_report(path)


def test_browser_summary_drops_external_versions_text_and_unknown_fields():
    m=module('diagnostics');result=m.browser_summary({'browser_version':POISON,'environment':POISON,'case':POISON,'grouped_questions':3,'injection_text_only':True,'clarification':'UNKNOWN','extra':POISON})
    assert result=={'grouped_questions':3,'injection_text_only':True,'clarification':'UNKNOWN'} and POISON not in json.dumps(result)


def test_committed_allowlist_exactly_matches_trusted_test_functions():
    m=module('diagnostics');expected=set()
    for path in (ROOT/'tests').glob('test_*.py'):
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):expected.add(str(path.relative_to(ROOT)).replace('\\','/')+'::'+node.name)
    assert m._allowed_tests()==expected


def test_browser_binding_failure_has_explicit_phase_without_path(tmp_path,monkeypatch):
    m=module('browser_smoke')
    # Restore simulated OS before pytest/pathlib or formatter touches paths.
    with monkeypatch.context() as patch:
        patch.setattr(m.os,'name','nt');patch.delenv('CHROMEWEBDRIVER',raising=False)
        with pytest.raises(RuntimeError) as error:m.run_browser(tmp_path,POISON)
    row=module('diagnostics').exception_row('lifecycle_exception',error.value,'native_browser')
    assert row['phase']=='browser_driver_binding' and row['category']=='RuntimeError' and POISON not in json.dumps(row)


@pytest.mark.parametrize('diagnostic_state',['AVAILABLE','JUNIT_MISSING','JUNIT_INVALID','JUNIT_UNREADABLE_OR_OVERSIZE','ALLOWLIST_UNAVAILABLE','REPORT_INVALID'])
@pytest.mark.parametrize('platform',['posix','nt'])
def test_suite_publishes_allowlisted_failures_in_job_summary_and_keeps_exit_failure(tmp_path,monkeypatch,capsys,diagnostic_state,platform):
    m=module('native_suite');m.REPO=tmp_path;m.require_server=lambda:None
    monkeypatch.setattr(m,'os',SimpleNamespace(name=platform,environ=m.os.environ))
    path,reference=junit(tmp_path,[('test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields['+POISON+']','failure'),(POISON,POISON,'error')])
    if diagnostic_state=='JUNIT_MISSING':path.unlink()
    elif diagnostic_state=='JUNIT_INVALID':path.write_bytes(b'<unclosed>')
    elif diagnostic_state=='JUNIT_UNREADABLE_OR_OVERSIZE':path.write_bytes(b'x'*(4*1024*1024+1))
    if diagnostic_state=='ALLOWLIST_UNAVAILABLE':
        def unavailable():raise ValueError(POISON)
        monkeypatch.setitem(m.failure_tests.__globals__,'_allowed_tests',unavailable)
    summary=tmp_path/'job-summary.md'
    monkeypatch.setattr(m.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'));monkeypatch.setattr(m.sys,'argv',['native_suite','--report',str(tmp_path/'suite.json')])
    monkeypatch.setattr(m.os,'environ',{'PARKWEAVE_OWNER_DSN':'host=127.0.0.1 dbname=parkweave user=park_ci_owner','PARKWEAVE_DSN':'host=127.0.0.1 dbname=parkweave user=parkweave_app','PARKWEAVE_TEST_OWNER_DSN':'host=127.0.0.1 dbname=postgres user=park_ci_owner','GITHUB_STEP_SUMMARY':str(summary),'GITHUB_TOKEN':POISON})
    def run(command,**kwargs):
        assert 'GITHUB_TOKEN' not in kwargs['env'] and 'GITHUB_STEP_SUMMARY' not in kwargs['env']
        if 'scripts/run_acceptance.py' in command:
            Path(command[-1]).write_text(json.dumps({'engineering_total_counts':{'PASS':0,'FAIL':2,'SKIP':0},'whole_AT_EX':'NOT_RUN','private_junit':reference,'private_log':POISON,'arbitrary':POISON}),encoding='utf-8')
            if diagnostic_state=='REPORT_INVALID':Path(command[-1]).write_bytes(b'[]')
            return SimpleNamespace(returncode=1,stdout=POISON,stderr=POISON)
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr=POISON)
        return SimpleNamespace(returncode=1 if any(str(x).endswith('Setup.ps1') for x in command) else 0,stdout=POISON,stderr=POISON)
    monkeypatch.setattr(m,'run_owned_job',lambda command,**kwargs:run(command,**kwargs))
    monkeypatch.setattr(m.subprocess,'run',run);assert m.main()==1
    rows=json.loads((tmp_path/'suite.json').read_text(encoding='utf-8'))['cases'];reg=next(x for x in rows if x['case']=='full_engineering_regression')
    assert reg['status']=='FAIL' and reg['exit_code']==1
    if diagnostic_state!='REPORT_INVALID':assert reg['counts']['FAIL']==2
    if diagnostic_state=='REPORT_INVALID':
        assert any(x['case']=='full_engineering_regression' and x.get('phase')=='regression_report' and x['category']=='ValueError' and x['status']=='FAIL' for x in rows)
        assert 'failure_diagnostics' not in reg
    else:assert reg['failure_diagnostics']['state']==diagnostic_state
    if diagnostic_state=='AVAILABLE':assert reg['failure_diagnostics']['failed_test_ids']==[KNOWN] and reg['failure_diagnostics']['unknown_failed_cases']==1
    elif diagnostic_state!='REPORT_INVALID':assert reg['failure_diagnostics']['failed_test_ids']==[]
    assert POISON not in summary.read_text(encoding='utf-8') and POISON not in capsys.readouterr().out
    assert len(summary.read_bytes())<12000


def test_preflight_missing_configuration_emits_safe_phase_instead_of_raw_key(tmp_path,monkeypatch,capsys):
    m=module('native_suite');m.require_server=lambda:None;monkeypatch.setattr(m.sys,'argv',['native_suite','--report',str(tmp_path/'suite.json')]);monkeypatch.setattr(m.os,'environ',{'GITHUB_TOKEN':POISON})
    assert m.main()==1
    row=json.loads((tmp_path/'suite.json').read_text(encoding='utf-8'))['cases'][0]
    assert row=={'case':'suite_initialization','status':'FAIL','phase':'configuration','category':'KeyError'}
    assert POISON not in capsys.readouterr().out


@pytest.mark.parametrize('codec',['utf-16','utf-16-le','utf-16-be'])
@pytest.mark.parametrize('doctype',[False,True])
def test_non_utf8_xml_is_refused_even_without_bom(tmp_path,codec,doctype):
    m=module('diagnostics');path,reference=junit(tmp_path,[])
    xml=('<!DOCTYPE testsuite [<!ENTITY x "PRIVATE">]>' if doctype else '')+'<testsuite/>'
    path.write_bytes(xml.encode(codec));result=m.failure_tests(tmp_path,reference)
    assert result['state']=='JUNIT_FORMAT_REFUSED' and result['failed_test_ids']==[]


def test_non_utf8_declared_xml_is_refused(tmp_path):
    m=module('diagnostics');path,reference=junit(tmp_path,[])
    path.write_bytes(b'<?xml version="1.0" encoding="UTF-16"?><testsuite/>')
    assert m.failure_tests(tmp_path,reference)['state']=='JUNIT_FORMAT_REFUSED'


@pytest.mark.parametrize('failure',[FileNotFoundError,ValueError,TypeError,KeyError])
def test_unavailable_allowlist_is_constant_and_does_not_echo(tmp_path,monkeypatch,failure):
    m=module('diagnostics');path,reference=junit(tmp_path,[])
    def unavailable():raise failure(POISON)
    monkeypatch.setattr(m,'_allowed_tests',unavailable)
    result=m.failure_tests(tmp_path,reference)
    assert result['state']=='ALLOWLIST_UNAVAILABLE' and POISON not in json.dumps(result)


@pytest.mark.parametrize('payload',[b'{invalid',b'[]',b'null',b'x'* (512*1024+1)],ids=['malformed','array','null','oversize'])
def test_report_malformed_non_mapping_and_size_are_rejected(tmp_path,payload):
    m=module('diagnostics');path=tmp_path/'report.json';path.write_bytes(payload)
    with pytest.raises(ValueError):m.read_report(path)


def test_overlong_junit_fields_are_unknown_without_echo(tmp_path):
    m=module('diagnostics');path,reference=junit(tmp_path,[(POISON*20,'test_name','failure'),('test_lifecycle',POISON*50,'error')])
    result=m.failure_tests(tmp_path,reference)
    assert result['failed_cases']==2 and result['unknown_failed_cases']==2 and result['failed_test_ids']==[] and POISON not in json.dumps(result)


def test_linked_private_junit_is_refused(tmp_path):
    m=module('diagnostics');path,reference=junit(tmp_path,[]);outside=tmp_path/'outside.xml';outside.write_bytes(path.read_bytes());path.unlink()
    try:path.symlink_to(outside)
    except OSError:pytest.skip('platform cannot create test-owned symlink')
    assert m.failure_tests(tmp_path,reference)['state']=='JUNIT_PATH_REFUSED'



def test_long_parameter_is_mapped_before_length_check_and_all_cases_aggregate(tmp_path):
    m=module('diagnostics')
    _,reference=junit(tmp_path,[('test_lifecycle','test_config_write_is_exclusive_and_no_secret_fields['+POISON*100+']','failure')]*42)
    result=m.failure_tests(tmp_path,reference)
    assert result['failed_test_counts']=={KNOWN:42}
    assert result['mapped_failed_cases']==42 and result['unknown_failed_cases']==result['mapped_cases_omitted']==0
    assert POISON not in json.dumps(result)
    public=module('publish_summary').failure_diagnostics(result,{KNOWN})
    assert public['failed_test_counts']=={KNOWN:42}
    result['mapped_failed_cases']=41
    assert module('publish_summary').failure_diagnostics(result,{KNOWN})['state']=='DIAGNOSTIC_FIELDS_INVALID'
