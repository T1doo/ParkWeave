"""Real local publisher stdout and hostile metadata; no GitHub writes or CI."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import os
import io
import pytest
from parkweave.process_env import minimal_environment
from test_windows_ci_preparation import module,ROOT
from test_summary_publication import publication,KNOWN,POISON,console_json

PREFIX='::notice title=ParkWeave safe diagnostics::'


def payloads(commands):
    assert all(c.startswith(PREFIX) and '\n' not in c and '\r' not in c for c in commands)
    # GitHub workflow command message escapes, in the documented inverse order.
    return [json.loads(c[len(PREFIX):].replace('%0D','\r').replace('%0A','\n').replace('%25','%')) for c in commands]


def test_real_publisher_CLI_annotations_expose_safe_failure_without_paths(publication):
    source,path,output=publication
    row=json.loads(path.read_bytes());row['cases'][0].update(phase='regression_run',category='AssertionError',private_log=POISON)
    path.write_text(json.dumps(row),encoding='utf-8')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/windows_ci/publish_summary.py')],env=minimal_environment(os.environ,**source),capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and result.stderr==''
    public=console_json(result.stdout);assert public['cases'][0]['status']=='FAIL'
    commands=[line for line in result.stdout.splitlines() if line.startswith(PREFIX)];header,case=payloads(commands)
    assert header['report_state']=='COMPLETED' and header['case_counts']=={'PASS':0,'FAIL':1,'NOT_RUN':0}
    assert case['case']=='full_engineering_regression' and case['phase']=='regression_run' and case['category']=='AssertionError'
    assert case['failed_test_ids']==['test_lifecycle::test_config_write_is_exclusive_and_no_secret_fields']
    assert case['counts']=={'PASS':0,'FAIL':1,'SKIP':0}
    for private in (POISON,str(path),str(output),'GITHUB_TOKEN','PARKWEAVE_OWNER_DSN','123456','a'*40,'tests/'):
        assert private not in '\n'.join(commands)


@pytest.mark.parametrize('field', ['case','status','phase','category','reason','failed_test_id','active_phase','report_state'])
def test_hostile_annotation_fields_fail_closed_before_any_case(publication,field):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    attack='SYNTHETIC\r\n::error file=/private, title=INJECTED::bad%0A::add-mask::value'
    if field=='failed_test_id':public['cases'][0]['failure_diagnostics']['failed_test_ids']=[attack]
    elif field in ('active_phase','report_state'):public[field]=attack
    else:public['cases'][0][field]=attack
    commands,ok=m.annotation_commands(public)
    assert not ok and payloads(commands)==[{'kind':'publication','state':'ANNOTATIONS_UNAVAILABLE'}]
    assert 'INJECTED' not in ''.join(commands) and '/private' not in ''.join(commands)


def test_unknown_nested_fields_are_discarded_and_PASS_rows_not_emitted(publication):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    public['environment']=POISON;public['cases'][0]['raw_log']=POISON
    public['cases'][0]['failure_diagnostics']['raw_error']=POISON
    public['cases'].append({'case':'Setup_native','status':'PASS','private_path':POISON})
    commands,ok=m.annotation_commands(public);assert ok and POISON not in ''.join(commands)
    assert len(commands)==2 and payloads(commands)[0]['case_counts']['PASS']==1


def test_batch_case_limit_and_global_ID_limit_have_exact_omission_counts(publication):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    ids=sorted(m._allowed_tests())[:25];row=public['cases'][0];row['failure_diagnostics']['failed_test_ids']=ids
    public['cases']=[deepcopy(row) for _ in range(32)]
    commands,ok=m.annotation_commands(public);assert ok and len(commands)==8
    values=payloads(commands);assert values[0]['annotation_cases_omitted']==25
    assert sum(len(x.get('failed_test_ids',[])) for x in values)==25
    assert all(len(x['failed_test_ids'])+x['annotation_ids_omitted']==25 for x in values[1:])
    assert sum(m.annotation_size(x) for x in commands)<=16*1024


def test_long_whitelisted_IDs_pack_whole_identifiers_under_byte_limit(publication,monkeypatch):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    ids=['tests/test_synthetic.py::test_'+('a'*210)+str(n) for n in range(25)]
    monkeypatch.setattr(m,'_allowed_tests',lambda:set(ids));public['cases'][0]['failure_diagnostics']['failed_test_ids']=ids
    commands,ok=m.annotation_commands(public);assert ok
    case=payloads(commands)[1];assert case['ids_truncated'] and case['annotation_ids_omitted']>0
    converted={x.removeprefix('tests/').replace('.py::','::') for x in ids}
    assert set(case['failed_test_ids'])<=converted and len(case['failed_test_ids'])+case['annotation_ids_omitted']==25
    assert all(m.annotation_size(x)<=2048 for x in commands)
    assert max(m.annotation_size(x) for x in commands)>1800


@pytest.mark.parametrize('change',['too_many_rows','negative_counts','bool_exit','bad_scope','missing_state','list_phase','invalid_diagnostic_count'])
def test_malformed_projected_data_never_partially_publishes(publication,change):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    if change=='too_many_rows':public['cases']*=33
    elif change=='negative_counts':public['cases'][0]['counts']['FAIL']=-1
    elif change=='bool_exit':public['cases'][0]['exit_code']=True
    elif change=='bad_scope':public['scope']=POISON
    elif change=='missing_state':public.pop('report_state')
    elif change=='list_phase':public['active_phase']=[POISON]
    else:public['cases'][0]['failure_diagnostics']['failed_cases']=POISON
    commands,ok=m.annotation_commands(public);assert not ok and len(commands)==1
    assert payloads(commands)[0]['state']=='ANNOTATIONS_UNAVAILABLE' and POISON not in ''.join(commands)


def test_message_percent_CR_LF_escaping_does_not_create_workflow_commands():
    m=module('publish_summary');value={'synthetic':'%0A\r\n::error::SYNTHETIC\u2028'}
    command=m.annotation_command(value)
    assert '\n' not in command and '\r' not in command and '\u2028' not in command and '%250A' in command
    assert payloads([command])==[value]


def test_unavailable_and_allowlist_failure_use_only_constant_notice(publication,monkeypatch):
    source,path,_=publication;m=module('publish_summary');public=m.read_summary(source)
    def fail():raise OSError(POISON)
    monkeypatch.setattr(m,'_allowed_tests',fail)
    commands,ok=m.annotation_commands(public);assert not ok and POISON not in ''.join(commands)
    path.unlink();commands,ok=m.annotation_commands(m.read_summary(source))
    assert not ok and payloads(commands)==[{'kind':'publication','state':'ANNOTATIONS_UNAVAILABLE'}]


@pytest.mark.parametrize('error',[OSError,RuntimeError])
def test_annotation_sink_failure_preserves_JSON_and_JobSummary(publication,monkeypatch,capsys,error):
    source,_,output=publication;m=module('publish_summary')
    def sink(value):raise error(POISON)
    monkeypatch.setattr(m,'write_annotations',sink)
    assert m.main(source)==1
    assert console_json(capsys.readouterr().out)['publication_state']=='SUMMARY_AVAILABLE'
    assert 'SUMMARY_AVAILABLE' in output.read_text(encoding='utf-8') and POISON not in output.read_text(encoding='utf-8')


def test_early_checkpoint_without_cases_still_exposes_current_phase(publication):
    source,_,_=publication;m=module('publish_summary');public=m.read_summary(source)
    public.update(report_state='IN_PROGRESS',active_phase='regression_run',cases=[])
    commands,ok=m.annotation_commands(public);assert ok and len(commands)==1
    header=payloads(commands)[0];assert header['active_phase']=='regression_run' and header['report_state']=='IN_PROGRESS'


def test_annotations_use_only_notices_and_leave_cleanup_order_unchanged():
    m=module('publish_summary');assert m.annotation_command({'kind':'publication'}).startswith('::notice ')
    text=(ROOT/'.github/workflows/windows-server-engineering.yml').read_text(encoding='utf-8')
    assert text.index('publish_summary.py')<text.index('Engineering.ps1 -Action Stop')
    assert 'contents: read' in text and 'checks: write' not in text and 'upload-artifact' not in text


def test_binary_sink_bypasses_Windows_CRLF_translation_at_exact_byte_boundary(monkeypatch):
    m=module('publish_summary');buffer=io.BytesIO();text=io.TextIOWrapper(buffer,encoding='cp1252',newline='\r\n')
    # This synthetic known command reaches the declared limit including LF.
    command=PREFIX+'x'*(2048-len(PREFIX.encode('utf-8'))-1)
    monkeypatch.setattr(m.sys,'stdout',text)
    m.write_annotations([command]*8)
    data=buffer.getvalue()
    assert len(data)==16384 and data.count(b'\n')==8 and b'\r' not in data
    assert all(len(line)+1==2048 for line in data.splitlines())


@pytest.mark.parametrize('mode',['short_write','write_error','flush_error'])
def test_binary_sink_failures_are_not_reported_as_delivery_success(mode):
    m=module('publish_summary')
    class Sink:
        def write(self,data):
            if mode=='write_error':raise OSError(POISON)
            return 0 if mode=='short_write' else len(data)
        def flush(self):
            if mode=='flush_error':raise OSError(POISON)
    with pytest.raises(OSError):m.write_annotations([m.annotation_command({'kind':'publication'})],Sink())


def test_real_CLI_annotation_bytes_have_exact_LF_without_console_normalization(publication):
    source,_,_=publication
    result=subprocess.run([sys.executable,str(ROOT/'scripts/windows_ci/publish_summary.py')],env=minimal_environment(os.environ,**source),capture_output=True,timeout=15)
    assert result.returncode==0 and result.stderr==b''
    start=result.stdout.index(PREFIX.encode('ascii'));batch=result.stdout[start:]
    assert b'\r' not in batch and batch.endswith(b'\n') and len(batch)<=16384
    assert all(len(line)+1<=2048 for line in batch.splitlines())
