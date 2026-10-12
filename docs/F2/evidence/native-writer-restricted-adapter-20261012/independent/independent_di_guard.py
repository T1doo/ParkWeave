"""Global prohibition of real privileged/runtime side effects for pure DI tests."""
import os
import socket
import subprocess
import psycopg
import pytest


@pytest.fixture(autouse=True)
def independent_no_real_actions(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('independent DI window forbids real PG/service/socket/permission/private-FD actions')
    for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(subprocess,'Popen'),
        (socket.socket,'bind'),(socket.socket,'connect'),(os,'chmod'),(os,'chown'),
        (os,'fchmod'),(os,'fchown'),(os,'umask'),(os,'memfd_create'),(os,'setuid'),
        (os,'setgid'),(os,'setgroups')]:
        monkeypatch.setattr(obj,name,forbidden)
