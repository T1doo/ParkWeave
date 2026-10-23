# run27：原页面视觉切片限定通过

实际受测源码 `01cb4a18d7396b542995116f41b576b82b39bb34`，tree `46bc9b1ef251024e67dbb7da3d184cc385352a89`，[官方 run27/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39876408749)，job `120162978439`。原正常 sandbox Chrome 真实执行，无业务 API／数据库／模型、0 POST；两侧各8 GET。8张原PNG、result.json、完整API job log和官方ZIP逐字保留。ZIP9成员合计3930322B，符合当次10文件/8MiB上限；本目录另含归档元数据和ZIP副本，不能把归档文件总数当CI上传数。未自动重跑。

原源码的run26门只重绑27，HTML/CSS及业务断言逐字未改；run26失败仍保留，旧Chrome退出与启动根因仍UNKNOWN，本次成功不反推旧根因。监督器记录7个已绑定pidfd退出、worker returncode0、受控子树闭合，未发清理信号；浏览器CLOSED、监听REFUSED、cleanup_errors空。工作与清理17.132秒，扫描发布17.151秒，保留原90/360秒和10分钟job预算。

逐张原图：01/02服务宽屏前后；03/04已归档合成计划面板宽屏前后；05/06演示导览宽屏前后；07当前历史计划面板390px模拟；08当前导览390px无效文件状态。07为362px宽面板截图，浏览器视口390px，不是手机实机。历史计划通过原render函数呈现，只是明示SYNTHETIC VIEW_REPLAY；不当作当前健康、权限、业务办理、核验或恢复成功。三次渲染的文字指纹和5个步骤ID保持一致，P1/P2历史VERIFIED、P3PENDING/P4/P5BLOCKED如实显示。

作者用真实view_image逐张看过8图：新深绿页头/左侧导航、较轻卡片和统一导览有可见改善，展示的中文可读、窄屏换行。仍有窄屏UUID与按钮拥挤、技术枚举与说明密、无效会话沿用绿色status等精致度缺口；原生file chooser在该环境为英文。具体观察和未覆盖范围见visual-review.json，不称整套前端已精美完成。协同/资源仅空态几何与真实glyph观察，未保留有内容关键页图；目标结果/TXT正文、实际办理与完整角色链不在本轮。

14项几何观察、13次可见节点glyph观察不是27个独立测试。固定字体完整静态集合为当前源码的684个码点，实际glyph只覆盖受检可见节点；不称所有页面全部码点视觉通过。focus-visible运行断言3px，非读屏播报实测。stdout仍为PENDING_FINALIZATION，最终以result.json与官方step结局及worker exit联合判断；summary正文未独立读取，完整日志无上传失败。757源码指纹预检与历史collection不算本轮业务回归。本片不含新wheel、冷启、Windows、正式来源、LIVE或正式AT35验收。
