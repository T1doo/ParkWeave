---
title: ParkWeave 前端精修与实机验收
date: 2026-11-04
tags: [ParkWeave, frontend, verification]
---

# ParkWeave 前端精修与实机验收

> 本文件保留早期迭代记录。用户后来提供了四场景系统重构要求，当前实现及验收以 [WorkspaceRebuild-20261104.md](WorkspaceRebuild-20261104.md) 为准。

## 最新修订：路径入口卡与分类工具控件

用户指出路径区的竖线、孤立箭头以及工具区默认三角列表仍过于简陋。本轮将三条路径重建为独立入口卡：复用已许可的 Fluent 图标、三种局部色调、统一标题/说明/操作区域，去掉竖线和箭头。整张入口仍只有一个原链接和键盘焦点，不嵌套假按钮；“编辑目标／查看方案／查看材料”是该链接内的操作提示，仍执行原焦点与权限检查逻辑。

辅助区改为桌面三列两排的紧凑分类控件，图标与文本对应，展开状态使用加减标记和连续内容面；窄窗自动单列。每项仍为 native details/summary，保留键盘和原业务内容。软件品牌仍使用上一轮 AI 生成 PNG，新增路径图标属于已有 UI 图标集。

实机局部截图 `entry-tiles-detail.png` 对应用户指出的两个区域；整页为 `entry-tiles-1366.png`。基础/高级 DOM 回归与完整浏览器回归通过，首屏高度断言通过、零 pageerror、零写请求。额外实测路径 Enter 后焦点回目标输入，辅助工具 Enter 展开，以及展开后 320px 无页面横向溢出。

## 最新修订：功能分区与清晰边界

按用户最新要求，将服务首屏划分为新建目标、办理路径、继续已有事项、辅助工具四区。目标区用蓝色顶边强调当前输入；路径和继续事项并排，使用一致的细蓝边框和浅色标题栏；标题旁说明用途，区内操作以更轻的分隔线区分。低频创建方式与来源入口归入辅助工具，不再散落在主区之间。资源、协同面板及资源摘要同步加强外边界。

最新截图：`section-hierarchy-1366.png`、`section-hierarchy-1440.png`。实测主区在 1366×768、1440×900 初始状态分别为 clientHeight/scrollHeight 768/768、900/900；320px 页面无横向溢出，按单列正常纵向滚动。窄窗展开“其他办理入口与来源条件”并等待 180ms 动效后，原正式来源入口可见且可操作。

原浏览器回归全部通过，24 个 GET、零写请求、零 pageerror；基础与高级 DOM 回归通过。此次没有修改业务请求契约。原数据库和 Windows 原生宿主未验证边界继续保留。

## 最新修订：位图品牌与紧凑首屏

本轮继续按用户要求减少纵向滚动，保留已认可的浅蓝方向，并降低背景光晕与点阵的存在感。

- 使用内置 image_gen 生成透明 PNG 品牌标记，两条蓝色带交织成庭院状负空间。原文件保存在 `src/parkweave/assets/parkweave-mark-original.png`；128px PNG 用于页面，ICO 是尺寸/格式转换的交付资产。已接入侧栏与网页 favicon，未重新编译 Windows EXE。
- 同源 `/parkweave-mark.png` 返回实际 PNG；加入 Python 包资源清单与只读预览清单，未放宽 CSP。
- 输入区域、标题、主动作与区块间距收紧；办理路径和继续事项在桌面并排，低频工具收成底部两列入口。
- 报告历史和人工协作使用 native details 保留原 DOM、ID 与处理器；状态变化或进入编辑会展开。实测键盘 Enter 展开以及合成状态变更后的自动展开。
- 实测服务初始页：1366×768 下主区 clientHeight/scrollHeight 均为 768；1440×900 下均为 900。仅初始页无需纵向滚动，展开长内容或进入业务详情仍允许正常滚动，不裁切内容。
- 品牌悬停有短时轻微转动，低频区域展开有高度过渡；保留按钮反馈、动态背景开关、后台暂停和减少动态路径。

最新截图：`compact-brand-1366.png`、`compact-brand-1440.png`。`compact-brand-motion.gif` 是 15 张实机操作帧组成的预览，包含按钮、输入焦点、品牌悬停与展开，不代表连续录屏的帧率。准确生图提示词与模式见 `evidence/frontend-polish-20261104/icon-generation.txt`。

最新浏览器回归见 `compact-brand-browser.json`：新增首屏高度、PNG 返回及键盘展开断言，原日期、七种宽度、状态、主题回归继续通过，零写请求、零 pageerror。六组前端 DOM 回归均通过；Python 原业务/装配保留和预览 HTTP 测试 7 passed、3 subtests passed。真实角色与数据库业务仍未重新验证。

## 后续修订：浅蓝玻璃与动态背景

用户随后明确要求突破原 DOCX 的静态米白方向，采用浅蓝科技风、磨砂玻璃按钮、更丰富的颜色和动态背景。本节覆盖下文旧版的视觉结论，旧截图保留为历史。

当前完整工作台增加蓝紫青三色缓慢移动的背景、玻璃按钮的内高光与按压反馈、半透明编辑面和导航、三色办理路径入口、协同分区和资源摘要表面。服务入口重组为目标编辑、继续事项、办理路径；长篇原说明放入可展开区域，原文及处理器保留。外观菜单提供“背景效果：柔和流动／静态背景”；页面后台暂停，减少动态直接停用动画。

参考来源：

- [Figma 官方 Glass 效果说明](https://help.figma.com/hc/en-us/articles/360041488473-Apply-effects-to-layers)：磨砂、透光、边缘光的层次。实现为 CSS 近似，并非 Figma 原生折射效果的像素复制。
- [Glassmorphism Dashboard 作者发布页](https://dribbble.com/shots/26136889-Glassmorphism-Dashboard)：作者提供 Community 入口；Community 文件访问受限，未打开源图层、未复制原资产。
- [Aceternity Aurora Background](https://ui.aceternity.com/components/aurora-background) 与 [Moving Border](https://ui.aceternity.com/components/moving-border)：作为背景流动与边界反馈研究参考；本地 CSS 原创实现，没有引入组件库。

新增证据：`blue-glass-service.png`、`blue-glass-collaboration.png`、`blue-glass-interaction.gif`，均位于本文件对应证据目录。GIF 由 16 张实际浏览器操作帧组成，固定帧间隔便于预览，不是性能测量或连续录屏。

本次重新通过完整浏览器回归（19 个 GET、零写请求、零 pageerror）、基础 DOM 回归、动效 DOM 回归、原业务与装配保留检查。额外实测背景两时刻的 transform 不同，减少动态时 animation 为 none，外观开关分别切换 paused／running。数据库与原生宿主未验证范围仍同下文。

本轮依据 `ParkWeave前端设计修改方案.docx` 完整正文及全部 35 张嵌入图进行对照。六张页面方案与按钮、比例、表单日期、预览时序等局部板另作大图检查。未将文档示意图当作产品截图，也未向产品复制第三方参考资产。

初始 `main` 与 fetch 后 `origin/main` 均为 `c5d39569e0ee669196354ad97b8bc48099af2914`，工作区干净，无需快进、没有远端差异。修改保留于 `codex/frontend-docx-polish-20261104`，未提交或推送。

## 本轮结果

用户在初版后明确指出视觉过于简陋，并补充不必局限于橙色。因此增加默认墨青主题：深墨青导航、雾白辅助表面、白色正文和克制的青绿操作色；陶橙与米白鼠尾草继续可选，已有偏好继续尊重。保持左导航加右功能区，原 ID、业务处理器及 HTML 装配标记不变。

- 将重复回访导航移出目标输入前的首屏，主操作置于办理路径说明之前。
- 重做品牌比例、侧栏导航、标题字号、正文宽度、输入内边距与辅助区层级；普通输入值保持常规字重。
- 查看已有记录改为次要描边动作，避免与当前主任务争夺视觉重点。
- 增加关联输入的目标说明与实际字数。修复目录读取失败后原目标恢复而字数未同步的问题。
- 修复资源、协同工作区仍显示服务辅助入口、首屏出现大块空白的问题。隐藏对应容器也从键盘和可见性判断中移除；工作区顶栏同步命名。
- 日期面板收至 440px 阅读宽度，日期选中、焦点和不可用保持独立。320px 触摸场景保留 44px 日期目标，只在网格内部横向滚动。
- 完整页与精简材料页共用新控件和主题规则；未改变身份、数据库、权限或请求契约。

## 同尺寸实机截图

浏览器 UA：Windows NT 10.0 Win64，Chrome 156.0.0.0。截图为原始 HTML 实际执行后的浏览器像素，1440×900 与 1366×768 是实际内容视口；非设计合成图。

修改前由 `git show c5d39569…:src/parkweave/...` 的原字节提供，修改后由工作区原文件提供。两者使用同一历史公开合成资源 DTO、相同输入和视口。服务页为空白初始状态，资源与日期页使用明确的历史合成数据；不代表当前资源可用或真实业务成功。

| 场景 | 修改前 | 修改后 |
| --- | --- | --- |
| 服务 1440×900 | [修改前](evidence/frontend-polish-20261104/before-service-1440.png) | [修改后](evidence/frontend-polish-20261104/after-service-1440.png) |
| 服务 1366×768 | [修改前](evidence/frontend-polish-20261104/before-service-1366.png) | [修改后](evidence/frontend-polish-20261104/after-service-1366.png) |
| 资源 1440×900 | [修改前](evidence/frontend-polish-20261104/before-resource-1440.png) | [修改后](evidence/frontend-polish-20261104/after-resource-1440.png) |
| 日期 1440×900 | [修改前](evidence/frontend-polish-20261104/before-calendar-1440.png) | [修改后](evidence/frontend-polish-20261104/after-calendar-1440.png) |
| 触摸日期 320×900 | 未采集 | [44px 日期目标](evidence/frontend-polish-20261104/after-calendar-touch-320.png) |

日期页以面板顶部为同一阅读锚点，内容因本轮修改而重排，不将不同滚动位置冒称布局完全相同。

## 验证证据

### 实际浏览器与 HTTP

[浏览器脚本](../../tests/frontend_polish_browser.js) 与 [记录](evidence/frontend-polish-20261104/browser.json)：

- 原服务目录 GET 失败后目标保留、字数同步；无虚构读取成功。
- 主题、密度切换保留草稿，不产生业务请求；Escape 关闭外观菜单并回焦。
- 日期方向键、不可用日期 Enter、PageDown、格内 Escape 与头部 Escape 通过；浏览月份不改变值，结束时间保留。
- 1440、1366、1280、1024、768、720、320 CSS px 的资源与日期布局无页面或主区横向溢出。
- 强制颜色与减少动态条件下日期可操作。
- 实际本机 HTTP 的 EMPTY、ERROR、DENIED 分别由原处理器正确显示，无残留资源卡。
- 本次脚本 19 次请求，均为 GET；JavaScript pageerror 为零。预期的目录 404、500、403 会产生浏览器网络错误日志，不能将其说成所有控制台和网络请求都无错误。
- 另用 `hasTouch:true`、320×900 的新浏览器上下文测量：日期格宽 44px，内部网格宽 326px，网格容器 247px，文档宽 305px。日期网格独立滚动，页面不横向溢出。

### DOM 与装配回归

六组既有脚本均 PASS，原始输出在同目录 JSON 中：`frontend_day_dom`、`frontend_day_advanced_dom`、`frontend_usability_dom`、`frontend_motion_dom`、`frontend_contract_adapters_dom`、`frontend_calendar_escape_callback`。

覆盖材料筛选与阅读回焦、版本变化关闭预览、分组编辑返回、未保存确认、未知操作守卫、权限拒绝清理、占位选择与本地意向分离、整组冲突的显示与失效、错误摘要、输入法保护、动态取消与请求适配。以上属于 DOM/测试替身证据，不能替代数据库业务或浏览器像素证据。

Python：`test_frontend_day_preservation.py`、`test_frontend_preview_stdlib.py`、`test_frontend_contract_adapters.py` 合计 **7 passed、6 skipped、3 subtests passed**。原业务 JavaScript 与全部静态 ID 保留断言通过；四角色登录和样例 HTML 装配点通过。6 项数据库测试因 Windows 未配置明确的 test-owner DSN 而跳过。存在 Starlette TestClient 的依赖弃用提示，未修改项目依赖契约来消除提示。

`test_local_workspace_entry.py` 在 Windows 收集时因其 Linux 入口依赖 `fcntl` 无法导入，未计通过。未绕过平台限制。`git diff --check` 通过。

## 逐项对照 DOCX

“保留”表示原实现继续存在；下表明确区分浏览器实测、DOM 回归和仍待业务实测。

| 条目 | 本轮对照与证据范围 |
| --- | --- |
| P01 服务目录与继续办理 | 调整目标、目录、回访优先级；浏览器已验目标在目录失败后保留；完整创建与采用待数据库 |
| P02 目标责任概览 | 开放正文保留；原处理器/ID 断言通过；有数据的计划页面未作本轮像素验收 |
| P03 资源常驻摘要 | 历史 DTO 浏览器截图、窗宽重排与 DOM 选择回归；实际占位/组合确认未验 |
| P04 日期时段上下文 | 浏览器方向键、PageDown、不可用、Escape、值保留及触摸目标实测 |
| P05 已核验摘要 | DOM 回归保留来源和原动作；真实事件回读未验 |
| P06 细选中轨与白面 | 浏览器服务/资源/日期可见，墨青新增；原两主题保留 |
| P07 标题与角色状态 | 原责任/状态渲染器保留；业务状态不得由新样式推断 |
| P08 分组核对修改 | DOM 回归通过；有数据的整页像素与完整提交待验 |
| P09 轻阶段轨 | 浏览器保留“浏览位置不等于完成”说明；未知状态未换成成功 |
| P10 窄屏阶段展开 | 既有 DOM 与动效回归通过；窄内容视口已运行 |
| P11 紧凑材料行 | 原文本类型/8KiB 限制保留；DOM 导入与元信息回归，真实上传未验 |
| P12 材料预览 | DOM 回焦、失效关闭、窄窗切换回归；真实授权材料浏览器未验 |
| P13 材料筛选 | DOM 过滤、清除、未知状态保留回归 |
| P14 同事项记录 | 原处理器与历史入口保留；真实记录浏览器未验 |
| P15 条件与状态 | HTTP 空/失败/拒绝浏览器验证；没有把未知变通过 |
| P16 查看编辑锁定 | 原动作和权限条件保留；角色业务实测未验 |
| P17 表单控件 | 外置标签、常规值字重、焦点、比例重做；服务/日期像素验收 |
| P18 错误不丢输入 | 真实 GET 失败保留目标与字数；DOM 字段错误摘要通过 |
| P19 协同紧凑筛选 | 原筛选回归；修复服务入口串入协同；真实协同列表像素未验 |
| P20 等待与责任 | 原文字与业务渲染保留；四角色真实交接未验 |
| P21 局部展开 | 既有动效 DOM 回归与减少动态浏览器验证 |
| P22 材料类别展开 | DOM 记忆与动态回归，真实材料未验 |
| P23 轻勾语义 | DOM 本地选择与占位清理回归，无新增写请求 |
| P24 修订保留历史 | 原处理器保留；DOM 局部修改返回通过；真实重开未验 |
| P25 完整备选主题 | 两个原主题保留，新增墨青；主题切换不丢草稿、不发请求 |
| P26 中文缩放 | 长中文资源与 7 种窗宽实测；720px 为 1440px 的 200% 等效内容宽度，不声称原生浏览器缩放通过 |

## 未验证范围

本轮没有已授权、可初始化的 Windows 业务数据库。四角色密码登录后的创建、审核、回执、企业确认、占位/释放、重启持久恢复及外部园区履约未实测。精简页浏览器只验证登录外壳，业务交互证据来自已有 DOM 回归。Windows EXE/WebView2 宿主未重新编译或验收。原生浏览器 125%/150%/200% 缩放、系统字体放大、读屏器和整页可访问性审计未验。文档 26 项未全部通过真实业务与像素验收。

## 复现

用 Python UTF-8 模式运行 `python -X utf8 scripts/frontend_polish_review.py --seconds 600`，打开 `http://127.0.0.1:8876/web.html`。资源回放标识是公开字符串 `SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY`，不是账户或令牌。8880 是不可变基准，8877/8878/8879 分别为空/失败/拒绝。脚本仅绑定 loopback，最多运行 1800 秒，所有写请求拒绝。

`tests/frontend_polish_browser.js` 是供 Playwright 浏览器工具执行的 async 函数源码；须先启动上述服务。截图和测试均不需要生产凭据。未对外部署，也未创建系统服务。
