"""Build the isolated Windows concept demo from official locked WebView2 SDK."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,zipfile,sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.windows_desktop.build import SDK_SHA,LOADER_SHA

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():raise ValueError('NEW_DEMO_OUTPUT_REQUIRED')
    sdk=ROOT/'.cache/windows-desktop/assets/microsoft.web.webview2.1.0.3537.50.nupkg'
    if digest(sdk)!=SDK_SHA:raise ValueError('OFFICIAL_LOCKED_SDK_REQUIRED')
    compiler=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.is_file():raise ValueError('WINDOWS_FRAMEWORK_COMPILER_REQUIRED')
    out.mkdir(parents=True);web=out/'Web';web.mkdir()
    names={'build/native/x64/WebView2Loader.dll':'WebView2Loader.dll',
        'lib/net462/Microsoft.Web.WebView2.Core.dll':'Microsoft.Web.WebView2.Core.dll',
        'lib/net462/Microsoft.Web.WebView2.WinForms.dll':'Microsoft.Web.WebView2.WinForms.dll',
        'LICENSE.txt':'WebView2-SDK-LICENSE.txt'}
    with zipfile.ZipFile(sdk) as archive:
        for src,dst in names.items():(out/dst).write_bytes(archive.read(src))
    if digest(out/'WebView2Loader.dll')!=LOADER_SHA:raise ValueError('OFFICIAL_LOADER_REQUIRED')
    app=ROOT/'src/parkweave'
    for src,dst in [('demo.html','index.html'),('workspace_design.css','workspace_design.css'),('demo-workspace.css','demo-workspace.css'),('demo-workspace.js','demo-workspace.js')]:shutil.copyfile(app/src,web/dst)
    (web/'assets').mkdir();shutil.copyfile(app/'assets/parkweave-mark-128.png',web/'assets/parkweave-mark-128.png')
    shutil.copyfile(app/'assets/parkweave.ico',out/'ParkWeave.ico')
    source=Path(__file__).with_name('ParkWeaveDemo.cs');exe=out/'ParkWeave演示版.exe'
    command=[str(compiler),'/nologo','/utf8output','/target:winexe','/platform:x64','/optimize+',
        '/out:'+str(exe),'/win32icon:'+str(out/'ParkWeave.ico'),'/r:System.Windows.Forms.dll',
        '/r:System.Drawing.dll','/r:System.Web.Extensions.dll',
        '/r:'+str(out/'Microsoft.Web.WebView2.Core.dll'),'/r:'+str(out/'Microsoft.Web.WebView2.WinForms.dll'),str(source)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=90)
    if result.returncode:
        (out/'compile-error.txt').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('DEMO_COMPILE_FAILED_SEE_OUTPUT')
    readme='园合 ParkWeave 产品演示\n\n双击 ParkWeave演示版.exe。请保留同目录 DLL 和 Web 文件夹。\n\n这是合成案例与本地预设流程演示，不连接真实园区、模型、预约或支付系统。\n普通使用不需要浏览器、终端、Python 或数据库。\n需要 Windows 10/11 x64、.NET Framework 4.8 和 Microsoft WebView2 Runtime。\n\n本地演示进度保存在当前 Windows 用户的 LocalAppData/ParkWeave/ProductDemo/WebView。\n页面可重置演示案例；不会删除已导出的文件。\n'
    (out/'使用说明.txt').write_text(readme,encoding='utf-8-sig')
    manifest=dict(scope='STANDALONE_WINDOWS_SYNTHETIC_CONCEPT_DEMO_NOT_BACKEND_ACCEPTANCE',
        sdk_sha256=SDK_SHA,compiler_sha256=digest(compiler),host_source_sha256=digest(source),
        files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(out.rglob('*')) if p.is_file()})
    (out/'demo-build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(out),exe=str(exe),files=len(manifest['files']),scope=manifest['scope']),ensure_ascii=False))

if __name__=='__main__':main()
