"""Additional strict snapshot completeness check; no database operations."""
from parkweave import native_run_access_preflight as preflight
from test_native_run_access_preflight import synthetic_catalog, synthetic_spec


def test_missing_excess_dml_evidence_is_unknown_not_empty():
    catalog = synthetic_catalog()
    del catalog['unneeded_writer_permissions']
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'REFUSED', report
    assert not report['installation_authorized']
    assert not report['activation_enabled']
    assert not report['production_connected']
