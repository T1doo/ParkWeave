"""Password-sealed bridge to the original six native identities.

No login bearer/password is placed in argv, environment or plaintext files. The API
child receives bounded ciphertext, then validates the decrypted original token
against current database permissions. This module grants no native acceptance.
"""
import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import warnings

from parkweave.store import Denied
from . import credential_envelope as e
from .local_preparation_identity import ENTERPRISES, REVIEWERS, PreparationIdentities

ENVIRONMENT = 'PARKWEAVE_NATIVE_LOGIN'
SCHEMA = 'parkweave-native-password-login/1'
MAX_CONFIG = 14000
ACCOUNTS = ENTERPRISES + REVIEWERS


def need(ok):
    if not ok: raise Denied('protected local login unavailable')


def actor_for(account):
    need(account in ACCOUNTS)
    suffix = account[-1]
    park = {'a':'park-a', 'b':'park-a', 'c':'park-b'}[suffix]
    return dict(id=account, park_id=park, org_id='org-'+suffix,
                role='enterprise_operator' if account in ENTERPRISES else 'park_specialist')


def password_bytes(password):
    need(type(password) is str and 12 <= len(password) <= 256)
    return password.encode('utf-8')


def entropy(password, salt, installation, account):
    need(type(salt) is bytes and len(salt) == 32)
    key = hashlib.scrypt(password_bytes(password), salt=salt, n=32768, r=8, p=1,
                         maxmem=64*1024*1024, dklen=32)
    return hmac.digest(key, e.canonical(dict(schema=SCHEMA, installation=installation,
                                           actor=actor_for(account))), 'sha256')


def parse_config(raw):
    need(type(raw) is str and 0 < len(raw) <= MAX_CONFIG)
    value = json.loads(raw, object_pairs_hook=e.pairs)
    e.exact(value, ('schema', 'installation', 'port', 'accounts'))
    need(value['schema'] == SCHEMA and re.fullmatch('[0-9a-f]{64}', value['installation']) and
         type(value['port']) is int and 1 <= value['port'] <= 65535 and set(value['accounts']) == set(ACCOUNTS))
    for account, row in value['accounts'].items():
        e.exact(row, ('actor', 'token_sha256', 'salt', 'ciphertext'))
        need(row['actor'] == actor_for(account))
        e.digest(row['token_sha256'])
        need(type(row['salt']) is str and re.fullmatch('[0-9a-f]{64}', row['salt']))
        need(type(row['ciphertext']) is str and 0 < len(row['ciphertext']) <= 4096)
        need(0 < len(base64.b64decode(row['ciphertext'], validate=True)) <= 3072)
    return value


class NativeLoginEnrollment:
    """Future installation input only; constructor neither generates nor stores tokens."""
    def __init__(self, passwords):
        need(type(passwords) is dict and set(passwords) == set(ACCOUNTS))
        for value in passwords.values(): password_bytes(value)
        need(len(set(passwords.values())) == len(ACCOUNTS))
        self._passwords = dict(passwords); self._used = False

    def __repr__(self): return '<NativeLoginEnrollment private>'
    def __reduce__(self): raise TypeError('LOGIN_INPUT_NOT_SERIALIZABLE')

    def seal(self, store, identities, installation, port):
        from .native_secret_store_candidate import _NativeFixedSecretStore
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()
        need(type(store) is _NativeFixedSecretStore and type(identities) is PreparationIdentities and not self._used)
        self._used = True
        rows = {}
        try:
            for account, token in identities.mapping().items():
                salt = secrets.token_bytes(32)
                extra = entropy(self._passwords[account], salt, installation, account)
                raw = e.canonical(dict(schema=SCHEMA, installation=installation,
                                       actor=actor_for(account), bearer=token))
                cipher = store.protection.protect(raw, extra)
                rows[account] = dict(actor=actor_for(account), token_sha256=hashlib.sha256(token.encode('ascii')).hexdigest(),
                                     salt=salt.hex(), ciphertext=base64.b64encode(cipher).decode('ascii'))
            config = dict(schema=SCHEMA, installation=installation, port=port, accounts=rows)
            return parse_config(e.canonical(config).decode('ascii'))
        finally:
            self._passwords = None  # Python immutable caller copies cannot be securely erased.


def prompt_enrollment():
    from scripts.windows.lifecycle import require_setup_readiness
    require_setup_readiness()  # Never prompt or create material behind the owner pause.
    passwords = {}
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)  # No echoing stdin fallback.
        for account in ACCOUNTS:
            label = ('企业' if account in ENTERPRISES else '专员') + ' ' + account[-1].upper()
            value = getpass.getpass(label+' · 设置独立密码（12–256 字）：')
            need(value == getpass.getpass(label+' · 再次输入：'))
            password_bytes(value); passwords[account] = value
    return NativeLoginEnrollment(passwords)


class NativePasswordLogin:
    def __init__(self, store, raw):
        need(os.name == 'nt')
        self.store = store; self.config = parse_config(raw)
        self.failed = False; self.unknown_native = []

    def unlock(self, account, password):
        from .dpapi_native_candidate import _NativeDPAPI, NativeFailure
        need(not self.failed and account in ACCOUNTS)
        row = self.config['accounts'][account]
        extra = entropy(password, bytes.fromhex(row['salt']), self.config['installation'], account)
        native = _NativeDPAPI()
        try:
            # A failed password never reuses a poisoned DPAPI call object.
            raw = native.unprotect(base64.b64decode(row['ciphertext'], validate=True), extra)
        except NativeFailure as error:
            if (not error.cleanup_types and error.phase == 'ALLOCATION' and
                    error.primary_type == 'ProtectionRefused' and error.winerror == 13):
                raise Denied('protected local login unavailable') from None
            self.failed = True; self.unknown_native.append(native)
            raise RuntimeError('native login outcome unknown; restart requires original runtime verification') from None
        except BaseException:
            self.failed = True; self.unknown_native.append(native)
            raise
        value = json.loads(raw, object_pairs_hook=e.pairs)
        e.exact(value, ('schema', 'installation', 'actor', 'bearer'))
        need(e.canonical(value) == raw and value['schema'] == SCHEMA and
             value['installation'] == self.config['installation'] and value['actor'] == row['actor'])
        token = value['bearer']
        need(type(token) is str and 1 <= len(token) <= 512 and
             hmac.compare_digest(hashlib.sha256(token.encode('ascii')).hexdigest(), row['token_sha256']))
        with self.store.connect() as connection:
            actor = self.store.auth(connection, token, lock=True)
            need({key: actor[key] for key in row['actor']} == row['actor'])
        return dict(bearer=token, role=actor['role'], actor_id=actor['id'], actor=row['actor'],
                    installation_id=self.config['installation'], scope='SYNTHETIC_LOCAL_PREPARATION_ONLY')


def configured_app():
    from parkweave.api import create_app
    from parkweave.store import Store
    from parkweave.local_workspace import mount_workspace
    need(os.name == 'nt' and os.environ.get('PARKWEAVE_MODE') == 'LOCAL')
    store = Store(os.environ['PARKWEAVE_DSN'], mode='LOCAL', file_root=os.environ['PARKWEAVE_FILE_ROOT'])
    login = NativePasswordLogin(store, os.environ[ENVIRONMENT])
    labels = tuple((name, ('企业' if name in ENTERPRISES else '专员')+' '+name[-1].upper()) for name in ACCOUNTS)
    return mount_workspace(create_app(store), login.unlock, login.config['port'], labels)
