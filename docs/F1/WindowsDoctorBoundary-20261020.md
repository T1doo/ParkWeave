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

## 第二阶段实测：首次 Join-Path 求值未返回

受测源 `3b41a5a62ed87a8e2f8ace5e26cab3a6b932c052`，[run39362533098](https://github.com/T1doo/ParkWeave/actions/runs/39362533098)／[job118431750331](https://github.com/T1doo/ParkWeave/actions/runs/39362533098/job/118431750331)，实际 FAIL。[原始安全 JSON](evidence/windows-doctor-source-boundary-ci-20261020.json)保留。Server门0.047秒通过，Doctor25.032秒原上限超时，driver25.14秒。

stderr严格为59字节的 `PS_DOCTOR_ENTERED`、`PS_COMMON_PATH_BEGIN` 两条固定标记，哈希 `0834982e8a8700d26c76fcfdb703e59be45d04d61b14fcbc7af2dd36e5626651`；stdout仍为空，无其他stderr/原错误协议。未收到 `PS_COMMON_PATH_READY` 或 `PS_COMMON_ENTERED`，因此确定原第一次 `Join-Path $PSScriptRoot 'Common.ps1'` 调用未返回；不是已经卡在Common内部、Get-Command、lifecycle或check_python。Join-Path内部是发现命令、加载模块还是cmdlet实现耗时，现有证据仍不能直接区分。

两窗诊断都只调用一次原Doctor、保留25秒和最小环境；第二窗由第一窗的实际边界触发，只细分未返回语句，不是相同输入循环重试。7合同独审独立通过、无开放P1/P2，没有更改安全策略、白名单或原生命周期退出判定。

## 最小修复及默认路径验证准备

仅将Doctor trace/default两支里同一个路径求值改成 `Microsoft.PowerShell.Management\Join-Path $PSScriptRoot 'Common.ps1'`。路径参数、dot-source目标、原始默认Python调用及其他包装器不改。不是用.NET改写路径语义或增加模块安装；不设置PSModulePath、不预加载外部模块、换shell或改变执行/错误策略。

[PowerShell5.1官方命令优先级文档](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_command_precedence?view=powershell-5.1)说明，未限定且未加载的cmdlet会搜索模块；模块限定名明确指定预期命令，并可按原自动加载规则导入。基于已定位的首次未限定Join-Path边界，限定内置模块是最小候选因果修复；文档本身不证明此runner内部发生了哪种等待。

验证准备是另一个一次性公开标准Windows CI，单次原 `powershell.exe -NoProfile -NonInteractive -File Doctor.ps1 -Python <同一venv>`，**不开TraceStages**，不重跑简单入口。沿用原25秒门/最小环境/Server20秒/17文件hash/fresh状态/psutil pin。默认输出必须是原Doctor JSON，model DISABLED、新Setup OWNER_MUTATION_PAUSED/NOT_ACCEPTED，exit0且stderr为空才通过；不把带trace的诊断通过代替默认运行。

10项诊断/验证标准库合同及已有5项标记合同本地通过，其中新增默认调用无trace参数/标记、原25秒/单次且超时不重试、坏JSON/非零退出/额外stderr均拒绝，以及精确分支/trace模式成对限定。它们不是尚未执行的默认Windows验证成绩。下一实测按真实回执填写。

## 默认修复验证：实际通过

受测源 `a25dbc9fedb5e08937897770deba1d6582f6e99d`，[run39362892738](https://github.com/T1doo/ParkWeave/actions/runs/39362892738)／[job118432910317](https://github.com/T1doo/ParkWeave/actions/runs/39362892738/job/118432910317)，job实际成功，公开总时长26秒。[原始安全 JSON](evidence/windows-doctor-default-ci-20261020.json)保留。

同最小环境的默认Doctor单次 **2.171秒、exit0、无超时**，原25秒门不变。明确未启用TraceStages，stages=[]；stdout499字节，为有效原Doctor JSON（已审判据要求ParkWeave/win32/model DISABLED及new_setup BLOCKED/OWNER_MUTATION_PAUSED/NOT_ACCEPTED），hash `c4faaa0c7f33e25ca4c0f601142ec94c9f0bb4a2014aafc500f18d04ed18fc17`。stderr严格0字节、空hash；没有用stdout阶段标记或直接Python调用替代原PowerShell入口。

Server门实际0.032秒通过，原生build26100/product_type3；Python3.12.10、psutil7.2.2、ImageVersion20261007.264.1与失败窗相同，driver总2.218秒。环境键集合与前次诊断一致；fresh状态始终不存在，17个受测源码前后hash保持。跨第二失败窗和本修复窗比较Windows实际17文件hash表，**仅Doctor.ps1改变，其他16文件完全一致**，符合只限定同一个cmdlet的源码改动。

这验证了限定Doctor首个Join-Path后，该runner本次默认Doctor恢复到原预算内完成；两次失败已经分别定位到dot-source语句和其中原Join-Path求值。尚未直接测到该未限定命令内部到底在哪个搜索/加载/实现环节等待，不宣称该机制已证明，也不据单次修复验证承诺所有runner上的表现。无需再盲跑相同Doctor或入口smoke。

本轮实际执行三个各自有界的免费标准Windows窗口：原标记诊断、依据该边界的细分诊断、最小修复后的默认验证；每窗各一次Doctor，原25秒上限，无重试、额外权限、sandbox关闭或超时放宽。Setup/Start/Status/Stop、完整fresh五包装器窗、Win11、正式AT01/04/05/34仍NOT_RUN；模型/数据库调用与owner/ACL/安全变更均0。仅Doctor的本次fresh默认行为通过，不写成整窗通过。

修复候选及默认验证工具已独审，独立10合同通过，无开放P1/P2；与作者重叠不相加。最终安全JSON和文字边界再次独审通过，独立核对两次实际环境键及源码hash差异吻合；独审没有重新执行Windows或取原始stdout，不能称第二次独立原生复测。既有pytest因当前环境缺模块仍NOT_RUN。归档后push受run1/attempt1门限制，不引入新的原生测量；实际跳过状态另核对，不预写平台回执。
