# Windows 隔离运行 20：路径问题通过，身份初始化仍拒绝

运行：https://github.com/T1doo/ParkWeave/actions/runs/42028107349

用户明确允许用 r6 再执行一次。已持续跟踪到 completed/failure，无自动重试。冻结源码 049d16e34ed12de739fe38683c6aef5dfc6d879b，approval e6f3a08b8066b8b6dd5944119eebb894165aa7b3。

## 已确认事实

- 云端精确构建通过，候选 SHA-256 与 r6 一致；下载、源绑定、私有解包、严格 CRT 检查通过。
- run 19 的 PIN_COMMAND_PATH 共享冲突已通过。流程进入 NativeClusterPrerequisites.initialize_protected，在受限令牌初始化链返回 TokenRefused / TokenFailure。
- 原始去敏记录 windows-run20-native-result.json：CLUSTER / UNKNOWN，桌面 NOT_STARTED，captures_completed=0，native_acceptance=NOT_ACCEPTED。
- 当前堆栈没有足够信息区分 derive、默认 DACL 或 owner 子阶段，不能声称已定位或修复令牌问题。不能把 Windows Server 受控测试失败外推为所有 Windows 11 环境同样失败。
- 出错后的安全资源关闭含 TrialRefused / ExceptionGroup，不能宣称正常关闭通过。没有进行第三次授权之外的运行。

## 本地补充定位

- 新增 TokenFailure 的有限输出：固定来源的 phase 与 uint32/null winerror。不输出 primary_type/cleanup_type 的任意字符串、异常原文、token、SID、ACL、路径或环境值。
- 将 restricted_token_candidate 与 native_protected_bootstrap 纳入原 SourceSites 的固定源码核对，保留准确来源匹配要求。
- 相关测试 34 passed。没有修改令牌校验、派生、owner、DACL 或生产准入规则；这只是定位增强，尚不是功能修复。
- 另外，原 _pin_command_path 在真实 Windows 自有空目录的局部测试通过：旧父目录权限复现 0xc0000043，新只读父目录完成路径链身份/描述符核对。仅用元数据 stand-in 提供观察到的 volume，不创建真实 lease、PGDATA capability 或数据库。见 run19-original-path-pin-check.json。

本次授权已使用。任何下一次云端运行仍需新的明确授权；不将自动目标续行视为追加次数。

## 冻结的定位候选

本地临时提交 `7602ccac0e6a2de762ff41cf4035aa35dd6240db`，执行记录 null、工作流 disabled，未推送。

r7 诊断候选已构建：53,760,516 字节，SHA-256 `b1c20c7dfdf8cc14e6bdefc197b9cd37d06f15aee51be763a96f4854bbb48ce5`；manifest 哈希见 ci-frozen-candidate-r7.json。首次本地资源编译 60 秒超时，确认无剩余 zig 进程后用同一冻结源码本地重建成功，失败日志保留；不是云端重试。

如果获准下一次运行，仍为现有临时分支、一次最多 25 分钟、合成数据、无 main/发布/部署/真实数据/模型密钥、失败不自动重试。目的为取得缺失的受限令牌子阶段、固定源码行及数字错误码；此候选仅补诊断，不能预先承诺初始化会通过。
