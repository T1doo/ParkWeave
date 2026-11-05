"""Curate verified synthetic media; never include browser profiles or secrets."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,shutil,struct,zipfile

ROOT=Path(__file__).resolve().parents[2]
DOCS=ROOT/'docs/demo-delivery-20261106'
SHOTS=[('01-goal.png','01-目标表达.png'),('02-plan.png','02-方案编排.png'),('03-materials.png','03-资料与来源.png'),
       ('05-conflict.png','04-资源冲突.png'),('04-resources.png','05-资源组合.png'),('06-dispatch.png','06-专员派单.png'),
       ('07-offer.png','07-等待接单.png'),('08-accepted.png','08-执行中.png'),('09-receipt.png','09-回执核对.png'),('10-complete.png','10-事项归档.png')]

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def curate():
    source=DOCS/'native-clean-final-check/session-1'
    verification=json.loads((DOCS/'native-clean-final-check/verification.json').read_bytes())
    if not verification['process_restart_state_restored'] or any(r['exit_code']!=0 or r['exports']['count']!=5 for r in verification['results']):raise ValueError('VERIFIED_NATIVE_DEMO_REQUIRED')
    target=DOCS/'软件截图_1440x900';target.mkdir(exist_ok=True)
    prior=json.loads((target/'截图来源.json').read_bytes()) if (target/'截图来源.json').exists() else []
    prior_hash={row['file']:row['sha256'] for row in prior}
    mapping=[]
    for original,name in SHOTS:
        src=source/original
        if struct.unpack('>II',src.read_bytes()[16:24])!=(1440,900):raise ValueError('SAME_SIZE_PNG_REQUIRED')
        dst=target/name
        if dst.exists() and digest(dst)!=digest(src) and digest(dst)!=prior_hash.get(name):raise ValueError('EXISTING_SCREENSHOT_PROTECTED')
        shutil.copyfile(src,dst);mapping.append(dict(file=name,source=original,scope='ACTUAL_EXE_WEBVIEW2_PRESET_SYNTHETIC_DEMO',sha256=digest(dst)))
    (target/'截图来源.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return mapping

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path);p.add_argument('--output',type=Path);p.add_argument('--source-ref',default='LOCAL_SOURCE');p.add_argument('--curate-only',action='store_true');args=p.parse_args()
    curate()
    if args.curate_only:print('CURATED_NATIVE_SCREENSHOTS');return
    if args.app is None or args.output is None:raise ValueError('APP_AND_OUTPUT_REQUIRED')
    app=args.app.resolve();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT):raise ValueError('NEW_WORKSPACE_OUTPUT_REQUIRED')
    build=json.loads((app/'demo-build.json').read_bytes());copied=[]
    out.mkdir(parents=True)
    def copy(src,relative):
        dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);copied.append(relative)
    for name,row in build['files'].items():
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or not (app/name).resolve().is_relative_to(app):raise ValueError('SAFE_APP_LAYOUT_REQUIRED')
        if digest(app/name)!=row['sha256']:raise ValueError('FROZEN_DEMO_APP_CHANGED')
        copy(app/name,'软件/'+name)
    copy(app/'demo-build.json','软件/demo-build.json')
    for _,name in SHOTS:copy(DOCS/'软件截图_1440x900'/name,'视频素材/01-软件截图_1440x900/'+name)
    copy(DOCS/'软件截图_1440x900/截图来源.json','视频素材/01-软件截图_1440x900/截图来源.json')
    copy(DOCS/'output-preview/产品理念_设计示意.png','视频素材/02-产品理念_设计示意.png')
    copy(DOCS/'output-preview/案例成果页.png','视频素材/03-案例成果页.png')
    copy(DOCS/'interactive-clean/ParkWeave-交互操作参考.webm','视频素材/04-交互操作参考_含校验与冲突.webm')
    for src in sorted((DOCS/'interactive-clean/outputs').iterdir()):
        if src.is_file() and src.suffix in ('.md','.json','.html'):copy(src,'输出样例/'+src.name)
    copy(DOCS/'output-preview/案例二-培训对照.json','输出样例/案例二-20人培训对照.json')
    for name in ('先看这里.md','录制操作路线.md','90秒讲解提纲.md','给GPT的审阅提示词.txt'):copy(DOCS/name,name)
    copy(DOCS/'WindowsDemoVerification.json','验证记录/WindowsDemoVerification.json')
    meta=dict(scope='WINDOWS_PRODUCT_CONCEPT_DEMO_AND_SYNTHETIC_VIDEO_MATERIALS',source_ref=args.source_ref,
        real_backend_acceptance=False,real_model_call=False,real_external_booking=False,
        files={name:dict(bytes=(out/name).stat().st_size,sha256=digest(out/name)) for name in sorted(copied)})
    (out/'交付清单.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def archive(path,names,manifest_name,manifest):
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in sorted(names):z.write(out/name,name)
            z.writestr(manifest_name,json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    full=out.parent/'ParkWeave_演示与视频素材_20261106.zip';media=out.parent/'ParkWeave_视频素材_20261106.zip'
    archive(full,copied,'交付清单.json',meta)
    selected=[name for name in copied if not name.startswith('软件/')]
    archive(media,selected,'素材清单.json',{**meta,'files':{name:meta['files'][name] for name in selected}})
    result=dict(full=dict(path=str(full),bytes=full.stat().st_size,sha256=digest(full)),media=dict(path=str(media),bytes=media.stat().st_size,sha256=digest(media)),files=len(copied),source_ref=args.source_ref)
    (DOCS/'交付包记录.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
