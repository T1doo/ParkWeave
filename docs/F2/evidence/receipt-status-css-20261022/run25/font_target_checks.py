"""Pure injected target-node guards; no browser or font rendering execution."""
from copy import deepcopy
import hashlib,json
from unittest.mock import patch
from scripts import receipt_status_css_browser_once as m
text='待核对';row={'exists':True,'ariaLive':'polite','display':'block','text':text,'height':50,'borderLeft':'3px','paddingTop':'14px','clientHeight':50,'scrollHeight':50,'withinViewport':True,'verticallyVisible':True,'pageOverflow':False}
node={'selector':'#receipt-submit-status','required_codepoints':sorted(m.ui_codepoints(text)),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'missing_codepoints':[],'invalid_sources':[]}
class Page:
 viewport_size={'width':390,'height':1000}
 def locator(self,_):return self
 def scroll_into_view_if_needed(self,**_):pass
 def evaluate(self,_):return deepcopy(row)
results=[]
for case in ('valid','absent','duplicate','wrong_text_hash','wrong_codepoints'):
 nodes=[deepcopy(node)]
 if case=='absent':nodes=[]
 if case=='duplicate':nodes*=2
 if case=='wrong_text_hash':nodes[0]['text_sha256']='0'*64
 if case=='wrong_codepoints':nodes[0]['required_codepoints']=[]
 m.REPORT={'checks':[],'installed_CJK_font':{'visible_node_font_usage':nodes}}
 with patch.object(m,'verify_rendered_font'):
  try:m.metrics(Page(),'after-unknown',False)
  except AssertionError:assert case!='valid'
  else:assert case=='valid' and len(m.REPORT['font_observations'])==1
 results.append({'case':case,'expected_guard_outcome':'PASS'})
print(json.dumps({'injected_target_node_cases':5,'results':results,'browser_runs':0,'CSP_or_font_rendering_verified':False},indent=2))
