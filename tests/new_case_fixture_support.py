"""Fresh ordinary-schema fixture for original HTML cold entry after cancellation."""
import pytest
from uuid import uuid4
from parkweave.api import create_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from cancel33_fixture_support import cancel33_case
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_service_selection_candidates import planner
from test_schema33_before_receipt_cancellation import cancel_body
from test_case_cancellation_before_receipt import post as cancel_case
from test_resource_bundles import states
from service_release_acceptance_support import case_history


@pytest.fixture
def new_case_entry(cancel33_case, capability_resource_catalog, tmp_path, request):
    x, a = cancel33_case, capability_resource_catalog
    f = x['f']
    assert a['f'] is f
    old_key = None
    cancelled_by_fixture = getattr(request, 'param', True)
    assert type(cancelled_by_fixture) is bool
    if cancelled_by_fixture:
        old_key = uuid4().hex
        result = cancel_case(f, x['p'], cancel_body(x), old_key)
        assert result.status_code == 200, result.text
    original = case_history(f[1], x['p']['preparation_id'])
    assert (original['cases'][0]['state'] == 'CANCELLED') is cancelled_by_fixture
    assert not original['service_step_receipts']
    assert states(f, x['holds']) == ['CONFIRMED'] * len(x['holds'])
    facade = ParkInstanceConsumer(a['catalog'],
        ConsumerRepository(tmp_path / 'independent-new-case-entry.consumer.candidate.sqlite3'),
        enabled_for_isolated_tests=True)
    selection_calls = []
    offline_planner = planner(selection_calls, mode='all')
    app = create_app(f[0], capability_catalog=a['catalog'], instance_consumer=facade,
        selection_planner=offline_planner)
    return dict(x=x, a=a, f=f, facade=facade, app=app, old_key=old_key,
        original=original, selection_calls=selection_calls)
