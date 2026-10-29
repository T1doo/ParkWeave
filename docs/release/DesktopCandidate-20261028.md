# Windows 独立桌面候选

正常桌面入口是包根的 `ParkWeave.exe`，不是 Chrome/Edge 标签页。EXE 有独立 Win32 窗口、标题和任务栏身份；无参数运行 `ParkWeave.cmd` 也只转交本包 EXE，缺少 EXE 则明确拒绝。显式 CLI 参数保留给工程诊断。

宿主的私有桥固定使用本包 `python.exe -I -B`，以 `CREATE_NO_WINDOW` 启动并只继承指定的匿名管道。这样沿用原入口只接受包内 `python.exe` 的校验，也保留桥所需的标准输入输出；不使用可能没有标准流的 `pythonw.exe`，不放宽解释器路径或清单校验。

程序目录与私有资料安装目录必须分开。保持整个程序包原样，运行其中的 EXE，在窗口填写已有私有安装目录，或明确选择首次新建及两个回环端口。首次新建需给六个企业/专员账号设置不同密码；密码仅通过本次子进程的私有继承管道进入原安装入口，不进参数、环境、日志、文件或网页消息。网页仍要求用户明确选择账号并登录，不默认提供角色 bearer。

已有合法安装第一次使用桌面时，须显式勾选“首次在已有安装使用桌面”。这仅独占建立该安装、该 Windows 用户的受保护 WebView2 profile 与 DPAPI 目录身份绑定，不重建数据库或角色。不勾选时只读原绑定，缺失/损坏/目录 ID 改变会拒绝，不把读取失败变成初始化。之后重开不要再次勾选，不删除 profile；其中保存非秘密的原请求句柄。主前端与已认可的一屏布局相同。

桌面使用已有的官方 x64 WebView2 Runtime，明确定位机器级 EdgeWebView 安装目录，拒绝浏览器/调试/profile 环境或策略覆盖。缺失、来源或离线签名链不能核验时停止，不安装/修复 Runtime、不启动 Edge 浏览器、不改默认浏览器或注册表。SDK Loader 由官方已锁 NuGet 提取，随包带原 BSD 许可。

只有原 Controller 完成真实 RUNNING、原 workspace 校验后，私有后台桥才通知宿主打开当前回环 origin；不是读取 stdout URL 或 `/health` 判定。宿主在 Python 启动前核不可变目录完整成员与全部已冻结文件，持有原文件及目录；桥接模块从原路径加载。页面无 host objects/原生脚本桥，外部请求、导航、弹窗、协议启动和未请求权限被拒绝。材料文本下载仅进入本实例 profile 的受保护 `Downloads`，不自动打开外部程序。

关闭窗口先关闭 WebView2 控制器，等待原 browser HANDLE 对应的退出事件以及本次 UI Job 剩余进程退出，再发正常停止字节，最后由原 Controller 停 API/worker/PG并回读停机结果。管道 EOF、启动异常、未知关闭或等待超时进入 UNKNOWN，不自动重发/重开或删资料。仅本次创建的 Job 管理本次进程树，不能按 PID 或进程名清理其他程序。进程终止、profile 持久性、窗口像素和操作均仍须 Windows 实跑验证。

此片不是 Windows 成品签收：OWNER、fixed journal、loader 三门保持关闭；源码/协议通过、真实 AMD64 GUI PE 编译或 Runtime 已存在均不能使 `usable_product` 为 true。原 `5a` native harness 仍固定其旧包，不能拿它验证新版桌面包。当前包身份以本轮独立 delivery manifest 与 SHA256 为准；不覆盖旧候选，不公开发布。

工程来源：

- SDK：Microsoft.Web.WebView2 1.0.3537.50，NuGet SHA256 `5ea526bbd728adda0da4d31219267e96460494a427e4894c4e09d9f320f4b9aa`，Loader SHA256 `2f965e10aed3b356a408978a0e6d74eb86e3e722dd008fa9ad39f68884479e85`。
- 编译：官方 Zig 0.15.2 Linux 发行包 SHA256 `02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239`，离线逐成员验证发行树、固定编译环境；不执行生成的 Windows 程序。
- [微软 WebView2 分发说明](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)、[嵌入安全](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security)、[用户资料目录](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder)、[EventRegistrationToken ABI](https://learn.microsoft.com/en-us/windows/win32/api/eventtoken/ns-eventtoken-eventregistrationtoken)。
