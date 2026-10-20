# Windows原AT自动化子项与本次原生预检

基线 `9276a730a3013f735bcc21bc372aec05b0857ea0`。本轮按用户批准的有界免费Windows runner范围，对照原[验收规格](../验收规格.json)、[产品§9](../sources/V1/平台产品设计%20(2).md)和现有入口；不重跑已接受的资源浏览器切片，不把Windows Server当Win11，不以缺人工桌面阻塞整个本地项目。

## 原条款与实际可执行范围

| 原条款 | 可自动化部分 | 当前结论与精确缺项 |
| --- | --- | --- |
| AT-01：原生API/worker/DB存在、数据可读、停止再启动；错误清晰、不覆盖配置 | CLI解析、Python位宽/平台、正常停启、错误处理都能自动化，不必先人工视觉 | 本轮只验证原CLI fresh Doctor与缺配置/首次安装拒绝。成功启动链缺合法安装初态；不将拒绝当成功启动或整项PASS。 |
| AT-04：跨企业/园区资料、Case、结果、匿名占用隔离 | 后端请求/权限/持久状态可自动化 | 仍需Windows合法schema/会话/业务fixture；当前native pytest迁移入口明确拒绝，不能借Linuxfixture证明或造配置绕过。 |
| AT-05：文件/凭证边界 | 许多恶意路径与日志检查可自动化 | 本次只读源审查，未运行此整项；Windows实际根目录/descriptor与创建authority仍有独立缺项。 |
| AT-34：干净重建、关闭网页/API/worker、重开与时效 | 已合法安装时，网页/API/worker关闭及重开可自动化；不是全都人工项 | 当前没有合法Windows安装/迁移初态；托管Server新job不是同一Win11机器的关机/休眠恢复。不得关闭runner机器伪造同机冷恢复。 |

原产品§9.2要求关机/休眠期间本地计算停止，重开核对过期与已生效动作，不重放。Win11 x64是原§9.1主平台；Server可提供精确的原生工程子项证据，不能替代平台、受保护文件或整套AT。原AT-02真实模型链仍不在此次无模型授权内，但不阻塞此预检子项。

已核实的代码阻断：[`setup_readiness()`](../../scripts/windows/lifecycle.py)固定返回 `BLOCKED / OWNER_MUTATION_PAUSED`，[`setup()`](../../scripts/windows/lifecycle.py)在检查Python、venv/pip、DSN、数据库、ACL前要求该前置。现有[`synthetic_session_file`](../../src/parkweave/synthetic_session_file.py)生产创建仍拒绝owner mutation；既有安全配置/会话不会由这个预检创建。

[ENG104](../F2/ENG104-CreationReceiptAdapter.md)已有显式数据库创建回执候选及Linux实际PG证据，不能再称候选未实现；它**没有接到默认Windows lifecycle或native pytest入口**。`tests/conftest.py::pg`在Windows明确拒绝当前未评审迁移025创建适配，已有目标不能补造receipt。[generation候选](../F2/ENG100-WindowsGenerationAuthority.md)也不是受保护authority部署。只给DSN、恢复旧`native_suite`或打开默认布尔值均不能解决这些问题。

原`Engineering.ps1 Prepare`会执行Set-Acl、初始化cluster、建角色和DB，不能在本次范围中悄然恢复。原Windows workflow当前只执行已验过的两个controlled parent/child Job测量；它既不执行应用生命周期，本轮也不重复它。预装PG可用与否不等于已有应用安装授权，不启动/改变其默认停止且禁用的系统服务，不使用公开默认凭据或发现凭据。

## 最小原包装验证

新增薄调用器只调用既有 `Doctor.ps1`、`Setup.ps1`、`Start.ps1`、`Status.ps1`、`Stop.ps1`，不改它们或产品算法。使用`powershell.exe -NoProfile -NonInteractive -File`与明确Python路径，无ExecutionPolicy改动。预期结果：

1. fresh Doctor实际执行win32/Python3.12/x64检查，exit0并报告BLOCKED/OWNER_MUTATION_PAUSED及NOT_ACCEPTED；exit0只代表Doctor成功。
2. fresh Setup exit1及原固定OWNER_MUTATION_PAUSED；不安装应用依赖、不接触DSN/DB/ACL。
3. 无配置Start exit1及原CONFIG_MISSING诊断；Status exit1及原缺配置错误。
4. 无managed record的Stop exit0且明确无操作；**不是成功停止服务**。

每次调用前后`.runtime`与`.venv-windows`必须仍不存在，原包装/生命周期/相关源码hash相同。没有既有配置对象，所以不声称本次实测“既有配置不覆盖”；也不创建假配置解除Start拒绝。输出与失败原件只放本次`RUNNER_TEMP`新目录，不在应用状态根制造安装。执行器只保留OS环境和本次显式UTF8/禁止pycache设置，应用子进程不继承任何DSN或模型配置。

## CI、依赖与证据边界

用户已批准在既定范围使用有界免费Windows CI。[GitHub计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)确认公开仓库标准托管runner免费；本片限定公开T1doo/ParkWeave、精确开发分支、标准windows-2025一个job/6分钟，contents:read、固定checkout SHA、不保留凭据，无其他触发器、matrix、secret、cache、artifact上传、部署或安全权限变化。首次run1/attempt1在checkout即失败；有明确原因后仅补run2/attempt1，之后push或rerun均在job前拒绝。

[官方镜像清单](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md)标明Windows Server2025、已有Python3.12和PostgreSQL17；实际版本由run另记录，不拿清单当实测。只从显式`RUNNER_TOOL_CACHE/Python/3.12.x/x64/python.exe`选择已有最高补丁版，再经原`PythonCommand.ps1`解析并核对3.12/x64；不依赖默认PATH碰巧指向3.12，缺失或不匹配就拒绝，不下载Python或猜个人路径。在RUNNER_TEMP新venv仅装原`requirements-windows-candidate.txt`已有的唯一所需包`psutil==7.2.2`（只用wheel、无依赖、无cache、零下载重试）；[该版原许可](https://github.com/giampaolo/psutil/blob/release-7.2.2/LICENSE)为BSD-3-Clause，无新增许可接受步骤。不装PG、Linux pgserver、完整应用依赖、浏览器或模型。Start/Status/Stop在缺配置/record前也先import psutil，不能忽略这个已有依赖。

本地只做AST、YAML和范围检查；未在Linux模拟成原生通过，未写新测试框架、未改固定AT状态。最终独审及实际CI结果另记录。公开状态与原step JSON分开；原Forbidden Actions REST/日志接口不重试，失败不盲重跑。

推送前有限只读独审通过，无开放P1/P2。已闭合超时丢失输出/阶段与默认PATH版本不确定两处薄调用器问题，未改产品。冻结脚本SHA256 `1537e2c5cc3e92d25e2192c5a9edaa6eb2698da3cc8516d50227c94c59ba09b4`，workflow `1b1e3a0d288b23e9d6fc41362edcaf464ae933d9333393e02d583b8f12fc260d`。独审只读源码、AST/hash和旧原件，没有动态测试、网络、产品import或Windows执行。

首次实际CI [39353359602](https://github.com/T1doo/ParkWeave/actions/runs/39353359602)，源SHA `b99aa8b3765bd27f044aa93e4bfc81f3159b8ca1`：[公开job](https://github.com/T1doo/ParkWeave/actions/runs/39353359602/job/118402464025)显示checkout失败，10条注释均为历史`docs/F2/evidence/known-not-started-frontier-20261016`深路径`Filename too long`。依赖准备和原生包装器step均Skipped，原生调用为零；不能称预检失败或成功。[失败回执](../F2/evidence/windows-native-preflight-first-failure-20261020.json)保留公开注释和HTML hash，原失败不覆盖。

根据这个明确原因，修正仅将checkout设为Git cone sparse模式，保留整个原`scripts/windows`、`scripts/windows_ci`、`src/parkweave`及Git cone默认的根文件（含`pyproject.toml`），不检出无关历史证据目录。未改Git全局设置、LongPaths注册表、执行策略、安全描述符或原产品文件；实际原包装器源码仍前后hash一致。只允许同workflow的第二次新push/run2/attempt1，不重跑原失败run，不放开无界重试；补跑结果另记。

成功启动/正常停止/重启及业务隔离的下一最小输入是：合法Windows安装初态中的受保护配置/会话和原目录、已安装原固定依赖、合法受限app DSN/schema及合成业务权限；若从fresh新建，则需先接通并评审原生创建/迁移与文件authority边界。收到这些输入时可直接复用原Start/Status/Stop和既有native suite相应子项，不要求先完成全部Win11人工/真实模型门，也不能由此次错误路径测试补造这些输入。

## 旧165项超时：仅原件定界

[脱敏取证摘要](../F2/evidence/windows-at-timeout-forensic-20261020.json)从原XML、stderr和现有诊断直接计算：原失败165窗口在旧主机cd8f6963ff1b于2026-10-19 09:28:36.541875开始，按XML耗时668.198秒在09:39:44.739875结束；现有连接诊断始于09:40:22.249628，PG日志始于09:40:23.960，属于随后49PASS窗。两个窗口没有时间交集。

原`target_read`在prepared→ADD连接超时，早于撤销READ/另派；其DROP teardown语句超时。原`WITHDRAW[material]`在fixture GRANTS连接超时并清理超时。后窗1880次连接/关闭均成功，失败采样为0。现有后窗日志不足以识别原失败的连接等待、锁持有者、资源压力或未关闭连接；不能因DROP超时直接断言泄漏，也不能把后窗低负载当原窗原因。

原165唯一项仍163PASS/1FAIL/2ERROR（XML166记录含同例call/teardown）；根因未确立。最小因果缺项是**原失败时刻**同一集群/DB的连接与PG活动/锁/服务日志关联；没有这些原件，重复通过不证明原因。此次没有重跑165/49、没有连旧库、没有改2秒连接或5秒清理预算。此未知只限制对应可靠性结论，不暂停其他已授权开发。

补跑修正已再经有限只读独审，无开放P1/P2：公开失败注释与step结论吻合；17个原文件字节及根文件齐全，最大相对路径55，未扩安全/业务边界。补跑冻结脚本SHA256 `5bd870f0874acbb21a06a8e8c827b0d5ee7352f7711e33305dd0ccf6fdaede3a`，workflow `beb3aef29a89d9ebb179e9d4af353969a6252c926f8288bb930071cc3610c79e`；独审无网络、动态或原生执行。
