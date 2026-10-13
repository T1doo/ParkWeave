# 仅保护环境准备探针：待精确范围复核

本候选仅离线开发与纯DI测试，`scripts/host_case_once/prepare_approval.json` 和原host Case approval均为false/null/null。旧run38373923111的授权已耗用，结果仍1PASS/1FAIL/19NOT_RUN、cleanup=false、准确失败原因UNKNOWN_NOT_PUBLIC。本入口不复用该工作流或授权，不宣称已复现11秒失败。

入口 `scripts/host_case_once/prepare_once.py` 和独立工作流 `prepare-only-security-once.yml` 用于确定源码复制、解释器/标准库复制、19wheel下载/核验/安装、固定纯导入究竟在哪项失败。它不启动controller、worker、模型、服务器、浏览器或PG；不做Case建单/取消/权限试验。复制bundle中包含旧业务源码，但不导入或执行其控制器。

## 下一次实际操作的精确边界

此处保留原准备阶段root保护语义以检验该阶段本身，**实际运行包含安全相关所有权/权限动作，不能归为完全普通无权限变更的导入测试**。全部动作仅限新免费GitHub官方ubuntu-24.04 x86_64 VM、本候选的Git冻结源码和下列新资源；不改变已有系统解释器/标准库/软件包、用户/组、账号、凭据、数据库、挂载、Grant或registry。普通用户无root的导入测试不能证明本保护准备阶段通过，若改成该替代范围应另写清单，不能混用结论。

| 资源/操作 | 精确范围 |
| --- | --- |
| 一次claim | `/tmp/parkweave-prepare-only-once-20261013.claim`，root 0600，O_EXCL/O_NOFOLLOW创建一次，内容仅冻结source SHA。成功/失败均不删除以拒绝同VM重试；VM销毁时消失 |
| 一个新T | `/tmp/parkweave-prepare-<uuid4hex>`，root 0711；仅系统UUID标识，无随机业务凭据；记录创建时dev/inode用于清理验证 |
| 私有目录 | T/private，root 0700；空empty.netrc 0600、wheels目录、dependencies.log、import-stderr.log、失败时prepare-failure.log。不读取用户netrc/keyring或任何现有凭据 |
| 源码副本 | 从冻结Git对象复制 `src/parkweave`、`scripts/linux_trial`、`scripts/host_case_once` 到T/source，最多512路径；目录0755/文件0644。Git以原checkout非root owner读取，stdout捕获，全部Git stderr=PIPE；不改git config/safe.directory/凭据 |
| 官方运行时副本 | 仅读 `/usr/bin/python3.12`、`/usr/lib/python3.12` root-owned/nonwrite正规目录/文件。复制到T/environment；只对**新副本**chown(0,0)、目录0755/文件0644、bin/python3.12 0755。保留两个已审固定链接例外：省略sitecustomize外部hook，不读取/etc；同根固定sysconfig alias物化正规文件。其余链接/链/权限不符拒绝，O_NOFOLLOW，无任意resolve |
| 19wheel依赖 | 原完整哈希锁不变。官方系统python/pip `--isolated` 向 `https://pypi.org/simple` 下载原锁定19个wheel到T/private/wheels；hash/bytes/metadata exact验证后 `--no-index --no-deps --no-compile` 安装到T/environment/lib/python3.12/site-packages。无额外pip安装、apt、system依赖修改；每次下载/安装最多90s，原pip public输出转T/private/dependencies.log |
| 纯导入子进程 | 仅T/environment/bin/python3.12 `-I -S -B`、空白最小LANG环境、cwd=/、固定受保护sys.path。导入sysconfig及fastapi/uvicorn/psycopg/pydantic/httpx五顶层包并验证__file__在T/environment，get_config_vars非空且sitecustomize未加载；不导入ParkWeave业务入口、不连接数据库/网络/模型。stdout只接受固定`PREPARE_IMPORTS_PASS`加一个LF换行字节，stderr只写T/private/import-stderr.log，最多30s |
| 无其他资源 | 不创建用户、组、PG cluster/角色/数据库、业务资料、Case、socket监听、memfd/密封fd、模型请求或随机凭据；不扩大安全权限、不配置网络/凭据，不运行原完整业务验收 |

gate在任何claim、新目录、timer、准备/导入子进程或网络动作前要求root、`-I -S -B`、准确新approval、准确新branch、公开T1doo/ParkWeave repo、push、官方GitHub Linux runner、run_number=1、run_attempt=1。Git证明执行commit仅一个父提交（精确冻结候选），差异仅新prepare_approval.json的三字段激活，父提交该文件必须仍pending，checkout干净；gate自身允许以原checkout owner执行只读Git子进程核验。不手工workflow_dispatch、不改旧approval或旧执行branch，不自动重试/补跑；任何明确拒绝停止该动作并保留失败。

## 时限、清理和结果

总job最多12min，运行step最多10min；通过gate后进程SIGALRM主窗口480s，成功清理或失败保存日志窗口最多60s。Git读取每项5s；两pip阶段各90s；纯导入30s，subprocess.run timeout/异常杀掉并等待其自有直接子进程；不存在业务daemon。runner超时/硬中止不能宣称清理成功。

成功只在root的dev/inode、root owner、nonwrite目录、/tmp父目录和固定前缀仍匹配且fd-safe shutil.rmtree可用时删除整个新T；核T确实不存在后FILES_REMOVED=PASS、cleanup=true。成功日志随T一同删除。claim仍保留到VM销毁。准备、导入或确认T删除之前失败，停止后保留尚存在的新T/private和原始诊断文件在当前临时VM，不上传私有日志、异常文字、路径、argv或stderr；cleanup=false，FILES_REMOVED保留NOT_RUN或实际失败，不伪造删除签收。若失败发生在T之前公开failure_logs=UNAVAILABLE；失败部分目录也不越权补清理，仅随新VM销毁。若最后timer复位失败发生在已确认删除T之后，整体仍FAIL/PROTECTED_RUNTIME失败，但保留真实FILES_REMOVED=PASS和cleanup=true；此时T已经不存在、failure_logs=UNAVAILABLE，不能声称仍保留私有日志。

公开stdout仅现有封闭JSON schema：source SHA、phase/error固定枚举、21case状态、cleanup、failure_logs和至多32个`case/substage/check_id/source/line`。该探针成功只证明GATE、PROTECTED_RUNTIME、FILES_REMOVED三项PASS，其他18项NOT_RUN；不是完整host/Case验收。诊断行来自已审代码对象身份和编译行集合，外来代码为0，0..10000。异常/stderr只在已允许的新T/private；不能据此回填旧失败准确原因。

## 精确下一次批准内容（尚未批准）

先由父级复核本候选完整交付SHA和本清单范围。若明确批准，应批准**该完整候选SHA**在新免费公开GitHub ubuntu-24.04 VM进行**一次且仅上述保护环境准备和纯导入**、允许上述新T内root ownership/chmod、一次claim、官方19wheel下载/离线安装、成功清理/失败VM私有保留和上述时间上限。执行branch只能为 `dev/f2-prepare-only-security-once-20261013`，approval_ref只能为 `USER_CONFIRMED_PREPARE_ONLY_ONCE_20261013`；只创建一个父为该候选SHA且仅激活新approval三字段的正常commit。当前新候选branch不触发此工作流，原approval仍false。未取得明确新批准不创建激活commit、不push执行branch、不运行入口或CI；本轮只推正常候选branch。

实际准备成功后，host身份/PG/权限/业务Case取消的21项组合仍是独立剩余验收，必须与本次探针结论区分。
