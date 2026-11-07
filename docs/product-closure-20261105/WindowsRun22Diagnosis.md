# Windows 运行 22：受限身份通过，管道回读的本地复现与修复

运行：https://github.com/T1doo/ParkWeave/actions/runs/42041684226

在用户批准 r8 后，用户进一步授权同范围连续修复验证，无需逐次确认。原有临时分支、合成数据、每次 25 分钟上限、无 main/发布/部署/真实数据/模型密钥范围保留。

## 云端结果

运行约 309 秒后 completed/failure。精确构建、传递、源绑定、私有解包及 CRT 检查通过。进入 protected bootstrap 的 server.create 后 PipeRefused/PipeFailure，尚未启动 initdb 或桌面。

按实际源码调用顺序，先前的令牌派生、默认 DACL 和 owner 准备已返回；run 21 的组属性检查阻断已通过。本次 ControlFailure 的 cleanup_count=0，但整体仍 UNKNOWN / NOT_ACCEPTED，不把没有清理错误等同正常业务退出验收。

原始去敏结果 windows-run22-native-result.json，汇总 WindowsRun22Result.json。云端原日志没有细分 PipeFailure 阶段，不能声称本地复现已证明云端唯一根因。

## 本地实际复现

只用当前 Windows 用户创建并关闭随机私有空管道，没有客户端、密码、数据写入、派生令牌、数据库或服务身份。调用原 _create_native 与 _verify_native，不创建注册 lease/pipe 能力。

原流程在 GetKernelObjectSecurity 成功后因 LengthNeeded=0 被拒绝。在沙箱及普通 Windows 进程均复现。对 1024/4096/65535/65536 固定缓冲区分别只读观察，均为 API 成功、原生描述符有效、独立 GetSecurityDescriptorLength=92，而 LengthNeeded=0。只记录长度/头部偏移等标量，没有 SID/ACL 内容。记录 run22-local-pipe-readback.json。

## 修复

固定 64KiB 缓冲区的全部相对偏移先经过原纯解析器验证：当前用户 owner、受保护 DACL、唯一允许 ACE、原权限 mask 和无额外 group/SACL 检查保留。随后原生结构验证及独立长度验证；长度必须有界，非零 LengthNeeded 必须一致；最后再按精确长度执行原解析器。

不因 LengthNeeded=0 单独放行，不跳过描述符/权限/句柄检查，不重试查询或改用不受控的路径。

GetSecurityDescriptorLength 对有效描述符提供原生长度的 API 规范：
https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptorlength

本地 36 项检查通过，其中一个是原管道边界的真实 Windows 测试，其他为受控 FFI、描述符和去敏诊断回归。普通 Windows 进程的原边界测试也通过，关闭无错误。

同时补齐固定来源的管道、客户端、受限启动、进程和数据库端点源码位置，以及有限 PipeFailure phase/数字错误码，避免后续只剩无法定位的类型名；不输出身份、凭据、环境值或异常文本。

下一次隔离验证按持续授权执行，但仍逐次冻结源码与产物，不盲目重跑相同失败。完整初始化、办理与冷重开尚未通过。
