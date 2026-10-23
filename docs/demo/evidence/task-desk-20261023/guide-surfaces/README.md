# 导览页暖橙分区候选：源码检查，未做像素验收

基线 `33083caaebdc640ba4361c3381ae13e1489e5c3d`。本片只修改 `src/parkweave/park_demo_web.html` 的展示：身份准备、候选输入、原流程说明分成三个独立表面，右侧双窗口说明保留。主入口暖橙、辅助输入蓝灰、说明浅暖中性；角色与填表示例按钮各自分组，窄屏单列。未新增链接或业务动作。

新增五个展示 div、一个 h3 和末尾 CSS；逆向移除这些改动后，整份文件与基线逐字一致。完整脚本、原九个 ID 及顺序、八按钮、一输入、一选择、两 label、三个 details（含 open 和全文）、右侧说明子树不变。顶部模拟警告、文件隐私、只填不提交、切换人物、取消及重启边界全部保留。状态仍独立：仅 neutral 改蓝灰，原 success/error 语义及脚本不变；disabled、键盘焦点、forced-colors 和 reduced-motion 保留。两位只读审查者完成源码复核，无确定阻断。

实际执行的是既有 `tests/workspace_content_refinement.js` 中导览专用原始代码块，使用 Node VM 与机械 DOM/window 替身；空文件、坏文件、等待、迟到读取、成功内存状态、弹窗拒绝和 pagehide 清理通过。此前六组服务配对未执行，本片没有运行 pytest/collection、HTTP、PG、浏览器或 CI，没有新增测试 ID。`node-original.json` 保留实际 stdout/exit 与原始块指纹，`source-checks.json` 保留源码不变证明和声明色对比计算；计算不等于实际 CSS 或完整 WCAG 通过。

导览文件 SHA256：`966f175764bdf323eea9c6e87f520c584da6ae03243b5c0396e492ce76a1af8c`。完整脚本 SHA256：`ad22e72b081099cbf0b2de44c75264705c34300f627afc367da356b5c9725179`。

实际 390/宽屏像素、原生文件选择、弹窗成功、跨窗口填表、焦点与 details 行为尚未验证；不据此称全站精美或正式业务验收。下一候选是经独审后将资源新场景与导览合并做一次必要渲染，本轮没有启动该窗口，也没有复跑 run39 或读取旧被拒附件。Windows/OWNER、正式来源、真实模型门不变。
