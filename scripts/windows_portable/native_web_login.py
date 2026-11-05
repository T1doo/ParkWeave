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
from .local_preparation_identity import ENTERPRISES, REVIEWERS, PreparationIdentities, PreparationProfile, EXECUTOR, RESOURCE_ADMIN

ENVIRONMENT = 'PARKWEAVE_NATIVE_LOGIN'
SCHEMA = 'parkweave-native-password-login/1'
MAX_CONFIG = 14000
ACCOUNTS = ENTERPRISES + REVIEWERS
MATERIAL_LABELS = tuple(
    (name, ('企业' if name in ENTERPRISES else '专员') + ' ' + name[-1].upper())
    for name in ACCOUNTS
)
SAMPLE_ACCOUNTS=('fixture-a','prep-specialist-fixture-a',EXECUTOR,RESOURCE_ADMIN)
SAMPLE_SCHEMA='parkweave-native-password-login/2'


def accounts(profile):
    need(type(profile) is PreparationProfile)
    return SAMPLE_ACCOUNTS if profile is PreparationProfile.SAMPLE else ACCOUNTS


def config_profile(value):
    return PreparationProfile.SAMPLE if value.get('schema')==SAMPLE_SCHEMA else PreparationProfile.MATERIAL


def need(ok):
    if not ok: raise Denied('protected local login unavailable')


def actor_for(account,profile=PreparationProfile.MATERIAL):
    need(account in accounts(profile))
    if profile is PreparationProfile.SAMPLE and account in (EXECUTOR,RESOURCE_ADMIN):
        return dict(id=account,park_id='park-a',org_id='org-a',role='service_executor' if account==EXECUTOR else 'resource_admin')
    suffix = account[-1]
    park = {'a':'park-a', 'b':'park-a', 'c':'park-b'}[suffix]
    return dict(id=account, park_id=park, org_id='org-'+suffix,
                role='enterprise_operator' if account in ENTERPRISES else 'park_specialist')


def password_bytes(password):
    need(type(password) is str and 12 <= len(password) <= 256)
    return password.encode('utf-8')


def entropy(password, salt, installation, account,profile=PreparationProfile.MATERIAL):
    need(type(salt) is bytes and len(salt) == 32)
    key = hashlib.scrypt(password_bytes(password), salt=salt, n=32768, r=8, p=1,
                         maxmem=64*1024*1024, dklen=32)
    return hmac.digest(key, e.canonical(dict(schema=SAMPLE_SCHEMA if profile is PreparationProfile.SAMPLE else SCHEMA, installation=installation,
                                           actor=actor_for(account,profile))), 'sha256')


def parse_config(raw):
    need(type(raw) is str and 0 < len(raw) <= MAX_CONFIG)
    value = json.loads(raw, object_pairs_hook=e.pairs)
    need(type(value) is dict)
    profile=config_profile(value)
    e.exact(value, ('schema','installation','port','accounts','profile','sample','sample_sha256') if profile is PreparationProfile.SAMPLE else ('schema', 'installation', 'port', 'accounts'))
    need(value['schema'] == (SAMPLE_SCHEMA if profile is PreparationProfile.SAMPLE else SCHEMA) and re.fullmatch('[0-9a-f]{64}', value['installation']) and
         type(value['port']) is int and 1 <= value['port'] <= 65535 and set(value['accounts']) == set(accounts(profile)))
    if profile is PreparationProfile.SAMPLE:
        need(value['profile']==profile.value)
        from parkweave.local_synthetic_demo import NativeDemoInputs
        NativeDemoInputs.parse(value['sample']).values()
        need(hashlib.sha256(value['sample'].encode()).hexdigest()==value['sample_sha256'])
    for account, row in value['accounts'].items():
        e.exact(row, ('actor', 'token_sha256', 'salt', 'ciphertext'))
        need(row['actor'] == actor_for(account,profile))
        e.digest(row['token_sha256'])
        need(type(row['salt']) is str and re.fullmatch('[0-9a-f]{64}', row['salt']))
        need(type(row['ciphertext']) is str and 0 < len(row['ciphertext']) <= 4096)
        need(0 < len(base64.b64decode(row['ciphertext'], validate=True)) <= 3072)
    return value


class NativeLoginEnrollment:
    """Future installation input only; constructor neither generates nor stores tokens."""
    def __init__(self, passwords,*,profile=PreparationProfile.MATERIAL):
        names=accounts(profile);self.profile=profile
        need(type(passwords) is dict and set(passwords) == set(names))
        for value in passwords.values(): password_bytes(value)
        need(len(set(passwords.values())) == len(names))
        self._passwords = dict(passwords); self._used = False

    def __repr__(self): return '<NativeLoginEnrollment private>'
    def __reduce__(self): raise TypeError('LOGIN_INPUT_NOT_SERIALIZABLE')

    def seal(self, store, identities, installation, port,*,sample=None):
        from .native_secret_store_candidate import _NativeFixedSecretStore
        from .native_trial_authority import require_owner
        require_owner(self)
        need(type(store) is _NativeFixedSecretStore and type(identities) is PreparationIdentities and identities.profile is self.profile and not self._used)
        self._used = True
        rows = {}
        try:
            values=identities.mapping()
            for account in accounts(self.profile):
                token=values[account]
                salt = secrets.token_bytes(32)
                extra = entropy(self._passwords[account], salt, installation, account,self.profile)
                schema=SAMPLE_SCHEMA if self.profile is PreparationProfile.SAMPLE else SCHEMA
                raw = e.canonical(dict(schema=schema, installation=installation,
                                       actor=actor_for(account,self.profile), bearer=token))
                cipher = store.protection.protect(raw, extra)
                rows[account] = dict(actor=actor_for(account,self.profile), token_sha256=hashlib.sha256(token.encode('ascii')).hexdigest(),
                                     salt=salt.hex(), ciphertext=base64.b64encode(cipher).decode('ascii'))
            config = dict(schema=SCHEMA, installation=installation, port=port, accounts=rows)
            if self.profile is PreparationProfile.SAMPLE:
                config.update(schema=SAMPLE_SCHEMA,profile=self.profile.value,sample=sample,
                    sample_sha256=hashlib.sha256(sample.encode()).hexdigest())
            else:need(sample is None)
            return parse_config(e.canonical(config).decode('ascii'))
        finally:
            self._passwords = None  # Python immutable caller copies cannot be securely erased.


def prompt_enrollment(*,profile=PreparationProfile.MATERIAL):
    from scripts.windows.lifecycle import require_setup_readiness
    require_setup_readiness()  # Never prompt or create material behind the owner pause.
    passwords = {}
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)  # No echoing stdin fallback.
        for account in accounts(profile):
            label = {'service_executor':'执行者','resource_admin':'资源管理员','enterprise_operator':'企业','park_specialist':'专员'}[actor_for(account,profile)['role']]+' '+account[-1].upper()
            value = getpass.getpass(label+' · 设置独立密码（12–256 字）：')
            need(value == getpass.getpass(label+' · 再次输入：'))
            password_bytes(value); passwords[account] = value
    return NativeLoginEnrollment(passwords,profile=profile)


class NativePasswordLogin:
    def __init__(self, store, raw):
        need(os.name == 'nt')
        self.store = store; self.config = parse_config(raw)
        self.profile=config_profile(self.config)
        self.failed = False; self.unknown_native = []

    def unlock(self, account, password):
        from .dpapi_native_candidate import _NativeDPAPI, NativeFailure
        profile=config_profile(self.config)
        need(not self.failed and account in accounts(profile))
        row = self.config['accounts'][account]
        extra = entropy(password, bytes.fromhex(row['salt']), self.config['installation'], account,profile)
        native = _NativeDPAPI()
        try:
            # A failed password never reuses a poisoned DPAPI call object.
            raw = native.unprotect(base64.b64decode(row['ciphertext'], validate=True), extra)
        except NativeFailure as error:
            if error.invalid_data_call_refusal:
                raise Denied('protected local login unavailable') from None
            self.failed = True; self.unknown_native.append(native)
            raise RuntimeError('native login outcome unknown; restart requires original runtime verification') from None
        except BaseException:
            self.failed = True; self.unknown_native.append(native)
            raise
        value = json.loads(raw, object_pairs_hook=e.pairs)
        e.exact(value, ('schema', 'installation', 'actor', 'bearer'))
        need(e.canonical(value) == raw and value['schema'] == self.config['schema'] and
             value['installation'] == self.config['installation'] and value['actor'] == row['actor'])
        token = value['bearer']
        need(type(token) is str and 1 <= len(token) <= 512 and
             hmac.compare_digest(hashlib.sha256(token.encode('ascii')).hexdigest(), row['token_sha256']))
        with self.store.connect() as connection:
            actor = self.store.auth(connection, token, lock=True)
            need({key: actor[key] for key in row['actor']} == row['actor'])
        return dict(bearer=token, role=actor['role'], actor_id=actor['id'], actor=row['actor'],
                    installation_id=self.config['installation'], scope='NATIVE_SYNTHETIC_COLLABORATION_ONLY' if profile is PreparationProfile.SAMPLE else 'SYNTHETIC_LOCAL_PREPARATION_ONLY')


def configured_app():
    from parkweave.api import create_app
    from parkweave.store import Store
    from parkweave.local_workspace import mount_workspace
    need(os.name == 'nt' and os.environ.get('PARKWEAVE_MODE') == 'LOCAL')
    store = Store(os.environ['PARKWEAVE_DSN'], mode='LOCAL', file_root=os.environ['PARKWEAVE_FILE_ROOT'])
    login = NativePasswordLogin(store, os.environ[ENVIRONMENT])
    if login.profile is PreparationProfile.SAMPLE:
        from .native_sample import ENVIRONMENT as SAMPLE_ENV,dependencies,NativeSampleWorkspace,LABELS
        from parkweave.local_resource_approval import configure
        need(os.environ.get(SAMPLE_ENV)==login.config['sample'])
        steps=dependencies(store,login.config['sample'])
        app=create_app(store,local_synthetic_demo=steps.local_synthetic_demo,
            case_step_assignments=steps,local_resource_approval=configure(store,'CURRENT_OWNER'))
        return mount_workspace(app,login.unlock,login.config['port'],LABELS,
            sample_workspace=NativeSampleWorkspace(store,login.config['sample']))
    from .native_sample import ENVIRONMENT as SAMPLE_ENV
    need(SAMPLE_ENV not in os.environ)
    return mount_workspace(create_app(store), login.unlock, login.config['port'], MATERIAL_LABELS)
