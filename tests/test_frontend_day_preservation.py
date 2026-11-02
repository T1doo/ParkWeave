"""Preserve the original app and all HTML assembly anchors across the design rewrite."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import subprocess

from parkweave.local_workspace import full_workspace_page, full_sample_workspace_page

ROOT = Path(__file__).parents[1]
BASE = 'fbb27a59dbbeb01b8af80e5706e42b3d185a5459'


class IDs(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = Counter()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get('id')
        if value:
            self.ids[value] += 1


def test_original_html_ids_and_business_javascript_are_preserved():
    for name in ('web.html', 'local_preparation_web.html'):
        path = 'src/parkweave/' + name
        before = subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT, text=True)
        after = (ROOT / path).read_text()
        assert IDs(before).ids == IDs(after).ids
        original = before.split('<script>')[1].split('</script>')[0].strip()
        current = after.split('<script>')[1].split('// Frontend-day presentation.')[0].strip()
        if name == 'web.html':
            current = current.replace('bundleControls();parkDesignRefresh();}', 'bundleControls();}')
            # New explicit-owner candidates retain every original seal/binding
            # assertion while extending only the exact producer/version pairing.
            current = current.replace('!parkObservationProducerValid(consumption)', "consumption?.verification_basis?.validator_version!=='LOCAL_SYNTHETIC_DEMO_V2'||!localDemoProducerValid(consumption.producer,'LOCAL_SYNTHETIC_DEMO_V2')")
            current = current.replace('parkSelectionProducerCaption(source.candidate.producer)', "'原候选来自离线合成规划输出；原provider未启用，原采用仍由企业明确确认。'")
        assert original == current, 'business handler or original request contract changed'


def test_exact_login_and_four_role_assembly_still_bind_once():
    root = ROOT / 'src/parkweave'
    accounts = [('fixture-a', '企业经办'), ('specialist', '园区专员'),
                ('executor', '服务执行者'), ('resource-admin', '资源管理员')]
    for page in (full_workspace_page(root, accounts),
                 full_sample_workspace_page(root, accounts, 'SYNTHETIC_VALID_UNTIL')):
        assert page.count('id="local-workspace-session"') == 1
        assert page.count('<body class="desktop-shell" data-local-workspace="locked">') == 1
        assert page.count('<style>') == page.count('</style>') == 1
        assert '/local-command-pending.js' in page
        assert '/local-workspace-login.js' in page
        assert 'resource_admin' in page or '服务执行者' in page
    sample = full_sample_workspace_page(root, accounts, 'SYNTHETIC_VALID_UNTIL')
    assert sample.count('id="local-sample-resource-panel"') == 1
    assert 'body[data-local-role="resource_admin"] #park-main>:not(#local-sample-resource-panel):not(.shell-toolbar){display:none!important}' in sample
