"""Pure navigation observation shared by mechanical DOM and browser checks.

Keep this separate from the historical, source-pinned visual drivers: replacing
one visual scenario must not orphan the request-recovery assertions.
"""

NAVIGATION_WORKSPACE_SCRIPT = """() => ({
 workspace: {present:document.body.hasAttribute('data-workspace'),
             value:document.body.getAttribute('data-workspace')},
 current:[...document.querySelectorAll('[data-tab][aria-current=page]')].map(n=>n.dataset.tab),
 panels:['service','collaboration','resource'].map(id=>({id,hidden:document.getElementById(id).hidden}))
})"""


def assert_navigation_workspace(before, after):
    """UNKNOWN refusal preserves a valid service entry, including absent attrs."""
    expected_panels = [dict(id='service', hidden=False),
                       dict(id='collaboration', hidden=True),
                       dict(id='resource', hidden=True)]
    for value in (before, after):
        assert set(value) == {'workspace', 'current', 'panels'}
        workspace = value['workspace']
        assert set(workspace) == {'present', 'value'}
        assert type(workspace['present']) is bool
        if workspace['present']:
            assert workspace['value'] == 'service'
        else:
            assert workspace['value'] is None
        assert value['current'] == ['service']
        assert value['panels'] == expected_panels
        assert all(type(panel['hidden']) is bool for panel in value['panels'])
    assert before == after
