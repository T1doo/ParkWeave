# ParkWeave 页面精致化候选与 run26 启动失败原件

源码 `4a1c52826059991df3586679745670077bb4cefc`，基线 `cf936f8d3bc2f66bf5401edd661a84ad6769c95d`。[run26 / attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39829147881)，job `120000330770`，正式终态 **FAIL / exit1**。本候选已正常开发分支推送、独审，未获实际像素验收。

## 实际产品改动

原三工作区和导览页共用绿/暖白色阶、字号、边框、圆角与表单节奏；桌面侧栏三工作区、窄屏原三tab；减轻内层section的重复白卡和留白，记录编号保持12px及完整换行；统一只读/主动作/禁用/错误与focus细节。导览桌面角色按钮成组、窄屏保留顺序，长流程改轻量分隔。全部业务JS和style外HTML字节精确不变；原hidden强制规则、合成声明、原状态/权限和业务按钮不改。source-binding.json保留前后摘要，静态preflight核756源码指纹，不是测试执行或浏览器PASS。

审查依据是原产品§3及已归档真实run23套层计划卡片和run13导览图；这些旧图不是新版截图。新版尚无前后实际截图，不能宣称“全页面已精美验收”。

## 计划中的最小真实浏览器范围（本次全未执行）

原空初态服务/协同/资源与导览，1200/390px、焦点、禁用与原JS受控403加载/拒绝、非法文件反馈。为核有数据卡片，原run23公开result按SHA256 `0ef683ef62243d49b397abcf064a4714ec7cacfb5f42726d2c1c676b00cf8952` 精确取 `fresh_roles[0].plans[0]`，原renderer历史合成视图回放，不调用当前业务、不点击生成的业务按钮，不作当前权限/健康或业务恢复结论。目标结果与核对包正文没有填假数据，也不在其数据展示验收内。最多8原PNG+result、失败预留，10文件/8MiB门不扩。

## 官方实际失败

依赖和已批准固定Noto字体阶段成功。浏览器step在 BrowserType.launch 的15000ms门超时，只记 `<launched> pid=2466` 与stable-channel warning；没有明确sandbox拒绝。chromium_sandbox=True仅为请求参数，本次尚未验证sandbox实态。没有得到可用Browser对象，0页面、0GET/POST、0几何检查、0截图、0实际字体观察；静态684码点覆盖不是渲染。此失败不能判产品CSS错误，也不能猜是权限或font原因。

自有回放HTTP监听最终REFUSED、cleanup_errors为空；缺少browser_close=CLOSED，不能据此证明Chrome正常关闭或该子进程已确认退出。没有关sandbox、改权限/安全策略、换模型、额外业务调用或自动重跑。当前原因UNKNOWN，预算和源码保持供接续审查。

官方ZIP85915B，SHA256 `a130522fbe068ac8be8ae895761919749ef0ad3fcdb90e439b8dcac38c1fa616`，唯一成员result.json119206B，逐字相同。ci-original.log为官方job API完整解码全文162179B，SHA256 `5dc79ec3cef9e02b1cc04a286fd73a4590d81c211547d12eb9073274108e5803`，归档后与API内容逐字读回相等，包含完整最终化及job收尾，非截断CLI导出。run/job/API/artifact元数据保留；validation、preflight、source-binding、归档脚本及checksums是派生材料。stdout PENDING_FINALIZATION不当终态PASS，summary正文未独读。

旧run24失败、run25限定CSS通过均保留各自源码范围，不转签新版。Windows原生、LIVE、C0及正式来源门仍独立；AT31暂存，没有恢复信任根或新FULL入口。
