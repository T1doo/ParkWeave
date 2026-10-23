# 普通首办目录反馈

基线 `9212f0e624aa1d07b635cb354614d09fab132fb9`。原 `preparation._catalog_scope` 允许合法空服务或空专员；旧按钮 GET 成功后仅隐藏表单，没有结果说明。`red-original.log` 保存旧源码在合法空目录上的失败，不能把该空结果解释成接口拒绝。

本片在原按钮下增加局部状态：读取中、暂无服务、暂无核对专员、可填写本次目标、读取失败或身份拒绝。保留原表单和所有确认；只有明确点击时读取原 GET，没有新增 API 或自动建单。局部状态采用文字与原界面配色，不依赖颜色表达。增加 polite/atomic 状态语义、按钮描述关联与目录 busy 标记；尚未验证读屏实际播报。

沿用原身份/代际检查，旧响应不能结束新读取的 busy 状态；原清屏保护抛错时不会发 GET。完整校验当前目录范围及实际渲染字段后才显示表单；未知或损坏响应不能当作合法空目录。403 沿用原清屏和全局错误，再落本地拒绝提示。原建单提交函数、全局入口锁及其它代码逐字保留，见 `static-checks.json`。

实际定向验证：`pytest-original.log` 为 **9 passed，1 warning，0.45s**。执行提取的原 handler、prepCall、clearPreparation、prepError；DOM、传输及嵌套清屏依赖为替身。覆盖空服务/空专员/可继续/延迟读取/403后重读/损坏DTO/导航迟到/身份ABA/未决材料保护。未执行完整入口 wrapper，不称完整业务清屏、浏览器、像素或读屏验收。初次使用系统 Python 缺 pytest 的失败单列保留，随后使用已有项目 venv，未安装依赖。Node 语法检查通过。

`/root/summary_review` 独立只读审查限定 ACK，无新增确定 P1/P2；未写入、未代跑测试。当前 collection 清单刷新为9530项/406文件，**仅收集、非通过数**；四片计数从本轮全量实际收集推导，未重复执行分片。历史收集证据保留，未声明新的 Windows 诊断目录完整性或兼容性。

**真实视觉仍未验。** `render-capability.json` 记录只读核查：Chromium helper 仍为 uid/gid65534、mode4755，旧真实启动因配置错误失败；现有 CUA/Playwright-core 包并非已启用浏览器服务，未找到可调用宿主 renderer。`/root/.cache/ms-playwright` 检查被 PermissionError 拒绝后停止，内容未知。需要环境支持方提供正常 sandbox 镜像/运行条件或正式启用宿主浏览器工具。未改权限、禁 sandbox、安装替代浏览器、访问用户电脑或重试旧进程。run34 ZIP/log 的 Forbidden 未重试或换路线。

本片浏览器0、CI0、实际产品API0、新截图0，无待定写操作；原 Windows/OWNER/LIVE/正式来源门保持。当前产品改动是可审候选，不称整套前端精美或流畅度已验收。
