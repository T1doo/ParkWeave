# ParkWeave 桌面 UI/UX 材质与布局改造

日期：2026-11-05。审阅基准：`ace8d1c9c6b23d32a8a3019ebdeac7f07e56364e`。工作分支：`codex/material-polish-20261105`。

依据：用户提供的《ParkWeave_Codex_UIUX_改造清单_ace8d1c9》及粘贴审阅意见。此轮没有改后端 API、权限范围、请求参数、预约与业务完成语义。

## 完成内容

### P0：详情恢复区

- 在基准页实际复现 INVALID：刷新按钮的 `disabled=false`、`:disabled=false`，原 `entryReadAllowed` 返回 true。因此没有把截图视觉上的弱化误报为禁用逻辑故障，也没有移除原守卫。
- 读取影响、刷新与原恢复入口归入同一区块。展示原因来自原状态；展示代码不写 `disabled`，不自动重试 UNKNOWN。
- 用原 `renderPrepCommandPending` 实测 SUBMITTING、UNKNOWN：刷新禁用；UNKNOWN 保留原参数核对按钮；无 pending 后刷新可用，INVALID 下审核仍禁用。只注入合成渲染状态，没有发送写请求。
- 修复材料菜单鼠标点击落空：原 focusout 的微任务可能先于内部按钮获得焦点而关闭菜单，现在通过 relatedTarget 保留菜单内焦点转移。两份 HTML 同步修正。
- 修复原“查看来源与版本”指向隐藏元信息的问题：在原 click handler 前展示同一个当前材料 metadata 节点，保留原聚焦和当前版本检查。未提供的文件信息保持未提供。

### P1：统一材质与四个工作空间

- 采用 accent 语义令牌，兼容既有 green 别名。侧栏与顶栏实际 blur 18px；当前页面的辅助面 blur 14px；主要输入和材料阅读区实色。一屏最多三个主要模糊面，不给按钮和每行列表单独加 blur。
- 蓝色主按钮、轻高光次按钮、统一控件圆角与焦点环。浅蓝／淡紫背景保持克制。支持用户主动选择低效果实色模式；不支持 backdrop 时使用近实色回退。
- 服务：标题跨主区域，继续事项与输入容器同排；持续显示目标提示；本页导航明确标为“本页定位”。
- 资源：完整原名称显示在选择框附近，不去掉限定词；目录约束压成两行；起止日期对齐，原生日期与自定义面板共存；数量宽 144px，预检紧邻。填写草稿和已选占位分别呈现。
- 协同：标题、分类、单一工具栏、列表顺序清晰；两个资料读取动作保持独立范围；快捷入口标明“定位入口”。整行仍为原按钮，名称／状态／查看提示分栏，不嵌套按钮。
- 详情：主列表 280px；资料事项版本与材料版本分别标明；警告／刷新同区，材料筛选同排。1440×900 同样例实测：协同首条记录 y≈378，首份材料标题 y≈457。后者略低于建议的 420–450，不裁掉风险信息强凑坐标。

### P2：动效与降级

- 按钮 hover 130ms、按下 90ms／1px；列表不浮起；菜单和阅读浮层轻量入场。
- 新用户背景默认静态；已主动保存的背景微动偏好保留。不叠加第二套循环。
- 低效果关闭材质和相关动效；减少动态禁用动画；强制颜色使用系统颜色并移除实际 blur。修正了强制颜色规则被材质选择器优先级覆盖的问题。
- 本轮未增加可选指针跟随高光。

## 截图条件与文件

所有主对照图均为 1440×900、同一历史合成资源 DTO、同一资料事项列表和两份材料。详情的二级读取故意失败，因此都是 INVALID，不能当作真实业务办理成功。

基准来自 Git 精确提取 ace8d1c9 的 HTML、CSS、JS 与图标，在独立只读端口复现，没有切换或覆盖工作区。两边明确设置 ink、comfortable、ambient off、glass（旧版本忽略不认识的偏好）。资源截图保留相同的日期面板关闭后焦点，协同保留相同的搜索焦点；不是拿不同焦点态冒充视觉差异。

| 场景 | 修改前 | 修改后 |
| --- | --- | --- |
| 服务 | [before](evidence/material-polish-20261105/before/after-service.png) | [after](evidence/material-polish-20261105/after/after-service.png) |
| 资源 | [before](evidence/material-polish-20261105/before/after-resource.png) | [after](evidence/material-polish-20261105/after/after-resource.png) |
| 协同 | [before](evidence/material-polish-20261105/before/after-collaboration.png) | [after](evidence/material-polish-20261105/after/after-collaboration.png) |
| 详情 | [before](evidence/material-polish-20261105/before/after-detail.png) | [after](evidence/material-polish-20261105/after/after-detail.png) |

额外截图：after 目录内有 low、unsupported、reduce、forced、字号放大和 200% 等效视口详情图。

## 已验证

- 六个现有 DOM／callback 套件通过：day、advanced、usability、motion、contract adapters、calendar Escape。它们不是像素或真实数据库测试。
- Python：7 passed、6 skipped、3 subtests passed。保留测试仅增加精确的三项展示 dataset 白名单；原点击处理器和请求合同仍逐字比较。
- 新浏览器测试：`tests/frontend_material_polish_browser.js` 与 `tests/frontend_material_polish_states_browser.js`。结果见同目录 evidence 下 browser.json、states.json。
- 原 form owner、required、日期两列、数量宽度；原目录失败不丢目标；目录 EMPTY／ERROR／DENIED 无旧资源泄漏。
- 原只读预检 POST 的合成响应：可用仍未占位，编辑使预检失效，容量不足禁用占位。两次预检请求，无占位请求。
- 0／1／2 个合成占位选择分别检查，身份变化清空选择。注入内存 DTO 后使用原 renderResourceHold 和原 checkbox handler，不制造真实占位。
- 分类键盘方向键，搜索无匹配，原两个读取范围；A/B 详情切换滚动归零及标题焦点；返回列表保留搜索。
- 阅读器 Esc 焦点恢复，来源版本菜单鼠标点击，原生 datetime-local 值与自定义日历箭头、不可选日、翻月、Esc 回归。
- 桌面 1280×800、1440×900、1920×1080；详情 1024、375、320 CSS px；资源日期还覆盖 768、720、320。未发现水平溢出。
- 125% 字号压力测试、720×450 等效 200% CSS 视口。后者不是操作系统缩放或原生浏览器缩放实测。
- 实际低效果选项、受控 unsupported 展示分支、减少动态、强制颜色各自检查；不是声称在不支持 backdrop 的旧浏览器上跑过。
- 一次自动化 Chromium 滚动采样：119 个 rAF 间隔，p50≈4.2ms、p95≈5.2ms、最大≈8.5ms，无捕获到的 long task。仅代表这个短样本，不据此宣称显示帧率或低端设备性能。
- 离线 wheel 构建通过，JS 语法检查通过。新布局回归无 pageerror、无业务写请求。

## 尚未验证与依赖

- 真实数据库四角色端到端办理、真实鉴权与提交／恢复闭环；六项数据库相关测试因当前 Windows／无测试 DSN 条件跳过。合成资料详情 INVALID 回放不能证明完整 READY 流程。
- 原生 Windows EXE、系统 125%／150%／200% 缩放、原生浏览器 200% 缩放、读屏器、低端 GPU 和长期运行性能。
- 全部透明背景位置的逐像素 WCAG 对比审计尚未完成，不能把令牌颜色检查当作全页无障碍认证。
- 未新增后端字段、统计或附件元数据；真实文件大小、类型、原始上传信息缺失时继续显示现有未提供说明。

## 主要变更文件

- `src/parkweave/workspace_design.css`：材质、布局、尺寸、动效和回退。
- `src/parkweave/workspace_design.js`：展示重组、恢复说明、结构化标题、完整资源名、元信息可达性。
- `src/parkweave/web.html`：三项列表 DTO 展示字段、默认背景偏好、菜单 focusout 修复。
- `src/parkweave/local_preparation_web.html`：默认背景偏好、相同菜单焦点修复。
- 对应浏览器回归与保留测试；没有修改业务请求参数。

参考：[Fluent Material](https://fluent2.microsoft.design/material)、[MDN backdrop-filter](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/backdrop-filter)。本次只实现应用内部材质，不宣称原生 Windows 桌面穿透玻璃。
