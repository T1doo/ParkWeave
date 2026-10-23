# 协同工作区暖橙分区候选（尚未渲染）

基线 `dd12d91fe5d745ded7c1602d1284bca3222943fa`，沿原 F2 协同／资料／回执入口与用户“先功能分块，再精美配色”的要求。本轮没有浏览器、CI、PG、业务 API、真实模型、用户电脑操作或旧附件读取。run37 的父级四图限定 ACK 只属旧核心模板，不覆盖本候选。

## 实际产品变化

原协同页依靠三条横线连续堆放资料待办、分派、回执、通知、事项进度及运行核对。现在增加六个纯展示容器（一个 header、五个 div）和“资料准备与待办”标题：暖棕原页头、奶油主待办、浅沙分派／回执分区、蓝灰通知工具区及沙色运行核对。900px 以上两个同级办理区并列，各自列表保持一列；窄屏单列、动作全宽。三条原装饰横线仅被限定 CSS 隐藏，不隐藏警示或业务内容，不新增折叠、业务动作或展示成功数。

原 Run 访问入口保持在回执之后、通知之前，原隐藏权限门、内部表单、label 父子结构保留。所有原文本仍在，新增标题不是业务状态。原始状态徽标、LOADING／ERROR／DENIED、合成警告、disabled、焦点及减少动画规则未更改。暂无本候选真实宽窄图，布局、滚动高度及触控／键盘体验不能签收。

## 源码和实际检查

- 产品 web SHA256：`9711354a500e0940f1be9677b38e9d35d68e03a5485aa0ba4c9bd8d43ab30aa2`。
- 反向移除精确新增 CSS、六容器和标题后，整页与基线逐字相同；完整业务脚本 SHA256 `b6e5c87e2fcea5c3c7370318a39550d004c139b54495d3a4b27183c67d50adc5`，未变。
- 原754个 ID 及顺序、34 form／84 input／52 textarea／34 select／255 button 子树逐字保留。未修改测试、workflow、driver、字体 helper 或导览页；不新增 collection ID，不重跑全 collection。
- 当前最终源码上运行三个既有 Node 场景：`list_feedback_dispatch`、`list_feedback_receipt`、`same_batch_receipt_navigation`，退出码均0；原 stdout、stderr、命令、源hash见 `node-checks-original.json`。41／45／11 是场景内部断言次数，不能当作97个测试或累加历史成绩。本轮未跑pytest，不再次加计上一片5P。
- Node 场景使用实际整页 JavaScript，但 DOM 与 fetch 响应为受控替身，没有实际网络；覆盖列表加载、当前／旧响应、权限拒绝清屏、未知状态、错误不当空、同名记录原键导航。不证明真实浏览器、布局、CSP、焦点、服务冷启或正式业务。
- 源码检查和六组已声明实色对比数学见 `candidate-checks.json`；不是 computed style／WCAG 或真实像素验收。

两项独立只读源码审查均限定通过，包含独立逆向逐字比对；不代替实际浏览器或美观验收。

## 与回访候选合并的唯一后续渲染方案（本轮未执行）

先复核当前最终完整 SHA，再为实际下一编号绑定 workflow／font helper／driver main+worker／精确路径与来源父链，独审后一次，不重用run37或旧拒绝附件。仍用已有 hosted Chrome 正常 sandbox／CSP及已批准固定Noto/OFL，不安装新依赖、不启DB、不业务POST、不真实模型。

最多8张PNG＋result（9文件，另保留1失败图，合计≤10文件／8MiB）：1200／390服务入口、390定位原资料、390定位正式来源；协同1200空态、1200已有记录、390已有记录、390当前拒绝。协同数据仅用既有合法结构的显式 `SYNTHETIC / UI_STATE_FIXTURE`，经原列表 renderer 呈现；它不是真实后端／权限恢复证据。加载、错误、未知、disabled、focus/current、900／1060断点可用实际几何和状态日志核，不靠更多截图充数。

回访必须实际鼠标点击与键盘Enter分别核 fragment／activeElement／随后Tab、目标警示可读、请求增量0；UNKNOWN及在途原capture拒绝时默认跳转被阻止。正常原capture仍可能推进 tiEpoch／templateEntryGeneration；不声称零客户端状态变化。原目标未重排，新增快捷条可使实际y增加，仍待这次原生验证。

预算维持原10分钟job／3分钟依赖、90秒工作及清理／85秒worker、360秒发布绝对截止、原15／30秒等待、GET每侧<40（同批两侧不相加）、POST0；精确同源路由、凭据扫描与自有进程退出清理不放宽。不自动重跑，输出路线仅正常允许的新结果；执行器回报run/job/artifact ID/name/size/digest/expiry/source元数据，不尝试历史Forbidden下载方式。

本轮只冻协同源码；资源页与独立导览仍有旧中性绿表面未统一，不称全站精美完成。Windows／OWNER／正式来源／LIVE／正式AT35边界不变。
