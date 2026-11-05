// Standalone concept demonstration. No database, credentials or backend launch.
using System;
using System.Drawing;
using System.Globalization;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class DemoWindow : Form
{
    const string Origin = "https://parkweave.demo";
    readonly WebView2 web = new WebView2();
    readonly Label loading = new Label();
    readonly string captureDir;
    readonly string profileDir;
    readonly HashSet<string> completedExports = new HashSet<string>();
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    readonly Timer watchdog = new Timer();
    bool capturing;
    bool testingExports;
    string phase="BOOTSTRAP";
    ulong documentNavigation;
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int cx,int cy,uint flags);
    internal DemoWindow(string capture,string profileOverride)
    {
        captureDir=capture;
        profileDir=profileOverride??(capture==null ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"ParkWeave","ProductDemo","WebView") : Path.Combine(capture,"_webview-profile"));
        Text="园合 ParkWeave";
        AutoScaleMode=AutoScaleMode.None;
        ClientSize=new Size(1440,900);MinimumSize=new Size(860,580);
        StartPosition=capture==null?FormStartPosition.CenterScreen:FormStartPosition.Manual;
        if(capture==null)WindowState=FormWindowState.Maximized;
        if(capture!=null){Location=new Point(0,0);ShowInTaskbar=false;}
        Font=new Font("Microsoft YaHei UI",10);BackColor=Color.FromArgb(237,243,252);
        string icon=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"ParkWeave.ico");
        if(File.Exists(icon))Icon=new Icon(icon);
        web.Dock=DockStyle.Fill;Controls.Add(web);
        loading.Dock=DockStyle.Fill;loading.TextAlign=ContentAlignment.MiddleCenter;
        loading.Text="正在打开园合工作台…";Controls.Add(loading);loading.BringToFront();
        Shown+=async delegate {await OpenWorkspace();};
        FormClosed+=delegate {watchdog.Stop();watchdog.Dispose();web.Dispose();};
        if(captureDir!=null){watchdog.Interval=45000;watchdog.Tick+=delegate {watchdog.Stop();Fail("演示截图超时。",new TimeoutException());};watchdog.Start();}
    }
    protected override bool ShowWithoutActivation {get{return captureDir!=null;}}
    protected override CreateParams CreateParams
    {
        get {CreateParams p=base.CreateParams;if(captureDir!=null)p.ExStyle|=0x08000080;return p;}
    }
    async Task OpenWorkspace()
    {
        try
        {
            Directory.CreateDirectory(profileDir);
            var environment=await CoreWebView2Environment.CreateAsync(null,profileDir);
            await web.EnsureCoreWebView2Async(environment);
            var core=web.CoreWebView2;
            core.Settings.AreDevToolsEnabled=false;
            core.Settings.AreDefaultContextMenusEnabled=false;
            core.Settings.IsWebMessageEnabled=false;
            core.SetVirtualHostNameToFolderMapping("parkweave.demo",Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"Web"),CoreWebView2HostResourceAccessKind.DenyCors);
            core.NavigationStarting+=delegate(object sender,CoreWebView2NavigationStartingEventArgs e){if(IsWorkspace(e.Uri))documentNavigation=e.NavigationId;else e.Cancel=true;};
            core.NewWindowRequested+=delegate(object sender,CoreWebView2NewWindowRequestedEventArgs e){e.Handled=true;};
            core.PermissionRequested+=delegate(object sender,CoreWebView2PermissionRequestedEventArgs e)
            {
                Uri requested;
                bool own=Uri.TryCreate(e.Uri,UriKind.Absolute,out requested)&&requested.GetLeftPart(UriPartial.Authority)==Origin&&IsWorkspace(core.Source);
                e.State=own&&e.PermissionKind==CoreWebView2PermissionKind.MultipleAutomaticDownloads?CoreWebView2PermissionState.Allow:CoreWebView2PermissionState.Deny;
            };
            core.AddWebResourceRequestedFilter("*",CoreWebView2WebResourceContext.All);
            core.WebResourceRequested+=delegate(object sender,CoreWebView2WebResourceRequestedEventArgs e)
            {
                Uri uri;
                if(!e.Request.Uri.StartsWith("blob:"+Origin+"/",StringComparison.Ordinal)&&(!Uri.TryCreate(e.Request.Uri,UriKind.Absolute,out uri)||uri.Scheme!="https"||uri.Host!="parkweave.demo"))
                    e.Response=environment.CreateWebResourceResponse(new MemoryStream(new byte[0]),403,"Blocked","Content-Type: text/plain");
            };
            core.DownloadStarting+=SaveDemonstrationFile;
            core.NavigationCompleted+=async delegate(object sender,CoreWebView2NavigationCompletedEventArgs e)
            {
                if(documentNavigation==0||e.NavigationId!=documentNavigation)return;
                if(!e.IsSuccess){Fail("页面未能完成加载",null,e.WebErrorStatus.ToString());return;}
                loading.Visible=false;
                if(captureDir!=null&&!capturing){capturing=true;await CaptureFrames();}
            };
            if(captureDir!=null)
            {
                SetWindowPos(Handle,new IntPtr(1),0,0,0,0,0x13);
            }
            core.Navigate(Origin+"/index.html");
        }
        catch(Exception error){Fail("工作台未能打开，请确认本机 WebView2 运行组件可用。",error);}
    }
    void SaveDemonstrationFile(object sender,CoreWebView2DownloadStartingEventArgs e)
    {
        e.Cancel=true;
        if(web.Source==null||!IsWorkspace(web.Source.AbsoluteUri)||!e.DownloadOperation.Uri.StartsWith("blob:"+Origin+"/",StringComparison.Ordinal))return;
        if(captureDir!=null)
        {
            if(!testingExports)return;
            string name=Path.GetFileName(e.ResultFilePath);
            string[] allowed={"ParkWeave-01-办理方案.md","ParkWeave-02-材料清单.md","ParkWeave-03-资源组合.json","ParkWeave-04-办理记录.json","ParkWeave-05-案例成果.html"};
            if(Array.IndexOf(allowed,name)<0)return;
            string folder=Path.Combine(captureDir,"outputs");Directory.CreateDirectory(folder);
            string target=Path.Combine(folder,name);if(File.Exists(target))return;
            var operation=e.DownloadOperation;
            operation.StateChanged+=delegate {if(operation.State==CoreWebView2DownloadState.Completed)completedExports.Add(name);};
            e.ResultFilePath=target;e.Handled=true;e.Cancel=false;return;
        }
        var deferral=e.GetDeferral();
        BeginInvoke(new Action(delegate {
            try{using(var dialog=new SaveFileDialog())
            {
                dialog.Title="保存办理文件";dialog.FileName=Path.GetFileName(e.ResultFilePath);
                dialog.Filter="演示文件|*.md;*.json;*.html;*.txt|所有文件|*.*";dialog.OverwritePrompt=true;
                if(dialog.ShowDialog(this)==DialogResult.OK){e.ResultFilePath=dialog.FileName;e.Handled=true;e.Cancel=false;}
            }}finally{deferral.Complete();}
        }));
    }
    async Task CaptureFrames()
    {
        try
        {
            phase="CAPTURE_FRAMES";
            for(int i=0;i<30;i++)
            {
                if(await web.CoreWebView2.ExecuteScriptAsync("document.body.dataset.demoReady === 'true'")=="true")break;
                if(i==29)throw new InvalidOperationException("DEMO_DOCUMENT_NOT_READY");
                await Task.Delay(100);
            }
            string[] frames={"goal","plan","materials","resources","conflict","dispatch","offer","accepted","receipt","complete"};
            double scale;
            if(Double.TryParse(await web.CoreWebView2.ExecuteScriptAsync("devicePixelRatio"),NumberStyles.Float,CultureInfo.InvariantCulture,out scale)&&scale>0)
                web.ZoomFactor=1.0/scale;
            await Task.Delay(250);
            using(var file=new StreamWriter(new FileStream(Path.Combine(captureDir,"before-replay-state.json"),FileMode.CreateNew)))
                file.Write(await web.CoreWebView2.ExecuteScriptAsync("window.ParkWeaveDemo.state()"));
            for(int i=0;i<frames.Length;i++)
            {
                await web.CoreWebView2.ExecuteScriptAsync("window.ParkWeaveDemo.replay("+json.Serialize(frames[i])+")");
                await Task.Delay(650);
                using(var file=new FileStream(Path.Combine(captureDir,(i+1).ToString("00")+"-"+frames[i]+".png"),FileMode.CreateNew))
                    await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,file);
            }
            string dimensions=await web.CoreWebView2.ExecuteScriptAsync("({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scope:'NATIVE_WEBVIEW2_PRESET_DEMO_NOT_BACKEND'})");
            using(var file=new StreamWriter(new FileStream(Path.Combine(captureDir,"native-capture.json"),FileMode.CreateNew)))file.Write(dimensions);
            phase="DEMO_EXPORTS";testingExports=true;
            await web.CoreWebView2.ExecuteScriptAsync("document.querySelector('#demo-export-menu').click()");
            string[] kinds={"plan","materials","resources","record","report"};
            for(int i=0;i<kinds.Length;i++)
            {
                await web.CoreWebView2.ExecuteScriptAsync("document.querySelector('#demo-dialog [data-kind=\""+kinds[i]+"\"]').click()");
                for(int wait=0;completedExports.Count<i+1;wait++)
                {
                    if(wait>=30)throw new InvalidOperationException("DEMO_EXPORT_NOT_COMPLETED");
                    await Task.Delay(100);
                }
            }
            testingExports=false;
            using(var file=new StreamWriter(new FileStream(Path.Combine(captureDir,"native-exports.json"),FileMode.CreateNew)))
                file.Write(json.Serialize(new {scope="NATIVE_BLOB_DOWNLOAD_TO_FIXED_TEST_DIRECTORY",count=completedExports.Count,files=completedExports}));
            Environment.ExitCode=0;Close();
        }
        catch(Exception error){Fail("演示截图未完成。",error);}
    }
    static bool IsWorkspace(string value)
    {
        Uri uri;return Uri.TryCreate(value,UriKind.Absolute,out uri)&&uri.Scheme=="https"&&uri.Host=="parkweave.demo"&&uri.IsDefaultPort&&uri.UserInfo.Length==0&&uri.AbsolutePath=="/index.html"&&uri.Query.Length==0;
    }
    void Fail(string message,Exception error,string navigationStatus=null)
    {
        loading.Text=message;loading.Visible=true;loading.BringToFront();
        if(captureDir!=null)
        {
            try{File.WriteAllText(Path.Combine(captureDir,"capture-failure.json"),json.Serialize(new {error_type=error==null?"NavigationFailure":error.GetType().Name,hresult=error==null?0:error.HResult,navigation_status=navigationStatus,phase=phase,export_count=completedExports.Count}));}catch{}
            Environment.ExitCode=2;Close();
        }
    }
}

internal static class Program
{
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr value);
    [STAThread] static void Main(string[] args)
    {
        try{SetProcessDpiAwarenessContext(new IntPtr(-4));}catch{}
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        string capture=null;
        string profile=null;
        if((args.Length==2||args.Length==4)&&args[0]=="--capture-dir")
        {
            capture=Path.GetFullPath(args[1]);Directory.CreateDirectory(capture);
            if(args.Length==4){if(args[2]!="--profile-dir"){Environment.ExitCode=2;return;}profile=Path.GetFullPath(args[3]);}
        }
        else if(args.Length!=0){Environment.ExitCode=2;return;}
        Application.Run(new DemoWindow(capture,profile));
    }
}
