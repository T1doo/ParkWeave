"""Independent pure probes. No actual trial, identity, ACL, PG, or cloud changes."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path('/workspace/ParkWeave')
BASE='80ac6c86edd447d31e5f046b25eb335c63923102'
SHA='4649970278e29b999a2a4f332ba7380f20795a3f'
OLD='USER_CONFIRMED_ONE_FREE_GITHUB_VM_2026-10-12T12:49:49Z'

def mod():
    spec=importlib.util.spec_from_file_location('independent_second_bootstrap',ROOT/'scripts/linux_trial/bootstrap.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def env(m):
    return dict(TRIAL_REPOSITORY='T1doo/ParkWeave',TRIAL_REF=m.SECOND_BRANCH,
        TRIAL_ENTRY=m.SECOND_ENTRY,TRIAL_EVENT='push',TRIAL_ATTEMPT='1',TRIAL_NUMBER='1',
        RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux')

@pytest.mark.parametrize('route',['missing-flag','wrong-flag','extra-arg','old-branch','old-entry','attempt-2','number-2','missing-runner'])
def test_actual_main_denies_before_filesystem(monkeypatch,capsys,route):
    m=mod();e=env(m);args=[SHA,'--second-once-20261013']
    if route=='missing-flag':args=[SHA]
    elif route=='wrong-flag':args=[SHA,'--second-once-20261012']
    elif route=='extra-arg':args.append('extra')
    elif route=='old-branch':e['TRIAL_REF']=m.BRANCH
    elif route=='old-entry':e['TRIAL_ENTRY']='FIRST_ONCE'
    elif route=='attempt-2':e['TRIAL_ATTEMPT']='2'
    elif route=='number-2':e['TRIAL_NUMBER']='2'
    elif route=='missing-runner':del e['RUNNER_ENVIRONMENT']
    with monkeypatch.context() as p:
        p.setattr(m.os,'environ',e);p.setattr(m.os,'geteuid',lambda:0)
        def forbidden(*a,**kw):raise AssertionError('PHYSICAL_OPERATION_REACHED')
        p.setattr(m.Path,'cwd',forbidden);p.setattr(m.Path,'mkdir',forbidden)
        p.setattr(m.subprocess,'check_output',forbidden);p.setattr(m.subprocess,'Popen',forbidden)
        assert m.main(args)==1
    output=capsys.readouterr();value=json.loads(output.out)
    assert output.err=='' and value['phase']=='PREFLIGHT' and value['error']=='OS_REFUSED'
    assert value['cleanup'] is True and list(value['cases'].values()).count('FAIL')==1
    assert list(value['cases'].values()).count('NOT_RUN')==16

def test_actual_main_routes_second_to_exact_checkout_before_creation(monkeypatch,capsys):
    m=mod();calls=[]
    with monkeypatch.context() as p:
        p.setattr(m.os,'environ',env(m));p.setattr(m.os,'geteuid',lambda:0)
        p.setattr(m.Path,'cwd',lambda:Path('/synthetic-checkout'))
        def read(args,**kw):calls.append((args,kw));return 'b'*40
        p.setattr(m.subprocess,'check_output',read)
        def forbidden(*a,**kw):raise AssertionError('PHYSICAL_OPERATION_REACHED')
        p.setattr(m.Path,'mkdir',forbidden);p.setattr(m.subprocess,'Popen',forbidden)
        assert m.main([SHA,'--second-once-20261013'])==1
    assert calls==[(['/usr/bin/git','rev-parse','HEAD'],{'cwd':Path('/synthetic-checkout'),'text':True})]
    value=json.loads(capsys.readouterr().out)
    assert value['phase']=='PREFLIGHT' and value['error']=='CHECK_FAILED'

@pytest.mark.parametrize('pair',['second-old','absent-new','unknown-new','none-old'])
def test_actual_controller_rejects_cross_pairs_before_actions(monkeypatch,capsys,pair):
    monkeypatch.syspath_prepend(str(ROOT))
    from scripts.linux_trial import controller as c
    m=mod();context=dict(root='/synthetic-never-created',source_sha=SHA,approval=m.SECOND_APPROVAL)
    if pair=='second-old':context.update(entry=m.SECOND_ENTRY,approval=OLD)
    elif pair=='unknown-new':context['entry']='UNKNOWN'
    elif pair=='none-old':context.update(entry=None,approval=OLD)
    obj=c.Controller(context);calls=[]
    monkeypatch.setattr(c.os,'geteuid',lambda:0)
    monkeypatch.setattr(c.signal,'signal',lambda *a:None)
    monkeypatch.setattr(c,'private_file',lambda *a,**kw:calls.append('private-error'))
    def forbidden():raise AssertionError('PHYSICAL_OPERATION_REACHED')
    for name in ('identities','pg_start','host_start','acceptance'):monkeypatch.setattr(obj,name,forbidden)
    def clean():calls.append('cleanup');obj.value['cleanup']=True;return True
    monkeypatch.setattr(obj,'cleanup',clean)
    assert obj.run()==1
    value=json.loads(capsys.readouterr().out)
    assert value['error']=='OS_REFUSED' and calls==['private-error','cleanup']

def test_exact_five_file_scope_and_unchanged_old_gate_worker_and_sql():
    changed=subprocess.check_output(['git','diff','--name-only',BASE+'..'+SHA],cwd=ROOT,text=True).splitlines()
    assert set(changed)=={'.github/workflows/restricted-linux-second-trial-once.yml','scripts/linux_trial/bootstrap.py','scripts/linux_trial/controller.py','scripts/windows_ci/diagnostic-test-ids.json','tests/test_restricted_linux_trial_contract.py'}
    old=subprocess.check_output(['git','show',BASE+':scripts/linux_trial/bootstrap.py'],cwd=ROOT,text=True)
    new=(ROOT/'scripts/linux_trial/bootstrap.py').read_text()
    def gate(text):return ast.dump(next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='approved_context'))
    assert gate(old)==gate(new)
    for path in ('scripts/linux_trial/worker.py','.github/workflows/restricted-linux-trial-once.yml'):
        assert subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)==(ROOT/path).read_bytes()
    assert not any(p.startswith('src/') for p in changed)

def test_new_workflow_is_exact_reviewed_old_structure_with_separate_entry():
    old=(ROOT/'.github/workflows/restricted-linux-trial-once.yml').read_text()
    expected=old.replace('Linux trial once','Linux second trial once').replace('restricted-linux-trial-once','restricted-linux-second-trial-once').replace('dev/f2-restricted-linux-trial-20261012','dev/f2-restricted-linux-second-trial-20261013')
    expected=expected.replace('          TRIAL_NUMBER: ${{ github.run_number }}\n','          TRIAL_NUMBER: ${{ github.run_number }}\n          TRIAL_ENTRY: SECOND_ONCE_20261013\n')
    expected=expected.replace('RUNNER_OS="$RUNNER_OS" \\', 'RUNNER_OS="$RUNNER_OS" TRIAL_ENTRY="$TRIAL_ENTRY" \\')
    expected=expected.replace('bootstrap.py "$TRIAL_SOURCE_SHA"','bootstrap.py "$TRIAL_SOURCE_SHA" --second-once-20261013')
    actual=(ROOT/'.github/workflows/restricted-linux-second-trial-once.yml').read_text()
    assert actual==expected
    assert actual.count('    runs-on: ubuntu-24.04')==1
    assert actual.count('    timeout-minutes: 25')==1
    for gate in ("github.repository == 'T1doo/ParkWeave'","github.event_name == 'push'",'github.event.repository.private == false','github.run_attempt == 1 && github.run_number == 1'):
        assert gate in actual
