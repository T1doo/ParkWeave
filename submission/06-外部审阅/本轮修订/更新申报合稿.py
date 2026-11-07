
from pathlib import Path
from docx import Document
from docx.shared import Pt,Inches
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy
from zipfile import ZipFile,ZIP_DEFLATED
import json,re,hashlib
root=Path('submission');qa=root/'05-最终提交/排版检查';src=root/'05-最终提交/ParkWeave-项目申报书-审阅版-v3.docx'
d=Document(src);changes=json.loads((root/'06-外部审阅/本轮修订/正文替换映射.json').read_text(encoding='utf-8'))
def clean(line):return re.sub(r'^#+\s*','',line).replace('**','')
def para_before(anchor,text,bold=False):
 p=d.add_paragraph(text);p.paragraph_format.line_spacing=1.35;p.paragraph_format.space_after=Pt(5);p.paragraph_format.first_line_indent=Pt(0 if bold else 21);p.paragraph_format.keep_with_next=bold
 for r in p.runs:r.font.name='仿宋GB2312';r.font.size=Pt(10.5);r.bold=bold;r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'仿宋GB2312')
 anchor.addprevious(p._p)
def insert(anchor,body):
 lines=body.splitlines();i=0
 while i<len(lines):
  line=lines[i].strip()
  if not line:i+=1;continue
  if line.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    cells=[x.strip() for x in lines[i].split('|')[1:-1]]
    if not all(re.fullmatch('[-: ]+',x) for x in cells):rows.append(cells)
    i+=1
   table=d.add_table(rows=0,cols=len(rows[0]));table.autofit=False
   for ri,row in enumerate(rows):
    cells=table.add_row().cells
    for ci,value in enumerate(row):
     cells[ci].text=value;cells[ci].width=Inches(5.65/len(row))
     for p in cells[ci].paragraphs:
      p.paragraph_format.line_spacing=1.15
      for r in p.runs:r.font.name='仿宋GB2312';r.font.size=Pt(10.5);r.bold=ri==0;r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'仿宋GB2312')
    if ri==0:table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
   borders=OxmlElement('w:tblBorders')
   for side in ['top','left','bottom','right','insideH','insideV']:
    e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
   table._tbl.tblPr.append(borders);anchor.addprevious(table._tbl);continue
  para_before(anchor,clean(line),line.startswith('#'));i+=1
for change in changes:
 lines=[x.strip() for x in change['old'].splitlines() if x.strip()]
 first=clean(lines[0]);last=clean(lines[-1])
 ps=list(d.paragraphs)
 if first.startswith('|'):
  labels=[x.strip() for x in first.split('|')[1:-1]]
  starts=[t for t in d.tables if [c.text for c in t.rows[0].cells]==labels]
  assert len(starts)==1,(first,len(starts))
  begin=starts[0]._tbl
 else:
  starts=[p for p in ps if p.text==first];assert len(starts)==1,(first,len(starts))
  begin=starts[0]._p
 if lines[-1].startswith('|'):
  end=begin
  while end is not None and not end.tag.endswith('}tbl'):end=end.getnext()
  assert end is not None
 else:
  ends=[p for p in ps if p.text==last];assert len(ends)==1,(last,len(ends));end=ends[0]._p
 after=end.getnext();assert after is not None
 insert(begin,change['new'])
 node=begin
 while node is not after:
  nxt=node.getnext();node.getparent().remove(node);node=nxt
# Add the candidate comparison beside the impact explanation.
caption=next(p for p in d.paragraphs if p.text=='图 5 变化影响与修订方案设计')
anchor=caption._p.getnext()
p=d.add_paragraph();p.paragraph_format.keep_with_next=True;p.add_run().add_picture(str(root/'04-视频制作/审阅修订图/C04b-候选比较.png'),width=Inches(5.65));anchor.addprevious(p._p)
para_before(anchor,'图 5a 企业费用偏好与候选比较')
# Add concrete evidence matrix and output digest in appendix.
anchor=next(p._p for p in d.paragraphs if p.text=='案例材料与视频')
insert(anchor,'''### 材料与证据范围
| 材料 | 可核验内容 | 适用范围 |
| --- | --- | --- |
| Windows 本地窗口记录 | WebView2 页面、预设角色与导出体验 | 原生预设体验 |
| 本轮浏览器复核 | 费用偏好确认、资源确认、回执与归档 | 本地预设交互 |
| 五类输出 | 方案、材料、资源、事件与成果页 | 案例结构与状态 |
| 产品与技术图 | 完整产品机制和界面组织 | 方案设计 |
| 视频准备材料 | 分镜、图片、提示词与临时配音 | 待生成与成片核验 |
### 五类案例产物摘要
| 产物 | 可读内容 |
| --- | --- |
| 办理方案 | 40 人技术交流，场地、设备与接待准备，三步责任安排 |
| 材料清单 | 活动安排、接待要求、企业提供及核对状态 |
| 资源组合 | 多功能厅 A 与投影音响，资源参考小计 1,500 元 |
| 办理记录 | 活动保障准备范围、角色事件与确认状态 |
| 成果页 | 目标、材料、资源、回执与办理留痕 |
''')
anchor=d._element.body.sectPr
insert(anchor,'### 引用资料\n[1] 工业和信息化部，2026年4月10日，推动国家高新区高质量发展新闻发布会。\nhttps://www.miit.gov.cn/xwfb/xwfbh/bxwfbh/art/2026/art_1645f32c491a452489025bdb9430f490.html')
# Replace image bytes while keeping preserved template parts.
pairs=[
('04-视频制作/AI参考图/C01-园区总览/C01-v1.png','04-视频制作/审阅修订图/C01-v2.png'),
('04-视频制作/AI参考图/C02-企业机会/C02-v1.png','04-视频制作/审阅修订图/C02-v2.png'),
('04-视频制作/技术图/T01-技术架构.png','04-视频制作/审阅修订图/T01-v2.png'),
('04-视频制作/技术图/T02-部署接入.png','04-视频制作/审阅修订图/T02-v2.png'),
('04-视频制作/AI参考图/C04-变化影响/C04-v2.png','04-视频制作/审阅修订图/C04-v3.png'),
('04-视频制作/AI参考图/C08-跨园区/C08-v1.png','04-视频制作/审阅修订图/C08-v2.png'),
('04-视频制作/AI参考图/C03-方案推演/C03-v2.png','04-视频制作/审阅修订图/C03-v3.png'),
('04-视频制作/AI参考图/C06-研发设备/C06-v1.png','04-视频制作/审阅修订图/C06-v2.png'),
('04-视频制作/AI参考图/C07-企业入驻/C07-v1.png','04-视频制作/审阅修订图/C07-v2.png')]
replacement={hashlib.sha256((root/a).read_bytes()).hexdigest():(root/b).read_bytes() for a,b in pairs}
tmp=qa/'审阅修订临时.docx';d.save(tmp);out=root/'05-最终提交/ParkWeave-项目申报书-审阅版-v4.docx'
with ZipFile(src) as a,ZipFile(tmp) as b,ZipFile(out,'w',ZIP_DEFLATED) as z:
 for info in a.infolist():
  data=a.read(info.filename)
  if info.filename in ['word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml']:data=b.read(info.filename)
  if info.filename.startswith('word/media/'):data=replacement.get(hashlib.sha256(data).hexdigest(),data)
  z.writestr(info,data)
 for info in b.infolist():
  if info.filename not in a.namelist():z.writestr(info,b.read(info.filename))
print(out)
