"""Pure CI contract tests only; never start trial processes/PG or modify identities."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module():
    spec=importlib.util.spec_from_file_location('pwci_bootstrap_contract',ROOT/'scripts/linux_trial/bootstrap.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def clean(m):
    return dict(source_sha='a'*40,phase='PREFLIGHT',error='NONE',cases={c:'NOT_RUN' for c in m.CASES},cleanup=True)


@pytest.mark.parametrize('field',['source_sha','phase','error','cases','extra'])
def test_ci_public_output_never_serializes_private_poison(field):
    m=module();value=clean(m);poison='SYNTHETIC_PRIVATE_PASSWORD_KEY_PATH_TOKEN'
    if field=='cases':value[field][m.CASES[0]]=poison
    else:value[field]=poison
    with pytest.raises(ValueError) as error:m.public_summary(value)
    assert poison not in str(error.value)


def test_ci_public_projection_has_fixed_status_keys_and_zero_paid_resources():
    m=module();value=clean(m);output=m.public_summary(value)
    assert output['paid_services']==output['artifact_uploads']==output['cache_uploads']==0
    assert output['production_deployment'] is False
    assert len(output['cases'])==17 and set(output['cases'].values())=={'NOT_RUN'}


@pytest.mark.parametrize('change',[dict(TRIAL_REPOSITORY='other/repo'),dict(TRIAL_REF='refs/heads/main'),
    dict(TRIAL_EVENT='pull_request'),dict(TRIAL_ATTEMPT='2'),dict(TRIAL_NUMBER='2'),dict(RUNNER_ENVIRONMENT='self-hosted')])
def test_ci_context_refuses_wrong_or_repeated_scope_before_bootstrap(change):
    m=module();env=dict(TRIAL_REPOSITORY='T1doo/ParkWeave',TRIAL_REF=m.BRANCH,TRIAL_EVENT='push',
        TRIAL_ATTEMPT='1',TRIAL_NUMBER='1',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux')
    assert m.approved_context(env,0,'a'*40)
    env.update(change);assert not m.approved_context(env,0,'a'*40)
    assert not m.approved_context(env,1000,'a'*40)


def test_ci_workflow_uses_single_free_standard_job_without_upload_or_dispatch():
    text=(ROOT/'.github/workflows/restricted-linux-trial-once.yml').read_text()
    assert 'runs-on: ubuntu-24.04' in text and 'timeout-minutes: 25' in text
    assert 'github.run_attempt == 1 && github.run_number == 1' in text
    assert 'github.event.repository.private == false' in text and 'persist-credentials: false' in text
    for denied in ('workflow_dispatch:','pull_request:','upload-artifact','actions/cache','actions/setup-python','self-hosted','matrix:','secrets.'):
        assert denied not in text


def test_ci_private_trial_inputs_do_not_use_credentials_in_command_or_environment():
    controller=(ROOT/'scripts/linux_trial/controller.py').read_text();worker=(ROOT/'scripts/linux_trial/worker.py').read_text()
    assert 'pass_fds=(fd,)' in controller and "env={'LANG':'C.UTF-8'}" in controller
    assert 'pwfile=' in controller and 'passwords[\'pwci_owner\']' not in controller.split('subprocess.Popen([str(binaries')[1].split('finally:out.close()')[0]
    assert 'host.bind_api' in worker and 'ROOT_SEALED_INPUT_REQUIRED' in worker
    assert "if set(config)!={'api_uid','api_gid','ipc_gid','app_dsn','tokens','binding_path','binding_sha256','writer_private_path'}" in worker
