"""Regression from actual run14: closed native details rects are not glyphs."""
import json,subprocess
from pathlib import Path
import pytest
from scripts.fictional_park_restart_browser_once import VISIBLE_FONT_NODES_SCRIPT
ROOT=Path(__file__).resolve().parents[1]


def collect(source,mode):
    r=subprocess.run(['node','tests/font_details_visibility_oracle.js'],cwd=ROOT,input=json.dumps(dict(source=source,mode=mode)),text=True,capture_output=True,timeout=10)
    assert r.returncode==0,r.stderr
    return json.loads(r.stdout)


def test_original_run14_collector_red_includes_unpainted_closed_details():
    # Exact run14 collector, frozen here so shallow checkouts need no historical Git objects.
    # Original UTF-8 SHA256: 19afc182e3702ca3ae898cb67775ca2cc6f0aa5bcd1c433d25721dbdc3c848f3
    original="() => {\n        const found=new Map(), walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);\n        const path=e=>e.id?'#'+CSS.escape(e.id):e===document.body?'body':path(e.parentElement)+' > '+e.tagName.toLowerCase()+':nth-child('+([...e.parentElement.children].indexOf(e)+1)+')';\n        for(let n; n=walk.nextNode();){\n            if(!/[\\u3400-\\u9fff\\u3000-\\u303f\\uff00-\\uffef]/u.test(n.data))continue;\n            const e=n.parentElement,s=getComputedStyle(e),r=document.createRange();r.selectNodeContents(n);\n            if(s.visibility!=='visible'||s.opacity==='0'||!Array.from(r.getClientRects()).some(b=>b.width&&b.height&&b.bottom>0&&b.right>0&&b.top<innerHeight&&b.left<innerWidth))continue;\n            const key=path(e);found.set(key,(found.get(key)||'')+n.data);\n        }return [...found].map(([selector,text])=>({selector,text}));} "
    assert '#hidden-or-open-content' in collect(original,'closed')
    assert '#hidden-or-open-content' not in collect(VISIBLE_FONT_NODES_SCRIPT,'closed')


@pytest.mark.parametrize('mode,expected',[
 ('closed',['#visible-heading','#first-summary-span']),
 ('opened',['#visible-heading','#first-summary-span','#hidden-or-open-content']),
 ('outer_closed',['#visible-heading','#first-summary-span']),
 ('inner_closed',['#visible-heading','#first-summary-span','#hidden-or-open-content','#inner-summary-span']),
 ('second_summary',['#visible-heading','#first-summary-span']),
 ('no_summary',['#visible-heading']),
])
def test_only_native_painted_details_text_reaches_unchanged_CDP_checks(mode,expected):
    assert collect(VISIBLE_FONT_NODES_SCRIPT,mode)==expected
