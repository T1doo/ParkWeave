import importlib.util
from pathlib import Path
pytest_plugins=['owned_connection_diagnostics']
spec=importlib.util.spec_from_file_location('handoff_repo_fixture_support',Path('/workspace/ParkWeave/tests/conftest.py'))
fixture_support=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_support)
pg=fixture_support.pg
fixture=fixture_support.fixture
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_ordinary_case_steps import ordinary
