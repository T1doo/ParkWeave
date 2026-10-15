"""Expose the original owned PostgreSQL fixture to private runtime tests."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('at24_original_fixtures', ROOT / 'tests/conftest.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
pg = module.pg
fixture = module.fixture
