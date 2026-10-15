"""Explicit original fixtures and private-value capture for the seam probes."""
from pathlib import Path
import json
import os
import pytest
from original_fixtures import fixture, pg

HERE = Path(__file__).resolve().parent


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    yield
    values = set()
    for name in ['fixture', 'preparation_fixture', 'receipt_fixture', 'link_fixture', 'http_f']:
        data = item.funcargs.get(name)
        if isinstance(data, tuple) and len(data) > 2 and isinstance(data[2], dict):
            values.update(v for v in data[2].values() if isinstance(v, str) and len(v) == 43)
    if values:
        target = HERE / ('redaction-' + os.environ['REVIEW_SEAM_WINDOW'] + '.private.json')
        old = set(json.loads(target.read_text())) if target.exists() else set()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(sorted(old | values), stream)
            stream.write('\n')

