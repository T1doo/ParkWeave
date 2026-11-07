
from pathlib import Path
import csv,json,re,shutil,hashlib
root=Path('submission');v=root/'04-视频制作';review=root/'06-外部审阅/20261107';out=v/'审阅修订视频-v3';out.mkdir(exist_ok=True)
def ai(name):return v/'审阅修订图'/name
def old(name):return root/'03-截图与成果/01-主流程截图'/name
def n(name):return root/'03-截图与成果/05-审阅修订实录'/name
assets={
'S01':[(0,v/'AI参考图/A01-园区场景/A01-晨景-v1.png')],
'S02':[],
'S03':[(0,ai('C01-v2.png'))],'S04':[(0,ai('C02-v2.png'))],
'S05':[(0,old('01-目标表达.png'))],
'S06':[(0,ai('C05-v2.png'))],
'S07':[(0,ai('C03-v3.png'))],
'S08':[(0,old('05-资源组合.png')),(5,n('N01-主事项资源已确认.png'))],
'S09':[(0,old('06-专员派单.png')),(4,old('07-等待接单.png'))],
'S10':[(0,old('08-执行中.png')),(2,n('N05-活动保障准备回执待核对.png')),(4,n('N06-活动保障准备已归档.png'))],
'S11':[(0,n('N00-企业费用偏好待确认.png'))],
'S12':[(0,n('N00-企业费用偏好待确认.png')),(4,n('N07-偏好与方案比较.png'))],
'S13':[(0,ai('C04-v3.png'))],'S14':[(0,ai('C04b-候选比较.png'))],
'S15':[(0,n('N09-修订资源待确认.png')),(3,n('N02-修订资源已确认.png'))],
'S16':[(0,n('N10-回执退回与纠正.png')),(3,n('N11-修订回执v2待核对.png'))],
'S17':[(0,n('N03-首次归档-v1-回执v2.png')),(2,n('N12-重开事项待补充.png')),(5,n('N04-回执v3待企业核对.png'))],
'S18':[(0,n('N08-再次归档与历史.png')),(3,n('N13-原归档依据.png'))],
'S19':[(0,ai('C07-v2.png'))],'S20':[(0,ai('C06-v2.png'))],'S21':[(0,ai('C02-v2.png'))],
'S22':[(0,ai('T02-v2.png'))],'S23':[(0,ai('C08-v2.png'))],
'S24':[(0,v/'AI参考图/A01-园区场景/A01-夜景-v1.png')]}
with (review/'04_24镜头审阅与修订.csv').open(encoding='utf-8-sig',newline='') as f:shots=list(csv.DictReader(f))
with (review/'05_180秒修订剪辑台本.csv').open(encoding='utf-8-sig',newline='') as f:seconds=list(csv.DictReader(f))
assert len(shots)==24 and len(seconds)==180
frames=[];sources=[];voice=[]
for shot in shots:
 sid=shot['镜头'];folder=out/sid;folder.mkdir(exist_ok=True)
 shot['开始帧']=int(shot['起秒'])*25;shot['结束帧']=int(shot['止秒'])*25
 shot['占用帧']=int(shot['时长'])*25;shot['源片时长']='待生成或按静态素材剪辑';shot['生成状态']='NOT_RUN'
 if sid=='S08':shot['旁白建议']='预检后，核对当前资源状态，由企业明确确认组合。'
 if sid=='S13':shot['旁白建议']='系统区分保留、复验和候选替换，让有效安排继续沿用。'
 entries=[]
 for i,(time,p) in enumerate(assets[sid],1):
  assert p.is_file(),p
  dest=folder/f'{i:02}-{p.name}';shutil.copy2(p,dest)
  if p.with_suffix('.svg').is_file():shutil.copy2(p.with_suffix('.svg'),dest.with_suffix('.svg'))
  entries.append({'at':time,'path':str(dest.relative_to(out)).replace('\\','/')})
  sources.append({'shot':sid,'source':p.as_posix(),'file':dest.relative_to(out).as_posix(),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
 prompts=list((review/'H3替换提示词').glob(sid+'_*.txt'))
 if prompts:
  shutil.copy2(prompts[0],folder/'H3生成提示词.txt')
  if sid=='S06':shutil.copy2(ai('C05-clean-plate.png'),folder/'C05-clean-plate.png')
  if sid=='S13':
   for name in ['C04-clean-start.png','C04-clean-end.png']:shutil.copy2(ai(name),folder/name)
  mode='H3场景生成' if sid in ['S01','S02','S20','S24'] else '精确图层剪辑，H3材质可选'
 else:mode='原图或精确图层剪辑'
 shot['执行方式']=mode
 instructions=f'# {sid} 执行说明\n\n全片 {shot["起秒"]}–{shot["止秒"]} 秒，25fps，占用 {shot["占用帧"]} 帧。\n\n方式为 {mode}。\n\n{shot["具体修订"]}\n\n画面要求为 {shot["画面与运镜"]}。\n\n入镜为 {shot["入镜"]}。出镜为 {shot["出镜"]}。\n\n'
 for e in entries:instructions+=f'- 片段内 {e["at"]} 秒切入 [{Path(e["path"]).name}]({Path(e["path"]).name})。\n'
 if prompts:instructions+='\nH3仅生成情境或无字材质。精确汉字、金额、版本、箭头和品牌字版由后期叠加。上传映射见根目录H3使用说明。客户端参数需按实际支持核对。\n'
 else:instructions+='\n本镜使用原图、实际操作录屏或SVG编辑，按此说明剪辑即可。\n'
 (folder/'剪辑说明.md').write_text(instructions,encoding='utf-8')
 frames.append({'id':sid,'start':int(shot['起秒']),'end':int(shot['止秒']),'frames':entries,'title':shot['具体修订'],'transition':shot['出镜']})
 voice.append({'id':sid,'start':int(shot['起秒']),'end':int(shot['止秒']),'text':shot['旁白建议']})
with (out/'24镜头总表.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(shots[0]));w.writeheader();w.writerows(shots)
with (out/'180秒台本.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(seconds[0]));w.writeheader();w.writerows(seconds)
(out/'镜头素材.json').write_text(json.dumps(frames,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'旁白句表.json').write_text(json.dumps(voice,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'素材来源.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(review/'H3替换提示词/使用说明.md',out/'H3使用说明.md')
(out/'旁白与读音.md').write_text('# 统一旁白\n\n采用同一普通话声线。ParkWeave 读作 Park Weave，品牌中文读园合；UNKNOWN在中文讲解中读作依据不足。片尾全句从175秒起保持至180秒。\n\n'+'\n\n'.join(f'{x["id"]} · {x["start"]}–{x["end"]} 秒\n\n{x["text"]}' for x in voice),encoding='utf-8')
print('24 shot folders, six selectively enabled H3 prompts and 4500-frame timeline prepared.')
