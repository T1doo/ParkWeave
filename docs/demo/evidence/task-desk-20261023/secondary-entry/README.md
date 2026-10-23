# 次级新建入口分组候选

基线 `4fdfad688f3140cd7e600250dac765ec11ed00fa`。原普通首办下方增加“其他创建方式”分组：配置/模板的说明与按钮采用紧凑分列；窄屏按原顺序排列；简易建单表单使用原生 details 按需展开。原警示置于折叠区外，不截断文字或覆盖当前状态。

配置读取、两个原 key GET 恢复按钮始终在新折叠区外，保留取消后另办的原聚焦路径。`cold-status`、`template-input-status`、两个 current 及其确认动作也在外。全部原业务脚本逐字相同，未加 API、自动动作或业务入口；原权限、确认、来源和未知门不变。保留焦点与减少动画规则，无吉祥物。

独立只读审查 `/root/summary_review` 限定源码 ACK，无新增确定阻断。实际本地验证为 HTML 树/原文/控件顺序和五个原 form/current 子树连续性、Node 语法检查。425 控件与 747 原 ID 是核对数量，不是测试用例；未重跑 collection/业务套件。网页 SHA256：`2ea2c59cf2a4b9ce25b196764077dcdcbcfe1151af2c130fd15c7ceb2d9481d7`。

**缺少本片真实渲染。** 原本地 Chromium 启动失败于 SUID sandbox helper 所有权；本次只读 stat 仍为 uid/gid 65534、mode4755，并非要求的 root owner。既有原日志/结果位置与 hash 保存在 `local-render-status.json`。未重试启动、不改所有权/权限/沙箱，不安装新渲染器。没有其它已暴露的本地浏览器能力；Node 不是像素渲染证明。

本片新增浏览器运行0、CI0、产品API0、截图0。旧 run34 的 artifact/log Forbidden 没有重复下载或换路；旧官方 success 不代签当前源码。未验：实际宽窄布局/纵向高度、原生折叠键盘与读屏行为、视觉与流畅度。此处是可审产品实现候选，尚不称设计终验或整套前端完成。
