"""Effective CLI path with public synthetic files only; no child service."""
import json
from parkweave import native_run_access_trial_plan as trial
from test_native_run_access_trial_plan import inputs


def test_valid_public_cli_returns_only_unapproved_plan(tmp_path, capsys):
    spec, snapshot, host = inputs()
    paths = []
    for name, value in [('spec',spec),('snapshot',snapshot),('host-plan',host)]:
        path = tmp_path/(name+'.json')
        path.write_text(json.dumps(value))
        paths.extend(['--'+name,str(path)])
    assert trial.main(paths) == 5
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'APPROVAL_REQUIRED'
    assert result['writer_argv'] is None
    assert result['writer_runtime'] == 'NOT_IMPLEMENTED'
    assert result['actual_run'] == 'NOT_RUN'
    assert all(result[key] is False for key in ('launch_authorized','installation_authorized','activation_enabled','production_connected'))
