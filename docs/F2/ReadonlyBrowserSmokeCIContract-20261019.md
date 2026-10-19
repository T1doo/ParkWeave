# 原页面无会话只读浏览器冒烟：单次 CI 合同

本增量只为当前原页面提供真实 Chrome 的最小无会话冒烟。基线为
`ec4bd7371f7b9c190618057951e1bb6da8457397`。不修改产品代码、原 7 个 workflow，
也不重跑已有 HTTP 主例或 B0/B2 的 39 项规划测试。

## 执行与费用边界

新增 workflow 仅接收 `dev/f2-readonly-browser-smoke-20261019` 的 push；限定
`T1doo/ParkWeave`、公开仓库、首次 run 和 attempt、一个标准 `ubuntu-24.04` job，
总上限 6 分钟。没有手动、定时、PR 触发器，没有 matrix、cache、artifact 上传、部署、
外部业务服务或自定义 secret。checkout 使用原先固定 SHA，权限只有 `contents: read`，
不保留 Git 凭据。不自动重试，失败后不以新 push 或 rerun 继续执行。

[GitHub 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
说明公开仓库的标准托管 runner 免费，日志和 job summary 不计 artifact 存储；
较大 runner 另计费，本流程不使用。公开条件在 job 分配 runner 前核对；若仓库变私有则跳过。

仅用 runner 已有 `/usr/bin/python3.12` 和 Google Chrome。缺失、版本不兼容或 sandbox
不可用就失败；不安装浏览器、不执行 APT、不改变 OS/sandbox 设置。
[官方 Ubuntu 镜像清单](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)
列有预装 Chrome，但本次 runner 的实际镜像和浏览器版本以运行日志为准。

## 软件与许可核对

复用 `requirements-linux-evidence.txt` 的精确 Python 依赖，新增精确固定
Playwright 1.62.0、pyee 13.0.1、greenlet 3.5.6，与当前项目 `.venv` 一致。
项目此前没有提交 Playwright 锁；系统 Python 的 greenlet 3.5.5 不是项目基线。
本地包元数据分别标示 Apache-2.0、MIT、MIT AND PSF-2.0；
[Playwright 1.62.0 官方许可](https://github.com/microsoft/playwright-python/blob/v1.62.0/LICENSE)
为 Apache-2.0。没有新增许可接受步骤。Chrome 沿用 runner 已有安装，不下载其他浏览器包或 FFmpeg。

[Playwright 官方浏览器说明](https://playwright.dev/python/docs/browsers)
支持 `channel="chrome"`；这里使用 runner 的 Chrome 而不是 Playwright 配套 Chromium，
因此兼容性必须由实际执行证明。显式 `headless=True, chromium_sandbox=True`，
并读取 CDP 实际命令行及 `chrome://sandbox` 的 namespace、seccomp 和总体状态；
不能仅凭参数宣称 sandbox 生效。无关闭 sandbox 的 fallback。

## 原实现与拒绝边界

测试调用原 `configured_app()`，只提供无用户名、密码且指向不存在 Unix socket 的哑 DSN。
拒绝继承任何 `PARKWEAVE_*` 配置，不注入 provider、Case、会话、批准或成功 DTO。
整个工厂创建及 HTTP 服务生命周期内，测试进程的 `Store.connect` 守卫记录并拒绝每次连接；
任何连接尝试都会失败。没有数据库初始化、迁移、seed、worker，也不调用会访问 DB 的 `/health`。

额外的测试 middleware 在产品路由之前拒绝所有非 GET/HEAD；浏览器侧只允许同一
loopback 原点的首页、favicon 和两条指定 GET。测试中唯一 POST 是本地合同测试的守卫负例，
在路由前取得 405，不属于业务提交。浏览器业务写请求必须为 0。

真实浏览器检查：原首页响应字节与该 SHA 下 `web.html` 完全相同，原 inline CSS/JS 加载，
标题、页首与三个工作区按钮；非空非法 UUID 经真实点击得到原 JS 提示；合法形状但无真实来源
的固定 UUID 在空会话下经真实点击被拒；正式来源按钮在空会话下被拒。两者不请求记录入口。
浏览器发出的无 Authorization GET `/api/preparations`、`/api/preparation-catalog` 必须由
原路由取得 401。TXT 控件保持 disabled，不点击下载。不伪造凭据或绕过鉴权。

记录精确 source SHA、实际 Chrome/包/runner 版本、sandbox 状态、请求的方法/路径/状态、
JS 错误及结果到日志和 job summary。报告不包含请求头、会话、材料正文。
`PASS` 只能由实际完成的 job 支持；queued、skipped、无法读取结果均不能算通过。
仓库 REST 元数据的一次 `Forbidden` 已保存在忽略的运行目录，不再重试该接口。

## 验证范围

本地仅运行新增的一个合同用例，验证原页面、原无会话 401、路由前写守卫以及零 DB；
不启动本地浏览器。CI 对同一合同用例运行一次后，才启动一次真实 Chrome。
独审只读核对本增量及上述源盲判据，不执行动态业务或读取私有会话。

本地首轮实际结果：新增唯一合同节点 **1 passed**，pytest 退出码 **0**，
pytest 报告耗时 **2.75 秒**（外层控制器 7.055 秒），本地浏览器启动 **0**。
保留 3 条已有 Starlette/模型字段 warning；没有据此增装或升级依赖。
Python AST、YAML 和 workflow 的 shell 语法检查通过。原 7 个 workflow 字节不变。
JUnit、stdout/stderr 和退出码原件保存在忽略的 `.runtime/browser-readiness-ci-20261019/`；
远端浏览器执行结果必须另据实际 run 核对，本文本地结果不能替代它。

数据库、真实身份/Grant/分派/目录发布/批准、Case、worker、P1–P5、实际 TXT 下载、
业务冷恢复和 Windows 正式 AT 均为本轮 **NOT_RUN**。已过期业务窗口不延长或复活。
本轮结果不能代表完整项目验收或已有合法资料来源及 provider 已齐备。
