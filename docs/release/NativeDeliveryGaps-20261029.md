# 当前原生交付缺口与官方传输恢复

这是对原方案的源码诊断，不是准入证明。合成样例的提交、补材料、审核、确认、重开和持久回读不依赖正式园区资料；此前真实 Linux PG/API/worker 业务证据保留在其原提交，本轮不重复运行或改称 Windows 通过。桌面入口已完成 EXE→指定私有 Python→原 Controller→嵌入 WebView2 的源码接线；`cc559f58f8ad93c0a8177ebceef023b40f30d5ae` 修正 pythonw 与原解释器检查不兼容的问题。

## 上传失败发生在哪里

2026-10-29 原任务恢复后，正式运行时 Library 的一次只读 list 成功，且认证文件修改时间比旧失败记录新。基于这些新证据，仅调用一次当前技能的完整官方 prepared-upload 助手，拟保存原 `cc484a…` 桌面交接包；助手退出 1，标准输出为空，报 `hosted apps tools/list request failed with HTTP status 401`。失败发生于工具发现，尚未准备上传、传字节或创建 Library 文件 ID。该次状态记录时间为 15:43:59 UTC／北京时间 23:43:59，并非捕获到的精确 HTTP 请求时间。之后没有重试，新 `cc559f…` 包也没有上传。

成功的只读工具由当前会话运行时提供认证；上传助手在执行环境内按官方实现取得 Hosted Apps 身份。已知结果只能证明两个访问路径的结果不同，不能说全部 Library 授权失效，也不能说上传授权已恢复。当前专用 Apps 授权变量未注入，官方助手选择原 `CODEX_HOME/auth.json`；只核了选择路径、存在性和时间，没有读取其内容或显示秘密。现有证据不指向 GitHub 凭据、Space 页面权限、包大小或 Windows 下载故障。

用户可做的最小官方恢复步骤：

1. 在当前官方 ChatGPT/Codex 客户端确认仍是原账号；如果出现登录过期或重新登录提示，使用原登录方式完成，再恢复这个原 Park 云任务。无需提供密码、验证码、auth 文件或 token。[官方登录说明](https://help.openai.com/en/articles/7426629-why-cant-i-log-in-to-chatgpt)支持核对账号与原登录方式；这不是保证能修好云端助手的专门方案。
2. 如果网页及正式 Library 读取正常，助手仍是这个 401，则用户端没有已证实可修复它的额外按钮。通过 [OpenAI 帮助中心的右下角支持入口](https://help.openai.com/en/articles/6614161-how-can-i-contact-support)提交原任务 `01a17c57-0cc8-77d3-a425-852fc6f130e9`、上述时间/时区、原始固定错误及“原生 Library 读成功、官方 prepared 助手发现工具失败”。请求恢复该任务执行环境中官方助手使用的 Hosted Apps 会话。提交时自行在官方支持渠道填写账号信息，不附凭据文件、请求授权头或未经去敏的日志。

重新打开任务、网页可读、电脑恢复或文件时间变化均不单独证明上传授权有效。没有新相关恢复证据就不再请求上传；不改官方助手、不手填/搬运令牌、不改传输路线、不将私有包公开。正常 Windows Library 下载也须先有正式保存成功的文件身份，当前不存在。

## 三道门与缺失实现

| 门与实际函数 | 已有源码 | 仍缺什么 | 最小后续动作 |
|---|---|---|---|
| OWNER：`scripts/windows/lifecycle.py:setup_readiness()` | 派生 restricted token、仅修改本次派生 token 的 Owner/DefaultDacl、原 primary token 前后比较、CURRENT_USER DPAPI、保护文件、initdb 原管道/Job 的候选代码与组合已存在 | 历史新建暂停仍无条件返回 BLOCKED；生产准入策略未获独立 Windows 证据支持，并非只少一项用户账号。小型旧 harness 不覆盖跨 OS 身份及真实 initdb 全链 | 先取得限定安全调用的明确批准，在指定非共享测试根验证原 token 未变、派生 token/新对象、DPAPI 同身份重开/错误 entropy；跨身份用两个合法既有 Windows 测试身份，不能自动新建账号。实际 initdb 管道、Job、认证需另纳入明确范围，之后独审源码策略 |
| fixed journal：`fixed_windows_journal.py:require_fixed_native_acceptance()` | 原句柄、8192 字节双槽、固定偏移写/flush/回读、相同文件重开、排他、破损拒绝；Linux 和受控协议证据已有 | 函数仍无条件拒绝；缺目标 NTFS 下的进程中断恢复及持久性范围证据，缺可据此采用的生产准入策略。一次正常 file flush 不能充当断电结论 | 在本次新建的受保护临时对象上核 ID/SD 不变、排他、破损拒绝；单独限定本次子进程中断及冷重开。不得为此关闭用户电脑或声称断电已验。若要求断电保证，需支持该保证的平台测试环境及明确范围 |
| loader：`runtime_payload.py:RuntimePayloadPrerequisite.require_for_cluster()` | 冻结原字节与目录枚举、私有 DLL 名称闭包、已有 System32 CRT 的源/签名/版本/导出检查，原 Job 进程与 SQL backend 的 CRT 模块采样接线 | 函数 inspect 后仍无条件拒绝；完整 loader 实现未闭合：全部模块/Job 后代与动态加载来源、目标 API-set/forwarder 解析、最低工具链兼容策略尚未实现或取得可采信目标输入。CRT 两次采样不是整个加载器证明 | 先取得目标 Windows 版本/架构、API-set/系统 DLL 的正规只读证据及各冻结二进制的可信构建工具链版本，再据此实现精确来源/兼容策略；仍需在原句柄/Job 下核实际 initdb/postgres/SQL peer/API/worker，完成真实业务和重开。不借 PATH、系统 Python 或第三方同名 DLL |

当前 PG `postgres.exe` 原字节含 `compiled by msvc-19.44.35229`，但单个字符串不覆盖 ICU、OpenSSL、Python、wheel 等全部原生生产者，因此不据此发行整个包的最低工具链证明。后续源码已补完整私有符号/转发静态闭合与精确目标输入工具，具体字段、现包可取得项和 Linux 样例边界见[Loader 目标输入](LoaderTargetInputs-20261029.md)。先用真实包信息和可采目标导出/版本推进实现与有界测试，不将未知生产者元数据泛化为全部工程暂停。不会把 API-set 前缀、名称存在、14.x 或全部测试观察名当成 READY。

本轮进一步修复真实 PE 导出解析：数据可位于合法零填充节尾，不能一律要求其目标 RVA 有文件字节。修复不放宽表/字符串的文件边界，也不打开上述任一门。当前锁定 42 个 PG PE 的独立静态诊断核对 2214 处私有符号引用、484 个零填充导出，未发现缺失导出或解析错误；它不是系统 DLL、API-set、实际加载或 Windows 执行验收。

## 交付后目前允许的最小 Windows 动作

原唯一协调任务在 `E:\Software` 新建固定版本测试目录，先核外层/内层 SHA256、清单，再做有界只读依赖诊断及初始 GUI 标题/任务栏观察。不要运行旧 5a harness 验新包；不填新身份密码、不初始化 profile、不调用真实安全 setter、不改注册表/系统 runtime 或旧资料。当前正常 NEW 在 OWNER 处拒绝，REOPEN 在 fixed 门处拒绝，故初始窗口可测并不意味着主工作台已可进入。正式包名称、完整 SHA 与哈希以新一轮独立 delivery manifest 为准；不复用旧 EXE 冒充当前字节。
