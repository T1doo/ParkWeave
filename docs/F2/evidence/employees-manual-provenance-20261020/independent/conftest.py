import importlib.util
from pathlib import Path
pytest_plugins=['owned_connection_diagnostics']
spec=importlib.util.spec_from_file_location('manual_review_repo_fixture_support','/workspace/ParkWeave/tests/conftest.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
pg=mod.pg
fixture=mod.fixture
import test_employees_fact_provenance_independent as fp
fp.OUT=Path('/workspace/scratch/employees-manual-review/frozen/fixture-artifacts')
fp.chain.OUT=Path('/workspace/scratch/employees-manual-review/frozen/chain-artifacts')
fp.batch.OUT=Path('/workspace/scratch/employees-manual-review/frozen/batch-artifacts')
# This helper only writes a token-redaction file; no raw request logs are used here.
fp.private_tokens=lambda tokens:None
facts_case=fp.facts_case
fresh_chain=fp.fresh_chain
link_fixture=fp.link_fixture
receipt_fixture=fp.receipt_fixture
preparation_fixture=fp.preparation_fixture
