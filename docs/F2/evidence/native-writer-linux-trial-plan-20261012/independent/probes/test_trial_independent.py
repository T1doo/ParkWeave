"""Pure synthetic declared inputs. No fixture, authority or launcher use."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
import pytest
from parkweave import native_run_access_trial_plan as trial
from test_native_run_access_trial_plan import inputs


@pytest.mark.parametrize('tail',['/../outside','/sockets/../../outside'])
def test_declared_database_socket_cannot_escape_trial_root(tail):
    spec, catalog, host = inputs()
    target = host['trial_root'] + tail
    spec['policy']['database_host'] = target
    catalog['database']['host'] = target
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'REFUSED', result


def test_credential_like_actor_cannot_be_echoed_as_public_scope():
    spec, catalog, host = inputs()
    value = 'Bearer SYNTHETIC_PRIVATE_SENTINEL_NOT_A_REAL_CREDENTIAL'
    spec['policy']['owner_id'] = value
    spec['policy']['source']['owner_id'] = value
    result = trial.prepare(spec, catalog, host)
    assert value not in json.dumps(result), result
    assert result['status'] == 'REFUSED'


@pytest.mark.parametrize('location',['spec','host'])
def test_unknown_actor_setter_is_not_a_public_input(location):
    spec, catalog, host = inputs()
    (spec if location == 'spec' else host)['actor_id'] = 'SYNTHETIC_UNTRUSTED_ACTOR'
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'REFUSED'
    assert not result['launch_authorized']


def test_reference_argv_cannot_be_substituted_for_missing_restricted_runtime():
    spec, catalog, host = inputs()
    host['writer_argv'] = ['python', '-m', 'parkweave.native_run_access_writer', '--reference-bootstrap', 'SYNTHETIC_PRIVATE_REFERENCE']
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'REFUSED' and result['writer_argv'] is None
    assert 'SYNTHETIC_PRIVATE_REFERENCE' not in json.dumps(result)


def test_scope_digest_is_declared_and_changes_without_granting_authority():
    spec, catalog, host = inputs()
    before = deepcopy((spec, catalog, host))
    first = trial.prepare(spec, catalog, host)
    assert (spec, catalog, host) == before
    spec['policy']['source']['run_id'] = str(uuid4())
    second = trial.prepare(spec, catalog, host)
    assert first['plan_digest'] != second['plan_digest']
    assert second['declared_case_scope']['source']['run_id'] == spec['policy']['source']['run_id']
    assert second['writer_argv'] is None and second['writer_runtime'] == 'NOT_IMPLEMENTED'
    assert all(second[key] is False for key in ('launch_authorized','installation_authorized','activation_enabled','production_connected'))


def test_future_interval_is_not_started_or_automatically_adjusted():
    spec, catalog, host = inputs()
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    spec['policy'].update(valid_from=start.isoformat(),valid_until=(start+timedelta(minutes=30)).isoformat())
    before = deepcopy(spec)
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'REFUSED' and spec == before
    assert result['actual_run'] == 'NOT_RUN'
