"""Font-selection and CDP fixtures only. Never starts a browser or service."""
from copy import deepcopy
from hashlib import sha256
import json
import base64
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET
from scripts import fictional_park_restart_browser_once as font

ROOT=Path(__file__).parent
BASELINE='3c2cb8adfd14325db55df8d2954da9f4f08d59c0'
POINTS=font.ui_codepoints(''.join((font.original.ROOT/p).read_text() for p in
    ['src/parkweave/web.html','src/parkweave/park_demo_web.html']))
assert len(POINTS)==683
ORDER=sorted(POINTS); A=set(ORDER[:341]); B=POINTS-A
FA='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FB='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
assert Path(FA).is_file() and Path(FB).is_file()
results=[]

def line(file,index,family,postscript,points):
    return '\t'.join([file,str(index),family,postscript,' '.join(f'{p:x}' for p in sorted(points))])+'\n'

def attempt(name,*,missing=False,match_missing=False,extra='',limit=None,duplicate_ps=False):
    left=line(FA,0,'字体甲','FixtureA',A)
    right=line(FB,2,'字体乙 & Symbols','FixtureA' if duplicate_ps else 'FixtureB',B-({ORDER[-1]} if missing else set()))
    inventory=left+right+extra; calls=[]; report={}
    directory=Path(tempfile.mkdtemp(prefix=name+'-',dir=ROOT))/'font-config'
    def command(argv,**kwargs):
        calls.append((argv,kwargs['env']))
        if argv[0]=='fc-list': assert argv==['fc-list','-f',font.FONT_FORMAT]
        else:
            assert argv[0]=='fc-match' and kwargs['env']['FONTCONFIG_FILE']==str(directory/'fonts.conf')
            assert kwargs['timeout']==3
        raw=inventory if argv[0]=='fc-list' else left if match_missing else left+right
        return subprocess.CompletedProcess(argv,0,stdout=raw.encode(),stderr=b'')
    error=None; returned=None
    with patch.object(font.subprocess,'run',side_effect=command), patch.object(font,'FONT_DIAGNOSTIC_LIMIT',limit or font.FONT_DIAGNOSTIC_LIMIT):
        try: returned=font.installed_font_environment(dict(os.environ),directory,report)
        except RuntimeError as e: error=str(e)
    return report['installed_CJK_font'],directory,calls,error,returned

s,d,c,error,env=attempt('two-font-union')
assert not error and s['status']=='INSTALLED_CHARSET_COVERS_UI'
diag=font.unpack_font_diagnostics(s)
assert all(r['covered_count']<683 for r in diag['candidates'])
assert set().union(*(set(r['covered_codepoints']) for r in diag['candidates']))==POINTS
assert len(c)==3 and all(not x['missing_codepoints'] for x in s['resolved'].values())
assert all(set(r['missing_codepoints'])==POINTS-set(r['covered_codepoints']) for r in diag['candidates'])
assert '字体甲' in (d/'fonts.conf').read_text() and '&amp;' in (d/'fonts.conf').read_text()
ET.fromstring((d/'fonts.conf').read_text())
assert diag==json.loads((d/'font-diagnostics.json').read_text())
results.append(dict(name='two_partial_fonts_union683_Unicode_families_and_exact_diagnostics',result='PASS'))

missing,_,calls,error,_=attempt('missing-one',missing=True)
assert error and missing['status']=='NO_INSTALLED_CJK_SET_COVERAGE' and missing['missing_codepoints']==[ORDER[-1]] and len(calls)==1
assert font.unpack_font_diagnostics(missing)['commands']['inventory']['stdout']
results.append(dict(name='union_still_missing_one_refused_with_complete_missing_codepoint',result='PASS'))

resolved,_,_,error,_=attempt('resolved-missing',match_missing=True)
assert error and resolved['status']=='FONTCONFIG_RESOLVED_SET_MISSING_UI'
assert set(resolved['resolved']['system-ui']['missing_codepoints'])==B
assert 'system-ui' in font.unpack_font_diagnostics(resolved)['commands']
results.append(dict(name='complete_inventory_but_actual_fc_match_chain_incomplete_refused',result='PASS'))

bad=line('/tmp/fixture-font-not-system.ttf',0,'外部字体','Outside',POINTS)+'malformed row\n'
filtered,_,_,error,_=attempt('excluded-fonts',extra=bad)
assert not error
excluded=[r for r in font.unpack_font_diagnostics(filtered)['candidates'] if not r['eligible']]
assert len(excluded)==2 and all(r['exclusion_reason'] for r in excluded)
results.append(dict(name='excluded_or_malformed_candidates_keep_reasons_without_losing_valid_unicode_fonts',result='PASS'))

limited,d,_,error,_=attempt('diagnostic-limit',limit=16)
assert error and limited['status']=='FONT_DIAGNOSTIC_PUBLICATION_LIMIT'
assert not limited['diagnostics']['published_complete'] and 'data' not in limited['diagnostics']
assert (d/'font-diagnostics.json').is_file()
assert sha256((d/'font-diagnostics.json').read_bytes()).hexdigest()==limited['diagnostics']['sha256']
results.append(dict(name='diagnostic_limit_refuses_and_preserves_complete_private_original',result='PASS'))

for name,stdout,stderr,complete in [('invalid-utf8',b'\xffinvalid\n',b'\xfefull stderr\n',True),
        ('oversize',b'x'*(2*1024*1024+1),b'full stderr\n',False)]:
    directory=Path(tempfile.mkdtemp(prefix=name+'-',dir=ROOT))/'font-config';report={}
    with patch.object(font.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=stdout,stderr=stderr)):
        try:font.installed_font_environment(dict(os.environ),directory,report)
        except RuntimeError:pass
        else:raise AssertionError(name+' accepted')
    chosen=report['installed_CJK_font'];diag=font.unpack_font_diagnostics(chosen,require_complete=False)
    record=diag['commands']['inventory']
    assert chosen['diagnostics']['published_complete'] is complete
    for key,raw in [('stdout',stdout),('stderr',stderr)]:
        assert (directory/('inventory.'+key)).read_bytes()==raw
        assert record[key+'_sha256']==sha256(raw).hexdigest()
        if complete:assert base64.b64decode(record[key+'_base64'])==raw
    if not complete:assert not record['raw_public_complete'] and 'stdout' not in record
results.append(dict(name='invalid_UTF8_lossless_both_streams_and_oversize_not_falsely_complete',result='PASS',subcases=2))

directory=Path(tempfile.mkdtemp(prefix='launch-failure-',dir=ROOT))/'font-config';report={}
with patch.object(font.subprocess,'run',side_effect=FileNotFoundError('controlled missing fontconfig command')):
    try:font.installed_font_environment(dict(os.environ),directory,report)
    except FileNotFoundError:pass
    else:raise AssertionError('launch error not retained')
failed=report['installed_CJK_font']
assert failed['preflight_error']['type']=='FileNotFoundError' and not failed['diagnostics']['published_complete']
assert font.unpack_font_diagnostics(failed,require_complete=False)['commands']['inventory']['argv'][0]=='fc-list'
results.append(dict(name='command_launch_failure_keeps_original_error_and_incomplete_marker',result='PASS'))

class Session:
    def __init__(self,fonts): self.fonts=fonts; self.detached=False
    def send(self,method,args=None):
        if method=='DOM.getDocument': return {'root':{'nodeId':1}}
        if method=='DOM.querySelector': return {'nodeId':2}
        if method=='CSS.getPlatformFontsForNode': return {'fonts':self.fonts}
        assert method in ['DOM.enable','CSS.enable']; return {}
    def detach(self): self.detached=True
class Page:
    def __init__(self,session): self.context=self; self.session=session
    def new_cdp_session(self,page): assert page is self; return self.session
    def evaluate(self,expression):
        assert 'createTreeWalker' in expression and 'getClientRects' in expression
        return [{'selector':'h1','text':chr(min(p for p in A if 0x3400<=p<=0x9fff))+chr(max(p for p in B if 0x3400<=p<=0x9fff))}]
def glyph(ps,*,custom=False):
    return dict(familyName='Fixture family ignored for identity',postScriptName=ps,isCustomFont=custom,glyphCount=1)
good=deepcopy(s); session=Session([glyph('FixtureA'),glyph('FixtureB')])
font.verify_rendered_font(Page(session),{'installed_CJK_font':good})
assert good['rendering_observed'] and session.detached
assert not good['visible_node_font_usage'][0]['missing_codepoints']
assert {f['index'] for f in good['visible_node_font_usage'][0]['matched_faces']}=={0,2}
with_malformed=deepcopy(filtered);session=Session([glyph('FixtureA'),glyph('FixtureB')])
font.verify_rendered_font(Page(session),{'installed_CJK_font':with_malformed})
assert with_malformed['rendering_observed'] and session.detached
results.append(dict(name='CDP_fixture_valid_faces_with_and_without_malformed_excluded_rows',result='PASS',subcases=2,real_browser=False))

ambiguous,*_=attempt('ambiguous-PS',duplicate_ps=True)
untrusted_duplicate,*_=attempt('untrusted-PS-duplicate',extra=line('/tmp/untrusted-font.ttf',0,'Excluded font','FixtureA',POINTS))
for case,selection,fonts in [
    ('missing-node-char',s,[glyph('FixtureA')]),
    ('unknown-PS',s,[glyph('Unknown')]),
    ('custom-font',s,[glyph('FixtureA',custom=True),glyph('FixtureB')]),
    ('ambiguous-PS',ambiguous,[glyph('FixtureA')]),
    ('untrusted-PS-duplicate',untrusted_duplicate,[glyph('FixtureA'),glyph('FixtureB')])]:
    selection=deepcopy(selection);session=Session(fonts)
    try:font.verify_rendered_font(Page(session),{'installed_CJK_font':selection})
    except AssertionError: pass
    else:raise AssertionError(case+' unexpectedly accepted')
    assert not selection['rendering_observed'] and session.detached and selection['visible_node_font_usage']
results.append(dict(name='CDP_missing_unknown_custom_or_ambiguous_sources_refused_and_observations_kept',result='PASS',subcases=5,real_browser=False))

for case,clock in [('last-node-late',[0,1,6]),('detach-late',[0,1,2,6])]:
    selection=deepcopy(s);session=Session([glyph('FixtureA'),glyph('FixtureB')])
    with patch.object(font.time,'monotonic',side_effect=clock):
        try:font.verify_rendered_font(Page(session),{'installed_CJK_font':selection})
        except font.BudgetRefused:pass
        else:raise AssertionError(case+' unexpectedly accepted')
    assert not selection['rendering_observed'] and session.detached and selection['visible_node_font_usage']
results.append(dict(name='last_node_or_detach_crossing_same5s_clock_refused_without_success_flag',result='PASS',subcases=2,real_browser=False))

old=subprocess.check_output(['git','show',BASELINE+':scripts/fictional_park_restart_browser_once.py'],text=True)
new=Path(font.__file__).read_text()
assert old[old.index('def readonly_store('):]==new[new.index('def readonly_store('):]
assert old[old.index('class Deadline:'):old.index('def covers(')]==new[new.index('class Deadline:'):new.index('def ui_codepoints(')]
subprocess.run(['git','diff','--quiet',BASELINE,'--','scripts/fictional_park_browser_once.py','.github/workflows/fictional-park-browser-once.yml','src','tests'],check=True)
results.append(dict(name='original_business_recovery_Deadline_base_workflow_src_tests_bytes_unchanged',result='PASS'))

output=dict(source_sha256=sha256(Path(font.__file__).read_bytes()).hexdigest(),results=results,
    required_codepoints=683,services_started=False,browser_started=False,CI_started=False,
    warning='CDP records above are pure injected fixtures; rendering_observed in a fixture is not actual Chrome evidence')
(ROOT/'fixture-checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(output,ensure_ascii=False,indent=2))
