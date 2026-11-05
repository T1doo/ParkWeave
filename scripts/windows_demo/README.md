# Windows 产品演示入口

此入口仅承载预设合成案例和本地交互状态，不启动原数据库/API/worker，也不替代原生后端验收。它用于视频、界面评审和产品理念展示。

## 构建

在 Windows x64、Python 3.12 和系统 .NET Framework 4.8 环境运行：

```powershell
python scripts/windows_demo/build_demo.py --output build/demo-video/new-candidate
```

输出目录必须不存在。构建器读取 `.cache/windows-desktop/assets/microsoft.web.webview2.1.0.3537.50.nupkg`，先核对原锁定 SDK/Loader SHA-256，再复制 net462 Core/WinForms 组件、许可证和前端文件，使用系统 `csc.exe` 生成独立 WinForms EXE。SDK 是固定版本官方 NuGet 包；不会自动安装组件或使用未知 DLL。

成品运行无需 Python/数据库，保留同目录 DLL、图标与 Web 文件夹。WebView2 Runtime 和 .NET Framework 是系统前提。

## 验证

`tests/demo_video_journey.cjs` 通过真实 Edge 浏览器点击本地演示页面，核对状态前置条件、角色展示、文件导出、第二场景和浏览器进程重开。本地开发静态服务器只用于浏览器测试；成品使用虚拟主机文件映射，不依赖该服务器。

应用内部捕获检查：

```powershell
ParkWeave演示版.exe --capture-dir <新的工作区目录> --profile-dir <专用演示测试配置目录>
```

该模式仅使用预设演示帧，自动截取自身渲染区并向固定测试目录导出五个文件，随后关闭。它不自动操作用户的“另存为”对话框，也不执行后台业务。普通模式的保存位置由用户选择。

浏览器配置目录、缓存和测试录制中间文件不应进入源码提交或交付包。`package_delivery.py` 使用明确文件清单打包，核对构建哈希及原生截图尺寸，排除这些配置文件。
