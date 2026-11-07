"""Prepare one public WebView2 CRL under the original disposable trial grant."""
import ctypes as C
from hashlib import sha256
from pathlib import PureWindowsPath
import re
import time
import uuid

from scripts.windows_portable import authenticode_signature as trust, native_trial_authority as authority
from .crt_certificate_metadata import certificate
from .crt_crl_preparation import need
from .crt_cryptnet_cache_trial import NativeCachedCRL
from .crt_signature_readonly import ReadOnlySignature


CDP = 'http://www.microsoft.com/pkiops/crl/Microsoft%20Code%20Signing%20PCA%202024.crl'
ISSUER = '3dadfaf812dd1bbaef45834ccbd188f3cd97139e2ed1aca69c2dd63082142f8f'
CLIENT = r'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
OFFLINE = 0x80092013
MAX_BYTES = 2 * 1024 * 1024


def _installed_path():
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLIENT, 0,
                       winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
        version, kind = winreg.QueryValueEx(key, 'pv')
    need(kind == winreg.REG_SZ and type(version) is str and len(version) < 128
         and re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}', version) and version != '0.0.0.0',
         'WEBVIEW_INSTALLATION_VERSION')
    shell = C.WinDLL('shell32.dll', winmode=0x800)
    get = trust.bind(shell, 'SHGetFolderPathW', C.c_int32,
                     [trust.P, C.c_int, trust.P, trust.D, C.c_wchar_p])
    directory = C.create_unicode_buffer(260)
    need(get(None, 0x2a, None, 0, directory) == 0, 'WEBVIEW_INSTALLATION_DIRECTORY')
    root = PureWindowsPath(directory.value)
    need(root.is_absolute() and len(root.drive) == 2 and root.drive[1] == ':',
         'WEBVIEW_INSTALLATION_DIRECTORY')
    return str(root / 'Microsoft' / 'EdgeWebView' / 'Application' / version / 'msedgewebview2.exe')


def _selected_chain(probe, handle, path):
    guard = lambda: probe._signature_budget(None, None)
    action = C.create_string_buffer(uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le)
    file = trust.FileTrust(C.sizeof(trust.FileTrust), path, handle, None)
    data = trust.TrustData()
    data.size, data.ui, data.revocation, data.choice = C.sizeof(data), 2, 1, 1
    data.file, data.action, data.flags = C.pointer(file), 1, 0x1000 | 0x80
    guard()
    try:
        need(probe.native_wvt(None, action, C.byref(data)) == 0 and data.state,
             'WEBVIEW_CACHE_ONLY_VERIFY_REFUSED')
        provider = probe.call(probe.native_provider, data.state)
        need(provider, 'WEBVIEW_PROVIDER_STATE')
        signer = probe.call(probe.native_signer, provider, 0, False, 0)
        need(signer and signer.contents.size == C.sizeof(trust.Signer)
             and signer.contents.count == 3 and not signer.contents.error
             and not signer.contents.type & 0x10, 'WEBVIEW_SIGNER_POLICY')
        chain = []
        offline = False
        for index in range(3):
            entry = probe.call(probe.native_cert, signer, index)
            need(entry and entry.contents.size == C.sizeof(trust.ProviderCert),
                 'WEBVIEW_CHAIN_MEMBER')
            row = entry.contents
            need(row.cert and not (row.test or row.cyclic or row.error)
                 and (row.revoked == 0 or (index == 0 and row.revoked == OFFLINE)),
                 'WEBVIEW_CHAIN_MEMBER')
            context = row.cert.contents
            need(context.der and 0 < context.length <= 65536, 'WEBVIEW_CHAIN_BYTES')
            chain.append(C.string_at(context.der, context.length))
            if index == 0:
                name = C.create_unicode_buffer(256)
                oid = C.create_string_buffer(b'2.5.4.10')
                size = probe.call(probe.cert_name, row.cert, 3, 0, oid, name, len(name))
                need(1 < size < len(name) and name.value == 'Microsoft Corporation', 'WEBVIEW_PUBLISHER')
                offline = row.revoked == OFFLINE
        need(sha256(chain[-1]).hexdigest() == trust.ROOT_SHA256, 'WEBVIEW_ROOT_PIN')
        return chain, offline
    finally:
        try:
            probe._signature_cleanup_budget(None)
            data.action = 2
            need(probe.native_wvt(None, action, C.byref(data)) == 0, 'WEBVIEW_TRUST_CLOSE')
        except BaseException:
            probe.unknown.append((action, data, file))
            probe._retain_trust_unknown()
            raise


def _crl_inputs(chain, guard):
    need(sha256(chain[1]).hexdigest() == ISSUER, 'WEBVIEW_CRL_ISSUER_PIN')
    leaf, issuer = (certificate(der, guard) for der in chain[:2])
    need(leaf['crl_distribution_points'] == [CDP]
         and leaf['issuer_name_der_sha256'] == issuer['subject_name_der_sha256']
         and leaf['authority_key_identifier'] is not None
         and leaf['authority_key_identifier'] == issuer['subject_key_identifier'],
         'WEBVIEW_CRL_ENDPOINT_OR_ISSUER')
    return leaf, issuer


def prepare(cap):
    state = authority.state(cap)
    authority.need({'PUBLIC_CRL_NATIVE_REDIRECT_CACHE', 'OWN_EXE_WEBVIEW_UI_AND_PIXELS'} <= set(state.window.operations))
    end = min(time.monotonic() + 30, state.deadline)
    cleanup_end = min(end + 10, state.cleanup_end)
    probe = ReadOnlySignature(end, cleanup_end)
    try:
        path = _installed_path()
        handle = probe.call(probe.open, path, 0x80000000, 1, None, 3, 0x200000, None)
        need(handle not in (None, 0, trust.P(-1).value), 'WEBVIEW_EXECUTABLE_OPEN')
        probe.handles.append(handle)
        before = probe.identity(handle)
        chain, offline = _selected_chain(probe, handle, path)
        need(before == probe.identity(handle), 'WEBVIEW_EXECUTABLE_CHANGED')
        if not offline:
            return {'status': 'CACHE_ONLY_CHECK_PASSED', 'retrieval': None}
        retriever = NativeCachedCRL(end, cleanup_end)
        leaf, issuer = _crl_inputs(chain, retriever.guard)
        authority.state(cap)
        retrieval = retriever._acquire(leaf, issuer, chain[1], CDP, MAX_BYTES)
        observed, still_offline = _selected_chain(probe, handle, path)
        need(not still_offline and chain == observed and before == probe.identity(handle),
             'WEBVIEW_CACHE_ONLY_RECHECK_REFUSED')
        return {'status': 'CACHE_ONLY_CHECK_PASSED_AFTER_RETRIEVAL',
                'retrieval': {'bytes': retrieval['bytes'], 'crl_sha256': retrieval['crl_sha256']}}
    finally:
        need(probe.close() == 'OWNED_FILE_HANDLES_CLOSED', 'WEBVIEW_EXECUTABLE_CLOSE')
