# Doctor 路径求值与 dot-source 边界诊断

基线 `e67421f95fe4f7ff9f8088cfc611dda9dced9b0b`。用户明确授权在入口实测通过后继续必要的有界免费 Windows CI 和证据支持的最小修复。没有重复 PowerShell smoke、已成功浏览器 CI 或网络检查；没有更改 sandbox、执行策略、环境白名单、main 或用户电脑。

## 第一阶段：Doctor 进入，但原首个 dot-source 语句未返回

受测源 `ce4dfe79ded9dcc8ef8b12a9b8a0c822a2794717`，[run39362136954](https://github.com/T1doo/ParkWeave/actions/runs/39362136954)／[job118430503571](https://github.com/T1doo/ParkWeave/actions/runs/39362136954/job/118430503571)，实际 FAIL。[完整安全 driver JSON](evidence/windows-doctor-stages-ci-20261020.json)原样保留，不把诊断运行算作包装器整窗通过。

单次原 `powershell.exe -NoProfile -NonInteractive -File Doctor.ps1 -Python <同一私有venv解释器> -TraceStages`，原最小环境及25秒上限不变。真实 Server 门0.063秒通过，原生build26100/product_type3；Python3.12.10、psutil7.2.2、ImageVersion20261007.264.1。Doctor实际25.047秒触发 `TimeoutExpired`，exit_code=null，driver总25.172秒。

stderr严格只有28字节 `PW_STAGE:PS_DOCTOR_ENTERED\r\n`，SHA256 `db0faee82fc011f73b44f896f4000571c86f64b21bcc056f99be8889c7fce1d5`；stdout为空，SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。没有非标记 stderr、PowerShell错误类别或原生命周期错误协议；解析结果 DIAGNOSTIC_UNAVAILABLE 仅表示没有原错误协议，不是认证错误。原始两流（含超时部分输出）按原字节保存于本 runner 的 RUNNER_TEMP，公共证据仅保留完整哈希/字节数/原超时类型，不发布原始内容；runner结束后不声称这些临时原始文件仍可下载。

Doctor入口已执行，`PS_COMMON_READY`未收到，故原 `. (Join-Path $PSScriptRoot 'Common.ps1')`语句未在预算内返回。Common顶层是否进入、Join-Path是否返回及其模块加载原因尚不能判定；解释器解析、lifecycle和check_python没有进入标记。17个本次受测启动器/底层文件前后hash一致，应用状态始终不存在，数据库/模型/owner/ACL安全变更均0，其他四包装器及完整AT/Win11仍NOT_RUN。

## 针对已观察边界的细分

下一窗仅细分这一原语句：trace支路在原Join-Path前后标记；Common首可执行语句标记，保留原StrictMode/EAP Stop；Common内原PythonCommand路径求值前后及dot-source返回标记；PythonCommand文件进入及函数定义完成标记。默认关闭时原一行dot-source和原调用保持。

Common/PythonCommand各用默认false的独立脚本switch，避免其他包装器/准备步骤在StrictMode下读取不存在的TraceStages。没有为诊断增加Test-Path、Resolve-Path或Get-Command等前置cmdlet，避免改变首次加载观察点。所有新增标记仍是固定.NET stderr WriteLine+Flush，不输出路径、环境或参数。

共享有界driver增加精确的新分支入口；只允许两条已指定dev分支，不能用main覆盖。细分workflow沿原已审公开标准windows-2025路径，run1/attempt1、job6分钟、metadata20秒、Doctor25秒和仅psutil7.2.2依赖pin不变。此处细分准备不是新实测通过，也未据尚未验证的autoload猜测改正常运行路径。Python stderr被旧PowerShell包装为NativeCommandError的可能仅是后续解释限制；第一窗没有执行到Python，所以不能用该可能解释已观察超时。

7项标准库诊断合同本地通过；前一阶段6项独审合同及已有5项默认标记合同通过，重复范围不叠加。当前环境缺pytest，既有pytest回归仍NOT_RUN，没有安装测试依赖。细分实测及后续因果修复按真实回执另记。
