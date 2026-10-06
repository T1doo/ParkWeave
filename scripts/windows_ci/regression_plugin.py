"""Pytest-only hooks; publisher and acceptance parent use stdlib-only helpers."""
import pytest
from .regression_progress import write


def pytest_addoption(parser):parser.addoption('--parkweave-progress',default=None)


def mark(config,phase,nodeid=None):write(config.getoption('--parkweave-progress'),phase,nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):mark(session.config,'pytest_collect')


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):mark(item.config,'pytest_setup',item.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):mark(item.config,'pytest_call',item.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item):mark(item.config,'pytest_teardown',item.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):mark(session.config,'pytest_finish')
