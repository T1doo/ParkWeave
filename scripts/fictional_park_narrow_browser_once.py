"""Exact run9: desktop Chrome 390px viewport, new synthetic input; no cold replay."""
from copy import deepcopy
from hashlib import sha256
import json
import time

NEW_INPUT = dict(
    goal='SYNTHETIC 青禾科创园 / 云杉智造：9台温湿度仪月检资料整理（390px新输入，全部虚构）',
    request='SYNTHETIC 林岚新申请9台温湿度仪月检资料整理；本次型号和数量独立，仅本地模拟，不申请正式资质或真实设备。',
    need_summary='SYNTHETIC 新事项独立诉求：9台温湿度仪的本月检验资料，由林岚提交、周禾审核、许辰办理；本次独立提交月检资料。',
    material_outline='SYNTHETIC 本次9台温湿度仪独立材料目录：型号清单、月检记录说明、温湿度记录索引。全部虚构，不复用旧材料，不证明资格或履约。',
    receipt='SYNTHETIC 许辰已整理本次9台温湿度仪月检资料目录；仅本地模拟，无真实检验、外部受理或线下履约。',
    receipt_source='SYNTHETIC 390px新事项9台温湿度仪人工回执 v1')
CAPTURE_NAMES = frozenset(('01-narrow-guide','02-narrow-new-materials','03-narrow-new-plan',
    '04-narrow-new-receipt','05-narrow-new-results','06-narrow-old-retained'))
PUBLIC_FILES = frozenset({n+'.png' for n in CAPTURE_NAMES} | {'first-case-record-pack.txt','result.json'})
CAPTURE_SCRIPT = """(() => {
 const state=window.__parkNarrow={events:[],overflow:false,stage:'LOAD'};
 document.addEventListener('click',event=>{
  const element=event.target.closest?.('button,input,select,textarea,a,summary');
  if(!element||!event.isTrusted)return;
  if(state.events.length>=600){state.overflow=true;return;}
  const r=element.getBoundingClientRect();
  const x=Math.min(innerWidth-1,Math.max(0,r.x+r.width/2));
  const y=Math.min(innerHeight-1,Math.max(0,r.y+r.height/2));
  const hit=document.elementFromPoint(x,y);
  state.events.push({stage:state.stage,id:element.id,tag:element.tagName,
   action:element.dataset.serviceAction||'',trusted:true,viewport_width:innerWidth,
   viewport_height:innerHeight,document_width:document.documentElement.scrollWidth,
   x:r.x,y:r.y,width:r.width,height:r.height,
   hit:!!hit&&(element===hit||element.contains(hit))});
 },true);
})();"""


def validate_probe(probe):
    assert probe['viewport_width']==390, 'narrow viewport changed'
    assert probe['document_width']<=390, 'horizontal document overflow'
    if 'width' in probe:
        assert probe['width']>0 and probe['height']>0, 'zero-area control'
        assert probe['x']>=-1 and probe['x']+probe['width']<=391, 'control crosses viewport horizontally'
        assert 0<=probe['y']+probe['height']/2<=probe['viewport_height'], 'control outside vertical viewport'
        assert probe['hit'], 'control is occluded'


class Narrow:
    viewport=dict(width=390,height=1000)
    fixed_input_text='\n'.join(NEW_INPUT.values())

    def __init__(self,report,public,started):
        self.report,self.public,self.started=report,public,started
        self.data=report['narrow']=dict(scope='DESKTOP_CHROME_390_VIEWPORT_NOT_PHONE',
            inputs=NEW_INPUT,checkpoints=[],controls=[],trusted_clicks=[],font_observations=[])
        report.update(scope='FICTIONAL_PARK_NARROW_NEW_INPUT',cold_restart=False,cancel_scope='NOT_EXERCISED')

    def require(self,seconds=0):
        # 270s work +90s original stop/context/publication reserve. No reset or shortened waits.
        assert time.monotonic()+seconds<=self.started+270, 'narrow270s work reservation exhausted'

    def work_complete(self):
        self.require(0)
        self.data['work_completion_seconds']=round(time.monotonic()-self.started,3)

    def closing_reservation(self):
        assert time.monotonic()+20<=self.started+360, 'narrow final context/publication reservation exhausted'

    def install(self,context):
        context.add_init_script(CAPTURE_SCRIPT)

    def checkpoint(self,page,label):
        self.require(15)
        probe=page.evaluate("""label=>{const s=window.__parkNarrow;s.stage=label;
          return {viewport_width:innerWidth,viewport_height:innerHeight,
           document_width:document.documentElement.scrollWidth,events:s.events.splice(0),overflow:s.overflow};}""",label)
        events=probe.pop('events')
        self.data['checkpoints'].append(dict(stage=label,**probe))
        assert not probe['overflow'], 'narrow click evidence bound exceeded'
        self.data['trusted_clicks'].extend(events)
        assert len(self.data['trusted_clicks'])<=600
        for row in self.data['trusted_clicks']:validate_probe(row)
        validate_probe(probe)
        assert len(self.data['checkpoints'])<=160

    def before(self,page,selector):
        from playwright.sync_api import expect
        self.require(45)
        target=page.locator(selector)
        target.scroll_into_view_if_needed(timeout=15000)
        expect(target).to_be_visible(timeout=15000);expect(target).to_be_enabled(timeout=15000)
        probe=target.evaluate("""element=>{const r=element.getBoundingClientRect();
          const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
          return {viewport_width:innerWidth,viewport_height:innerHeight,document_width:document.documentElement.scrollWidth,
           x:r.x,y:r.y,width:r.width,height:r.height,hit:!!hit&&(element===hit||element.contains(hit))};}""")
        self.data['controls'].append(dict(stage=self.report['stage'],selector=selector,**probe))
        validate_probe(probe)
        assert len(self.data['controls'])<=120
        self.checkpoint(page,self.report['stage'])

    def font_observation(self,page,label):
        from scripts.fictional_park_restart_browser_once import verify_rendered_font
        self.require(15)
        entry=dict(stage=label,complete=False,
            scope='Actual named page viewport nodes;not all codepoints per-glyph pixel acceptance',
            nodes=[])
        self.data['font_observations'].append(entry)
        assert len(self.data['font_observations'])<=3
        selected=self.report['installed_CJK_font']
        selected['visible_node_font_usage']=[]
        selected['rendering_observed']=False
        try:
            verify_rendered_font(page,self.report)
            entry['complete']=True
        finally:
            selected=self.report['installed_CJK_font']
            entry['nodes']=deepcopy(selected.get('visible_node_font_usage',[]))
            selected['rendering_observation_stage']=label
            selected['rendering_observation_scope']=entry['scope']

    def guide_ready(self,page,report):
        self.checkpoint(page,'NARROW_GUIDE_390')
        self.font_observation(page,'NARROW_GUIDE_390')

    def separation(self,old,new,before,after,new_history,result,receipt,txt):
        for key in ('preparation_id','case_id','run_id'):assert old[key]!=new[key]
        assert before==after, 'old Case history changed while handling new input'
        assert after['preparations'][0]['service_case_plan'] is None
        assert not after['service_dispatches'] and not after['service_receipt_steps']
        assert not any(e['payload'].get('material_reuse') for e in new_history['preparation_events'])
        materials=new_history['preparation_evidence']
        assert {m['slot']:m['text'] for m in materials}=={k:NEW_INPUT[k] for k in ('need_summary','material_outline')}
        assert len(materials)==2 and not ({str(m['id']) for m in before['preparation_evidence']} & {str(m['id']) for m in materials})
        assert result['original_request']==NEW_INPUT['goal'] and result['current_request']==NEW_INPUT['request']
        assert receipt['current_receipt']['text']==NEW_INPUT['receipt']
        assert receipt['current_receipt']['source_label']==NEW_INPUT['receipt_source']
        for obj in (result,receipt['step']):
            for key in ('preparation_id','case_id','run_id'):assert str(obj[key])==new[key]
        for key in ('preparation_id','case_id','run_id','plan_id'):assert new[key] in txt and old.get(key,'NOT_AN_ID') not in txt
        assert NEW_INPUT['goal'] in txt and NEW_INPUT['request'] in txt
        digest=lambda obj:sha256(json.dumps(obj,sort_keys=True,default=str).encode()).hexdigest()
        self.data['separation']=dict(old=old,new=new,old_history_before_sha256=digest(before),
            old_history_after_sha256=digest(after),old_history_scope='declared case_history projection,not all DB',
            new_evidence_ids=[str(m['id']) for m in materials],new_materials_exact=True,new_request_exact=True,
            receipt_exact=True,TXT_exact_ids=True,old_ADOPT_or_plan_created=False)


if __name__=='__main__':
    from scripts.fictional_park_browser_once import main
    raise SystemExit(main(narrow_candidate=True))
