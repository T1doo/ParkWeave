import json,re,io
from scripts.windows_portable.desktop_bridge import request as bridge_request
from pathlib import Path
import pytest
from scripts.windows_desktop.startup_document import render
from scripts.windows_desktop.startup_protocol import parse_message


def test_startup_reuses_current_workspace_assets_with_no_network():
    root=Path(__file__).parents[1];html=render(root)
    normalized=re.sub(r'data:image/png;base64,[A-Za-z0-9+/=]+','/parkweave-mark.png',html)
    assert (root/'src/parkweave/workspace_design.css').read_text(encoding='utf-8') in normalized
    assert (root/'src/parkweave/workspace_design.js').read_text(encoding='utf-8') in html
    assert 'id="resource-form"' in html and 'id="prep-detail"' in html
    assert "connect-src 'none'" in html and "form-action 'none'" in html
    assert html.index('Content-Security-Policy')<html.index('<script')
    assert 'src="/workspace-design.js"' not in html and 'href="/workspace-design.css"' not in html
    assert 'data:image/png;base64,' in html


def reopen():
    return dict(action='reopen',instance='C:\\synthetic',database_port=0,api_port=0,passwords={},initialize_profile=False,sample_collaboration=True)


def test_startup_message_retains_original_request_shape():
    value=reopen()
    assert parse_message(json.dumps(dict(protocol='PARKWEAVE_STARTUP_V1',request=value)))==value
    framed=(json.dumps(dict(protocol='PARKWEAVE_STARTUP_V1',request=value))+'\n').encode()
    assert bridge_request(io.BytesIO(framed))==value


@pytest.mark.parametrize('mutation',[
    {'action':'execute'},{'action':'status'},{'database_port':True},
    {'passwords':{'unexpected':'secret'}},{'command':'arbitrary'}, {'initialize_profile':'yes'}
])
def test_startup_cannot_expand_original_bridge_contract(mutation):
    with pytest.raises(ValueError):
        parse_message(json.dumps(dict(protocol='PARKWEAVE_STARTUP_V1',request={**reopen(),**mutation})))


def test_duplicate_and_oversized_messages_rejected():
    with pytest.raises(ValueError):parse_message('{"protocol":"x","protocol":"PARKWEAVE_STARTUP_V1","request":{}}')
    with pytest.raises(ValueError):parse_message('x'*32769)
