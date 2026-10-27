"""Fresh PG16 session supplier, bounded to one retained Popen and new directory."""
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time

import psycopg
from psycopg.conninfo import make_conninfo, conninfo_to_dict

from parkweave.case_fact_clarifications import capture_fixture_cluster


class OwnedPG:
    def __init__(self, root):
        self.root = root; self.cluster = root/'cluster'; self.process = None
        self.created = False; self.init_started = False; self.init_complete = False
        self.dsn = None; self._case_fact_fixture_cluster = None

    def start(self):
        root = self.root
        if (os.geteuid() == 0 or root.is_symlink() or root.parent != Path('/tmp') or
                not root.name.startswith('parkweave-case-pg-') or root.stat().st_uid != os.geteuid() or
                stat.S_IMODE(root.stat().st_mode) != 0o700):
            raise PermissionError('NEW_PRIVATE_NONROOT_DIRECTORY_REQUIRED')
        self.cluster.mkdir(mode=0o700); self.created = True
        data = self.cluster/'data'; socket = self.cluster/'socket'; socket.mkdir(mode=0o700)
        binary = Path('/usr/lib/postgresql/16/bin')
        for name in ('initdb', 'postgres'):
            s = (binary/name).lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
                raise PermissionError('INSTALLED_REGULAR_PG16_BINARY_REQUIRED')
        with (root/'initdb.log').open('wb') as log:
            self.init_started = True
            subprocess.run([str(binary/'initdb'), '-D', str(data), '--username=pwci_owner',
                '--auth-local=trust', '--auth-host=reject', '--no-locale', '--encoding=UTF8'],
                env={'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin'}, stdout=log, stderr=log, timeout=60, check=True)
            self.init_complete = True
        if (data/'PG_VERSION').read_text().strip() != '16':raise AssertionError('PG16_REQUIRED')
        logpath = root/'postgres.log'
        with logpath.open('wb') as log:
            self.process = subprocess.Popen([str(binary/'postgres'), '-D', str(data), '-k', str(socket), '-p', '55441',
                '-c', 'listen_addresses=', '-c', 'unix_socket_permissions=0700', '-c', 'log_statement=none',
                '-c', 'log_min_error_statement=panic', '-c', 'log_error_verbosity=terse'],
                env={'LANG': 'C.UTF-8'}, stdout=log, stderr=log)
        until = time.monotonic()+10
        while b'database system is ready to accept connections' not in logpath.read_bytes()[:1048576]:
            if self.process.poll() is not None or time.monotonic() >= until:raise TimeoutError('OWNED_PG_NOT_READY')
            time.sleep(.05)
        if int((data/'postmaster.pid').read_text().splitlines()[0]) != self.process.pid:
            raise AssertionError('OWNED_POSTMASTER_PID_REQUIRED')
        passfile = root/'empty.pgpass'
        fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.close(fd)
        self.dsn = make_conninfo(host=str(socket), port=55441, dbname='postgres', user='pwci_owner',
            passfile=str(passfile), sslmode='disable', gssencmode='disable', connect_timeout=2,
            options='-c statement_timeout=30000 -c lock_timeout=10000')
        self._case_fact_fixture_cluster = capture_fixture_cluster(self.dsn, data)
        with psycopg.connect(self.dsn, autocommit=True) as c:
            for name in ('parkweave_app', 'pwci_writer'):
                c.execute(psycopg.sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(psycopg.sql.Identifier(name)))

    def get_uri(self):
        if self.dsn is None or self._case_fact_fixture_cluster is None:
            raise PermissionError('ORIGINAL_CLUSTER_PROOF_REQUIRED')
        return self.dsn

    def validate_connection(self, conninfo, kwargs):
        """No fallback environment/service/password or connection outside this cluster."""
        d = conninfo_to_dict(conninfo)
        d.update({k: str(v) for k, v in kwargs.items() if k not in
            ('autocommit', 'row_factory', 'cursor_factory', 'context', 'prepare_threshold')})
        exact = dict(host=str(self.cluster/'socket'), port='55441', passfile=str(self.root/'empty.pgpass'),
            sslmode='disable', gssencmode='disable')
        if (any(d.get(k) != v for k, v in exact.items()) or d.get('user') not in ('pwci_owner', 'parkweave_app', 'pwci_writer') or
                not re.fullmatch(r'postgres|fixture_[a-f0-9]{32}', d.get('dbname', '')) or
                set(d) - set(exact) - {'dbname', 'user', 'options', 'connect_timeout'}):
            raise PermissionError('ONLY_OWNED_NEW_CLUSTER_CONNECTIONS_ALLOWED')

    def fixtures_removed(self):
        with psycopg.connect(self.get_uri(), autocommit=True) as c:
            names = {r[0] for r in c.execute('SELECT datname FROM pg_database').fetchall()}
        return names == {'postgres', 'template0', 'template1'}

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
                raise RuntimeError('FORCED_STOP_NOT_CLEANUP_PASS')
        if self.process is not None and (type(self.process.poll()) is not int or self.process.poll() != 0):
            raise RuntimeError('NORMAL_OWNED_PG_EXIT_REQUIRED')
        if not self.created or (self.init_started and not self.init_complete):return 'UNKNOWN'
        if self.cluster.is_symlink() or self.cluster.stat().st_uid != os.geteuid():
            raise PermissionError('OWNED_CLUSTER_REMOVAL_REQUIRED')
        shutil.rmtree(self.cluster)
        return 'PASS'
