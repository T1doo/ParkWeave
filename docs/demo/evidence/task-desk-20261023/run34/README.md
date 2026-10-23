# ParkWeave 任务工作台：run34

本轮真正调整普通办理入口和阅读层级，保留原功能和安全门。当前结论是 **官方运行元数据成功、执行原件读取被拒**，不是视觉终验。

- 受测源码：`cb64d7a58ee608d162786a1511eecc97e7bd83a9`；直接父版 `f3f67f6e1a936172d7646508d9e768ada3313aa2`。
- [官方 run34](https://github.com/T1doo/ParkWeave/actions/runs/39938250371)，attempt 1；job `120363025560`。
- [本轮官方附件](https://github.com/T1doo/ParkWeave/actions/runs/39938250371/artifacts/12494299381)：API 声明 1,406,604 B，SHA256 `f672a833167d8691ed4c4654963b89dafcf567071f0b519e701066567eff245e`。这是上游声明，尚未独立下载核 hash；附件按原规则一天后过期。

## 产品变化

紧凑品牌头、独立工作区导航和身份条，中央普通首办与右侧继续已有事项/来源条件。普通首办使用原 `prep-catalog → prep-create`，而非默认关闭的实例 consumer。其原资格/外部未受理警示在主操作前。配置、模板和简易建单仍保留为次级入口，没有补接 API。

原服务块内部仅精确前移普通资料准备子树，原 section 进行精确重排并增加布局 wrapper；其他 HTML 除导览 scenario 显式 label 外不变，两页完整业务脚本逐字不变。等待/记录状态使用中性色，不推断成功；统一表单、按钮层级、焦点、禁用及错误提示。支持减少动画，不加宠物或插画。

设计参考只读学习 [frontend-design](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md)、[craft floor](https://raw.githubusercontent.com/pbakaus/impeccable/main/.agent/skills/impeccable/reference/craft-floor.md)、[Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)、[motion principles](https://raw.githubusercontent.com/kylezantos/design-motion-principles/main/skills/design-motion-principles/SKILL.md)。未安装或执行其代码。

## 实际验证与边界

本地完成两 HTML 精确结构变换及脚本字节核对、两脚本 Node 语法检查。离线控件比较分支核 reordered anonymous buttons、disabled drift、重复记录计数。792 是现有文件指纹核对，不是 792 测试；未重跑 collection 或业务套件。

官方 API 原件记录 run/job/全部 steps success，10:19:17–10:20:15 UTC。驱动计划对 1200/390 桌面视口做两场景前后八图：原普通首办首屏、原 renderer 的 run21 待企业核对回执。后者为明确标注的 SYNTHETIC VIEW_REPLAY，不是当前健康、授权或新业务。导览仅 DOM 文件错误反馈与标签检查，不在八图内；焦点和减少动画有运行断言，不是动画录像或设备流畅度签收。

本次约束保持 job 10 分钟/依赖 3 分钟/UI 连清理 90 秒/绝对发布 360 秒，两侧 GET 各 <40、0 POST、最多 10 文件/8 MiB、正常 Chrome sandbox/CSP、固定获许可字体。源码存在这些门不等于已独立读取本轮实测计数或清理报告。

## 精确读取阻塞

经已可用的 `gh api` 读取 artifact ZIP 和完整 job log 时，GitHub 重定向到 `productionresultssa17.blob.core.windows.net` 后，两目标 GET 均返回 **Forbidden**；原因未说明。两个本地输出均 0 B，停止下载，0 重试、0 替代路线，不为补证重跑 CI。没有 pending 写入或审批请求；这不是缺开发分支推送授权。

`evidence-download-denied.json` 为去除短期签名 URL 的结构化诊断，**不是完整原始 stderr**。空 ZIP/log 留在 scratch，不伪装正式原件入档。官方三份 API JSON 是真实已取得原件。当前缺本轮截图/结果 JSON/完整 job log，故像素、中文实际渲染、实际请求数、终态与进程清理均未独立复核。需恢复该证据下载通路或取得同一 run 原件，而非重跑。

本轮不签完整主流程、wheel、冷恢复、Windows/native、正式来源、LIVE、真实设备或整体美学完成。传输候选已独立保存于父提交；OWNER/Windows/旧门未解除。main 不变，未接触用户电脑。
