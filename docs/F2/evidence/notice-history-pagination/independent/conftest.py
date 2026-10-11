import importlib.util
spec=importlib.util.spec_from_file_location('notice_independent_owned_fixture','/workspace/ParkWeave/tests/conftest.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
pg=module.pg
fixture=module.fixture
drop_owned_fixture_database=module.drop_owned_fixture_database
