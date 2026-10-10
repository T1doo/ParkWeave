"""Only GET delegation to a live original fixture issuer, never proof transport.

Linux synthetic opt-in. The issuer retains the original P4 object and performs
its unchanged read/authorization path for every request. API clients get neither
its bridge/proof nor any write operation. Issuer restart is deliberately refused.
"""
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import tempfile
import threading
from uuid import UUID

from . import receipt_execution_preview as p4, isolated_execution_preview as ep
from . import isolated_local_execution as local
from .isolated_run_access import IsolatedRunAccessBridge
from .store import Denied, Conflict

SCOPE = 'ISOLATED_P4_LIVE_ISSUER_HISTORY_GET_V1'
REQUEST_LIMIT = 4096
RESPONSE_LIMIT = 2 * 1024 * 1024
TIMEOUT = 3
FIELDS = {'version', 'operation', 'preparation', 'key', 'token', 'binding'}
CONTRACT = ep._sha(dict(scope=SCOPE, version=1, operation='READ', fields=sorted(FIELDS),
    request_limit=REQUEST_LIMIT, response_limit=RESPONSE_LIMIT, socket_timeout=TIMEOUT,
    backlog=8, proof_scope='ORIGINAL_LIVE_ISSUER_ONLY', p4=p4.CONTRACT))


def process_generation(pid):
    """Actual Linux process start tick; a reused PID cannot replace the issuer."""
    if os.name != 'posix' or not hasattr(socket, 'SO_PEERCRED') or type(pid) is not int or pid < 1:
        raise Denied('validated local history transport required')
    try:
        data = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        if data[0] == 'Z':
            raise ValueError()
        return data[19]
    except (OSError, IndexError, ValueError):
        raise Denied('original live history issuer required') from None


def _directory(path):
    if os.name != 'posix' or not hasattr(socket, 'SO_PEERCRED') or not hasattr(os, 'geteuid'):
        raise Denied('validated local history transport required')
    root = Path(tempfile.gettempdir()).resolve()
    if (not path.is_absolute() or len(os.fsencode(path)) > 100 or
            not path.parent.is_relative_to(root) or path.parent == root):
        raise Denied('private temporary history socket required')
    for parent in (path.parent, *path.parent.parents):
        if parent.is_symlink():
            raise Denied('history socket directory symlink refused')
    s = path.parent.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o700:
        raise Denied('owned private history socket directory required')
    return s.st_dev, s.st_ino


def _socket_identity(path):
    if path.is_symlink():
        raise Denied('history socket symlink refused')
    s = path.stat()
    if not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o600:
        raise Denied('owned private history socket required')
    return s.st_dev, s.st_ino


def _peer(sock):
    return struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))


def _exact(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise ValueError('incomplete history frame')
        data.extend(part)
    return bytes(data)


def _receive(sock, limit):
    count = struct.unpack('!I', _exact(sock, 4))[0]
    if not 1 <= count <= limit:
        raise ValueError('bounded history frame required')
    return json.loads(_exact(sock, count))


def _send(sock, data, limit):
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    if len(raw) > limit:
        raise ValueError('bounded history reply required')
    sock.sendall(struct.pack('!I', len(raw)) + raw)


def _key(key):
    if key is not None and (type(key) is not str or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', key)):
        raise Denied('bounded opaque history key required')
    return key


class ReceiptHistoryAuthority:
    def __init__(self, store, preview, socket_path, *, enabled_for_isolated_tests=False):
        if enabled_for_isolated_tests is not True or type(preview) is not p4.ReceiptExecutionPreview:
            raise Denied('explicit original P4 history authority required')
        self.pid = os.getpid()
        self.generation = process_generation(self.pid)
        self.store, self.preview, self.path = store, preview, Path(socket_path)
        self.directory_identity = _directory(self.path)
        if self.path.exists() or self.path.is_symlink():
            raise Denied('existing history socket cannot be replaced')
        if store.mode != 'LOCAL' or getattr(store, preview.attachment_attribute, None) is not preview:
            raise Denied('original attached P4 store required')
        self._original()
        self.binding = dict(scope=SCOPE, pid=self.pid, generation=self.generation,
            namespace=preview.namespace, database=preview.database_identity, contract=p4.CONTRACT, history_contract=CONTRACT)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.thread = None
        self.stopped = threading.Event()
        try:
            self.listener.bind(str(self.path))
            self.path.chmod(0o600)
            self.socket_identity = _socket_identity(self.path)
            self.listener.listen(8)
            self.listener.settimeout(.2)
            self.thread = threading.Thread(target=self._serve, name='p4-history-get-authority', daemon=True)
            self.thread.start()
        except BaseException:
            self.listener.close()
            if hasattr(self, 'socket_identity') and self.path.exists() and _socket_identity(self.path) == self.socket_identity:
                self.path.unlink()
            raise

    def _original(self):
        bridge = getattr(self.store, '_isolated_run_access', None)
        adapter = local.provider(self.store)
        if type(bridge) is not IsolatedRunAccessBridge or adapter is None or adapter.bridge is not bridge:
            raise Denied('original issued bridge and local adapter required')
        bridge._issued_proof()
        with bridge.owner.connect() as c:
            bridge._proof(c)

    def _reply(self, request):
        if (type(request) is not dict or set(request) != FIELDS or type(request['version']) is not int or
                request['version'] != 1 or request['operation'] != 'READ' or request['binding'] != self.binding or
                type(request['token']) is not str or not 1 <= len(request['token']) <= 1024 or
                type(request['preparation']) is not str):
            raise Denied('closed read-only history request required')
        id = UUID(request['preparation'])
        key = _key(request['key'])
        if (os.getpid() != self.pid or process_generation(self.pid) != self.generation or
                _directory(self.path) != self.directory_identity or _socket_identity(self.path) != self.socket_identity):
            raise Denied('original live history authority unavailable')
        self._original()
        # Every call reuses the original full live qualification + document proof
        # path; there is no cached authorization or independent READ bypass.
        view = self.preview.read(self.store, request['token'], id, key)
        return dict(status=200, binding=self.binding, view=view)

    def _serve(self):
        while not self.stopped.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(TIMEOUT)
                try:
                    if _peer(conn)[1] != os.geteuid():
                        raise Denied('owned local history peer required')
                    answer = self._reply(_receive(conn, REQUEST_LIMIT))
                except Denied:
                    answer = dict(status=403)
                except Conflict:
                    answer = dict(status=409)
                except (ValueError, TypeError, KeyError):
                    answer = dict(status=403)
                except Exception:
                    answer = dict(status=503)
                try:
                    _send(conn, answer, RESPONSE_LIMIT)
                except (OSError, ValueError):
                    pass  # No request, token, proof, or exception text is logged.

    def close(self):
        self.stopped.set()
        self.listener.close()
        if self.thread is not None:
            self.thread.join(TIMEOUT + 1)
            if self.thread.is_alive():
                raise ep.Unavailable('owned history authority stop unconfirmed')
        if self.path.exists() and _socket_identity(self.path) == self.socket_identity:
            self.path.unlink()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ReceiptHistoryClient:
    def __init__(self, store, socket_path, *, authority_pid, authority_generation, namespace,
                 enabled_for_isolated_tests=False):
        if enabled_for_isolated_tests is not True or store.mode != 'LOCAL':
            raise Denied('explicit isolated read-only history client required')
        self.path = Path(socket_path)
        self.directory_identity = _directory(self.path)
        self.socket_identity = _socket_identity(self.path)
        if type(authority_generation) is not str or process_generation(authority_pid) != authority_generation:
            raise Denied('original history issuer generation required')
        UUID(namespace)
        self.binding = dict(scope=SCOPE, pid=authority_pid, generation=authority_generation,
            namespace=namespace, database=ep._identity(store), contract=p4.CONTRACT, history_contract=CONTRACT)
        self.store = store

    def attach_store(self, store):
        if store is not self.store:
            raise Denied('original history client Store required')
        store._isolated_receipt_history = self
        return store

    def read(self, store, token, preparation_id, key=None):
        if store is not self.store or getattr(store, '_isolated_receipt_history', None) is not self:
            raise Denied('attached read-only history client required')
        try:
            generation = process_generation(self.binding['pid'])
        except Denied:
            raise ep.Unavailable('original history authority unavailable') from None
        if generation != self.binding['generation']:
            raise Denied('original history authority generation changed')
        if (_directory(self.path) != self.directory_identity or
                _socket_identity(self.path) != self.socket_identity or ep._identity(store) != self.binding['database']):
            raise Denied('original history transport identity changed')
        request = dict(version=1, operation='READ', preparation=str(UUID(str(preparation_id))),
                       key=_key(key), token=token, binding=self.binding)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(TIMEOUT)
                conn.connect(str(self.path))
                pid, uid, _ = _peer(conn)
                if (pid, uid) != (self.binding['pid'], os.geteuid()) or _socket_identity(self.path) != self.socket_identity:
                    raise Denied('original history authority peer required')
                _send(conn, request, REQUEST_LIMIT)
                answer = _receive(conn, RESPONSE_LIMIT)
            if type(answer) is not dict or type(answer.get('status')) is not int:
                raise ValueError()
            if answer['status'] == 403:
                raise Denied('current original P4 history qualification required')
            if answer['status'] == 409:
                raise Conflict('original P4 history proof or sources unavailable')
            if answer['status'] != 200:
                raise ep.Unavailable('original history authority unavailable')
            view = answer['view']
            if (set(answer) != {'status', 'binding', 'view'} or answer['binding'] != self.binding or
                    type(view) is not dict or view.get('scope') != p4.SCOPE or
                    view.get('namespace') != self.binding['namespace'] or
                    view.get('preparation_id') != request['preparation'] or view.get('formal_writes') != 0):
                raise ValueError()
            return {**view, 'history_transport': SCOPE, 'read_only': True}
        except (OSError, ValueError, TypeError, KeyError):
            raise ep.Unavailable('read-only history transport unavailable') from None
