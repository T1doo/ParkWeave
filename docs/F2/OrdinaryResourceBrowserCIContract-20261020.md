# 普通资源页面：一次真实浏览器技术验证

在 `aad99ae06d9fa39a0d45508ecb4116a0195f9779` 的本地技术演示之上，补此前仅直接API执行的资源页面操作。原演示是Node原页面处理函数＋真实HTTP/PG混合链，不能称全浏览器。这里不重跑原57次页面POST，不改变产品算法、schema、权限或原八个workflow。

## 原环境和安全执行方式

指定环境 `9ff7ff919935` 的一次 Chromium 启动原件显示：`chrome_crashpad_handler: --database is required`；随后 SUID helper 要求root所有而中止。实际 `/usr/lib/chromium/chrome-sandbox` 为 `nobody:4755`，`/usr/bin/chromium`也归nobody。不存在可据此确认的正常本地sandbox启动方式；不修改所有权或OS权限，不使用旧资源脚本中的 `--no-sandbox` 或任何禁用sandbox层的开关。保留原 `.runtime/pr0-local-ui-execution-20261020/browser-probe.json`，没有重试该本地浏览器。

用户已明确再次批准既定范围的有界免费CI。本片另设 `ordinary-resource-browser-once.yml`，只接收 `dev/pr0-resource-browser-20261020` 的push，限定公开 `T1doo/ParkWeave`、run1/attempt1、标准 `ubuntu-24.04`，一个job总上限6分钟。无其他触发器、matrix、cache、artifact上传、部署、自定义secret或权限扩张。checkout沿用固定SHA且不保留凭据，权限仅contents:read；如果仓库私有则在分配runner前跳过。

[GitHub计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)确认公开仓库的标准托管runner免费，较大runner另收费，本片不使用；日志和job summary不计artifact存储。[官方Ubuntu24镜像清单](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)列预装Python3.12、Chrome，实际版本仍以run记录为准。

复用原固定 `requirements-browser-smoke.txt`，包括既有项目依赖及Playwright1.62.0/pyee13.0.1/greenlet3.5.6，不升级依赖、不安装浏览器/FFmpeg/APT。不接入外部业务或模型。已核对[Playwright该版许可](https://github.com/microsoft/playwright-python/blob/v1.62.0/LICENSE)为Apache-2.0，[pgserver0.1.4许可](https://github.com/orm011/pgserver/blob/v0.1.4/LICENSE)为Apache-2.0；pyee与greenlet的既有包元数据分别为MIT、MIT AND PSF-2.0。没有新增许可接受步骤。

Chrome使用runner已有channel，`headless=True, chromium_sandbox=True`；CDP核对实际命令行无禁用sandbox/security参数，并实际读取 `chrome://sandbox` 核验PID namespace、Seccomp-BPF及总体adequately sandboxed。缺失或失败就退出，无fallback。为避免空HOME带来的crashpad目录不明，只给Chrome指定本次新建私有XDG配置/缓存目录，不改变系统HOME或sandbox。

## 浏览器与非浏览器范围

先验证浏览器sandbox，再由原CLI一次setup建立全新私有空业务库及两组明确合成主体。原serve启动真实普通API/worker/PG；仅用原 `prepare_case` helper经API/worker为两范围各新建并人工审核/确认资料，作为资源操作前置。没有fixture插入业务行、真实身份/Grant/分派/发布/批准或新Run assignment。这些资料准备POST不算浏览器用户操作。

两范围各用真实页面点击：资源标签→读取本域目录→原输入框选择资源/UTC时段/数量/120秒TTL/合成用途→原预检→HOLD，重复另一资源→刷新原占位列表并勾选两条→组合确认→协同标签原资料列表→原Case资源入口→选择该组合、填写说明、提交关联。期望每范围2次预检POST200及4次业务POST201，合计12次浏览器POST，其中8次业务写入请求键唯一。原请求/响应直接到真实loopback API，不fulfill DTO，不用页面evaluate发送业务POST；evaluate仅观察状态和单列的外域GET探针。原生datetime-local用Playwright填值，未验日历选择器手势。

只放行精确loopback原点、原页面必需只读GET及当前范围六个一次性POST预算。拒绝外站、其他端口、额外/重复业务提交，冷读阶段写预算为零。两条必要附带GET `/api/resource-bundles` 和 `/api/plan-approval/status`只读取原身份/功能状态，不启用隔离批准。只记录方法、路径、状态、请求键、body hash和合成记录坐标，不记录Authorization或会话。异常输出统一剔除本次合成会话；私有状态和失败日志不上传artifact。

各自原组合列表、Case关联面板和API独立GET必须一致；两方向各四条浏览器GET探针（对方组合、Case关联、两HOLD）均须403。正常停止自有API/worker/PG后，同一状态原serve重启，三种PID均更换；用新浏览器上下文重新输入原合成会话，经原列表和Case面板GET读取。关联完整结构只排除每读更新的顶层server_time，其余须与停机前一致；资源仍CONFIRMED，无重POST。末尾核对授权和marker不变、2Case/4HOLD/2组合/2关联/0Run assignment及自有服务正常停止。

## 验证与结果口径

本地只执行有必要的两项离线CI/网络预算合同检查及AST/YAML/shell/diff检查，不启动本地浏览器或重做旧资源API链。只读独审按原页面核选择器、异步响应与边界。独审修正的场景脚本问题保留：协同资料列表曾误定位service隐藏标签；第二HOLD需等本次响应精确UUID渲染，不能凭仍存在的旧卡计数；资源目录包装读取需精确放行并等待bundleActor。它们是推送前审查发现，未消耗CI或认作产品缺陷。

冻结脚本的两节点合同短测实际2PASS，未启动浏览器/DB；AST、YAML、workflow shell与diff检查通过。最终有限只读独审通过，未留P1/P2；独审仅AST/hash和源代码核对，无产品import、网络、私有会话读取或动态独测。脚本SHA256为 `086b370983c11d5da6037c0ade910efcbe20dbc2534a2db22c20dc3def44bacc`。原件保留在 `.runtime/pr0-resource-browser-20261020/`，CI结果另据实际run结算。

CI只有实际完整执行才可称通过；queued/skipped、无法读取、失败或只有API成功都不算真实浏览器通过。原Actions REST/日志接口的Forbidden不重试，公开HTML状态与父侧已登录浏览器的精确step JSON另列。失败保留，先给明确证据和范围，不自动再push/rerun消耗第二个执行机会。

## 本次公开CI结果

一次正常push提交 `d624b64c1f020939020007c5404ddce45e79df33` 触发[run1/attempt1：39349292485](https://github.com/T1doo/ParkWeave/actions/runs/39349292485)。公开HTML实际显示Success，总1分16秒；唯一 [resource-browser job](https://github.com/T1doo/ParkWeave/actions/runs/39349292485/job/118389402528) 为completed successfully、1分12秒，非跳过。原HTML及hash保留，并提交[公开结果摘要](evidence/ordinary-resource-browser-ci-20261020.json)。没有重试或第二次实际执行。

精确workflow的资源步骤没有跳过条件，执行冻结脚本；脚本仅在实际sandbox、两范围原资源页12POST（其中8业务写入）、关联回读、8跨域GET403、物理冷启动GET及末尾权限/计数/停服断言全部完成后返回0。**据此成功job可判断这些强制检查通过，这是对执行代码和公开状态的推断。** 本实例没有取得原step JSON，因此不填实际Chrome/runner版本、业务UUID、每条请求或sandbox原文。公开job页未加载步骤，公开summary HTML partial一次404，未重试；待父侧既有登录浏览器核对精确资源步骤原JSON，不能把本摘要当已读原JSON。

另保留平台注释：固定checkout所用Node20被runner改用Node24执行；本片未因此升级action。结果证据提交仅改文档，不重开run1或再次执行资源场景；后续push的run_number不为1，job门禁拒绝分配runner。

公开结果另经有限只读独审，确认34个原件hash、两节点XML、精确CI源码/脚本hash及公开job状态自洽，推断与原JSON未读取的边界明确。独审未做网络、产品import、DB、测试或浏览器执行。

此片不代表全57POST链、用户人工验收、Windows正式AT、真实资源预约/外部受理/现实履约、真实业务或整个PR0通过。此前165项仍为163PASS/1FAIL/2ERROR，超时根因未确立，不据此次结果改写。
