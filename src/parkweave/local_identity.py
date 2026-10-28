"""Password sealed local identities. Tokens are never persisted in plaintext.

Each role has an independent scrypt key and authenticated ciphertext. The
installation's physical directory and database identity are authenticated data.
This protects stored bearer material; it is not a same-user OS sandbox.
"""
import base64
import hashlib
import json
import os
import secrets
import stat

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .store import Denied

ROLES = ('enterprise', 'specialist')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def password_bytes(value):
    if type(value) is not str or not 12 <= len(value) <= 256:
        raise Denied('role password must contain 12 to 256 characters')
    return value.encode('utf-8')


def key(password, salt):
    return hashlib.scrypt(password_bytes(password), salt=salt, n=32768, r=8, p=1,
                          maxmem=64 * 1024 * 1024, dklen=32)


class LocalSessionVault:
    """Exclusive creation and strictly read-only unlock; no reset or grant repair."""
    filename = 'local-identities.sealed'

    def __init__(self, passwords):
        if type(passwords) is not dict or set(passwords) != set(ROLES):
            raise Denied('two independently supplied role passwords required')
        for value in passwords.values():
            password_bytes(value)
        if passwords['enterprise'] == passwords['specialist']:
            raise Denied('distinct enterprise and specialist passwords required')
        self._passwords = dict(passwords)
        self._tokens = None

    def generate(self):
        if self._tokens is not None:
            raise Denied('one identity creation attempt per installation')
        self._tokens = {role: secrets.token_urlsafe(48) for role in ROLES}
        return dict(self._tokens)

    @staticmethod
    def binding(path, marker):
        info = path.stat(follow_symlinks=False)
        return dict(schema='parkweave-local-identities/1', directory=[info.st_dev, info.st_ino],
                    database=[marker['system_identifier'], marker['database_oid']], ids=marker['ids'])

    def publish(self, path, marker):
        if self._tokens is None or self._passwords is None:
            raise Denied('new private identity material required')
        binding = self.binding(path, marker)
        rows = {}
        try:
            for role in ROLES:
                salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
                aad = canonical(dict(binding=binding, role=role))
                cipher = AESGCM(key(self._passwords[role], salt)).encrypt(
                    nonce, self._tokens[role].encode('ascii'), aad)
                rows[role] = [base64.b64encode(raw).decode('ascii') for raw in (salt, nonce, cipher)]
            fd = os.open(path / self.filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(dict(binding=binding, roles=rows)))
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            self._passwords = self._tokens = None

    @classmethod
    def unlock(cls, path, marker, role, password):
        if role not in ROLES:
            raise Denied('local identity unavailable')
        fd = os.open(path / cls.filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077 or info.st_nlink != 1 or not 0 < info.st_size <= 16384):
                raise Denied('private owned identity ciphertext required')
            raw = os.read(fd, 16385)
            if len(raw) != info.st_size:
                raise Denied('identity ciphertext changed')
        finally:
            os.close(fd)
        try:
            value = json.loads(raw)
            binding = cls.binding(path, marker)
            if set(value) != {'binding', 'roles'} or value['binding'] != binding or set(value['roles']) != set(ROLES):
                raise ValueError()
            salt, nonce, cipher = [base64.b64decode(x, validate=True) for x in value['roles'][role]]
            if len(salt) != 16 or len(nonce) != 12 or not 16 < len(cipher) <= 528:
                raise ValueError()
            bearer = AESGCM(key(password, salt)).decrypt(nonce, cipher,
                canonical(dict(binding=binding, role=role))).decode('ascii')
            if not 32 <= len(bearer) <= 512:
                raise ValueError()
            return bearer
        except Exception:
            raise Denied('local identity unavailable') from None
