# 通知身份／权限拒绝的及时清理

接续基线 `4695193a529e456b15701b691637545ffed7cc7a`，开发分支 `dev/f2-notice-auth-headers-20261020`。原产品 V1 §5.5、F2-T04/T05 及 [ENG035 通知合同](ENG035-DispatchNotices.md)要求当前拒绝清除通知和关联私有详情。这是已有通知路径中的实际缺陷修复。

## 已复现的问题与修复

原 `noticeCall` 先等待 `response.json()`，再检查 HTTP 状态。收到明确的 401/403 头、正文却未结束时，拒绝清理会一直等待；原 `noticeError` 也只把 403 纳入清理，401 后仍保留旧通知。已有 `entryFetch` 会给 403 的 JSON 解析异常补状态，因此本片不声称“所有非 JSON 403 都绕过清理”。

现在收到响应后先核通知身份／选择代次，再按 401/403 固定提示进入原拒绝清理，不读取其正文；401 复用原 403 的通知及关联详情清理。明确刷新才重新读取，旧通知不能继续 MARK_READ。成功正文返回后仍重核代次，409/502 等原行为保持。没有自动 OPEN、接单、提交回执或重发请求。

HTTP 状态与 JSON 正文解析是不同阶段；实现参考 [MDN Fetch 说明](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)。后端鉴权、数据库、权限、时限、确认／取消／恢复协议和启动器均未修改。

## 实际测试和独审

2026-10-20 UTC，在本次新实例使用已有 Node v24.19.0、Python 3.12.14。没有安装依赖。

| 范围 | 实际结果 |
| --- | --- |
| 修改前的原页面函数 | 新增 8 场景全部失败：401/403 的 JSON、HTML、未完成正文，以及两种迟到拒绝。 |
| 修改前完整原脚本＋原生 HTTP | 原 401 请求因等待未完成正文而达到测试的 2 秒期限；预期非零退出，原错误保留。 |
| 最终源码的通知定向回归 | 原 10＋新增 8，共 18 场景全部通过；DOM／传输替身，实际加载原通知及传输函数。 |
| 最终完整页面脚本＋真实 loopback HTTP/fetch | 401/403 各通过：原 GET 详情、明确 MARK_READ POST，服务端只发拒绝头且始终不结束正文；完整原清理函数和入口包装执行，拒绝后无新请求。DOM 为机械替身，无浏览器／业务 DB。 |
| 独立审查 | 18 场景独立复跑通过；另自写 8 反例通过，覆盖同 token ABA、正文跨代、非授权错误兼容和不透明拒绝引用保留。这些范围有重叠，不相加为新唯一测试数。完整脚本 HTTP 两状态另独立实跑通过。最终无开放 P1/P2。 |
| 测试自身的失败清理 | 独审发现整页初始化在 server 清理的 try 外，已移入；独立合成初始化异常预期退出 1、0.057 秒自行结束，无悬挂。 |
| 语法与差异 | 两份 Node 测试语法、Python wrapper 编译、`git diff --check` 通过；最终四个产品／测试文件运行前后 SHA256 相同。 |

最终产品 `web.html` SHA256：`a50f602bbc1bf84f28afbae16b9ff4f5e9bdbe9d951eaa7700d09122bc497301`。最终 HTTP 测试 SHA256：`83321ec68f16d78ec02f18b868356fe41bd2a731584110dd29e18cb705cd40a4`。

独审另核完整入口：未知材料／异议提交阻止通知导航；原通知读取前清理资料上下文；重新进入资料同步使旧通知代次失效。未发现通过原 UI 使当前通知拒绝与未知材料写入并存的路径，没有为人工赋值构造的不可达状态扩大清理权限。

精确结果和源指纹见 [机器证据](evidence/notice-auth-headers-20261020.json)。本次原始红绿结果、浏览器启动错误和完整页 HTTP 输出保留在忽略目录 `.runtime/notice-auth-20261020/`。独立反例原脚本及结果另保留在本实例 `/tmp/parkweave-notice-independent-review.*`，不假定其他环境共享这些文件。

复现定向 JS：按 `tests/test_dispatch_notice_page_offline.py` 的 18 个 mode 分别运行 `node tests/dispatch_notice_pagination_offline.js src/parkweave/web.html <mode>`；完整原脚本 HTTP：`node tests/dispatch_notice_auth_http.js src/parkweave/web.html`。本环境缺 pytest、psycopg、pgserver，未执行 pytest 或数据库回归，不将 Node 结果写成 pytest 成绩。

## 未完成与保持的门

当前 Chromium `chromium_sandbox=True` 单次启动失败：SUID helper 配置不满足要求，另有 crashpad database 错误。浏览器在加载产品前中止；未改权限、关闭 sandbox 或重试。此为环境启动失败，不是自动批准审查拒绝。真实浏览器 UI、Windows 原生、正式 AT、真实来源／业务／模型及全项目验收未运行。

原 Windows CI `39353828380` driver exit 1 和内部首因未知保持；没有请求已拒绝的详细日志或盲重跑。main、workflow、真实凭据／模型／费用／安全网络设置、用户电脑和发布均未操作。本开发分支不匹配已有 workflow 的 push 分支列表。
