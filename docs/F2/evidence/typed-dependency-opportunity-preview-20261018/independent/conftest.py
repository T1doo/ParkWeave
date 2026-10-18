"""Expose unchanged frozen original fixtures to private independent test path."""
from pathlib import Path
import importlib.util
import sys
original=Path(__file__).resolve().parent/'mirror/tests/conftest.py'
spec=importlib.util.spec_from_file_location('_independent_frozen_original_conftest',original)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
pg=module.pg
fixture=module.fixture
pytest_plugins=['owned_connection_diagnostics']
