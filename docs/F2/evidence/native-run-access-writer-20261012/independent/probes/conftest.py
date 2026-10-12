"""Original, unchanged owned-fixture lifecycle in a distinct pytest process."""
import importlib.util
from pathlib import Path

source=Path('/workspace/ParkWeave/tests/conftest.py')
spec=importlib.util.spec_from_file_location('_independent_writer_fixture_original',source)
original=importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
pg=original.pg
fixture=original.fixture

