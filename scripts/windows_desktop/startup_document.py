"""Package the existing workspace frontend for the pre-backend desktop view.

No replacement design, server, credentials or native activation is created here.
"""
import base64
from pathlib import Path


def render(root: Path):
    app=root/'src/parkweave'
    html=(app/'web.html').read_text(encoding='utf-8')
    css=(app/'workspace_design.css').read_text(encoding='utf-8')
    design=(app/'workspace_design.js').read_text(encoding='utf-8')
    startup=(app/'desktop_startup.js').read_text(encoding='utf-8')
    if '</style' in css.lower() or any('</script' in s.lower() for s in (design,startup)):
        raise ValueError('STARTUP_INLINE_BOUNDARY')
    replacements={
        '<link rel="stylesheet" href="/workspace-design.css">':'<style>'+css+'</style>',
        '<script src="/workspace-design.js"></script>':'<script>'+design+'</script>',
    }
    for old,new in replacements.items():
        if html.count(old)!=1:raise ValueError('WORKSPACE_ASSET_ANCHOR_CHANGED')
        html=html.replace(old,new)
    icon='data:image/png;base64,'+base64.b64encode((app/'assets/parkweave-mark-128.png').read_bytes()).decode('ascii')
    html=html.replace('/parkweave-mark.png',icon)
    policy="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'"
    charset='<meta charset="utf-8">'
    if html.count(charset)!=1:raise ValueError('WORKSPACE_CHARSET_ANCHOR_CHANGED')
    html=html.replace(charset,charset+'<meta http-equiv="Content-Security-Policy" content="'+policy+'">',1)
    html=html.replace('</body>','<script>'+startup+'</script></body>',1)
    if len(html.encode('utf-8'))>1900000:raise ValueError('STARTUP_DOCUMENT_TOO_LARGE')
    return html
