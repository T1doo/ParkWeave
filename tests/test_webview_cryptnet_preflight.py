"""Source and endpoint guards. These tests do not exercise Cryptnet."""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from scripts.windows_ci import webview_cryptnet_preflight as webview
from scripts.windows_ci.crt_crl_preparation import PreparationRefused
from scripts.windows_portable import native_trial_authority


@pytest.mark.parametrize('operations', [[], ['PUBLIC_CRL_NATIVE_REDIRECT_CACHE'],
                                        ['OWN_EXE_WEBVIEW_UI_AND_PIXELS']])
def test_webview_cache_requires_both_operations_before_native_io(monkeypatch, operations):
    monkeypatch.setattr(native_trial_authority, 'state',
                        lambda _: SimpleNamespace(window=SimpleNamespace(operations=operations)))
    monkeypatch.setattr(webview, 'ReadOnlySignature', lambda *_: pytest.fail('native file opened'))
    with pytest.raises(native_trial_authority.TrialRefused):
        webview.prepare(object())


def test_crl_endpoint_is_fixed_by_the_bound_signing_chain(monkeypatch):
    chain = [b'synthetic leaf', b'synthetic issuer']
    leaf = dict(crl_distribution_points=[webview.CDP], issuer_name_der_sha256='name',
                authority_key_identifier='key')
    issuer = dict(subject_name_der_sha256='name', subject_key_identifier='key')
    monkeypatch.setattr(webview, 'certificate', lambda der, _: dict(zip(chain, (leaf, issuer)))[der])
    with pytest.raises(PreparationRefused) as wrong_pin:
        webview._crl_inputs(chain, lambda: None)
    assert wrong_pin.value.reason == 'WEBVIEW_CRL_ISSUER_PIN'
    monkeypatch.setattr(webview, 'ISSUER', sha256(chain[1]).hexdigest())
    assert webview._crl_inputs(chain, lambda: None) == (leaf, issuer)
    leaf['crl_distribution_points'] = ['http://example.invalid/elsewhere.crl']
    with pytest.raises(PreparationRefused) as wrong_endpoint:
        webview._crl_inputs(chain, lambda: None)
    assert wrong_endpoint.value.reason == 'WEBVIEW_CRL_ENDPOINT_OR_ISSUER'
