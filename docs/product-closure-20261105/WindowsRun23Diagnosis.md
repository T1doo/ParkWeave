# Windows 运行 23：管道通过，初始化预算交接修复

运行：https://github.com/T1doo/ParkWeave/actions/runs/42045112136

在用户持续授权范围内，源码和产物分别冻结，单次上限 25 分钟；没有 main 修改、发布或部署。

## 实际结果

约 408 秒后 completed/failure。精确构建、传递、解包、CRT 检查通过，受限身份和原密码管道创建/验证已继续到后续 _freeze。初始化进程尚未创建时，_profile_held → PGDATA _verify → _time 返回 DEADLINE；整体 UNKNOWN / NOT_ACCEPTED。

原始去敏结果 windows-run23-native-result.json。清理含 LeaseRefused 等错误，不宣称正常关闭通过；工作台和办理未运行。

## 源码交接问题

配置阶段建立 PGDATA 对象时使用配置截止时间；FixedClusterProcesses._configuration 随后调用 require_inputs，该原检查默认使用 10 秒观察窗口并把它留在 target.deadline。initialize_protected 后续复用同一 target，却没有交接初始化调用方仍有效的明确截止时间，因此 token/pipe/载荷准备后 _freeze 再访问目录时可能使用过期的旧观察窗口。

## 修复

require_inputs 增加可选 deadline 参数，仍通过原 _run 入口、原 lease/输入身份/路径检查。initialize_protected 在进入 bootstrap 前用调用方原有 deadline 重新验证；原 _run 仍裁剪到 source trial budget，保留 <=30 秒的局部契约，不创建新的计时起点或无限延长窗口。

bootstrap 继续在短输入检查退出租约入口后调用，避免把 _freeze 等公共入口错误嵌套在同一 lease entry 内。

定向 6 项测试覆盖过期旧窗口交接、source 上限裁剪、过期或过长截止时间拒绝、相同 inputs 对象身份和非嵌套调用。测试使用受控时钟和接口，没有原生/数据库执行，目标环境效果待下一次冻结候选实测。

扩大回归共 10 passed、4 failed。四项均为 test_native_subwindow_budget 的旧 fixture 在 Windows 调用 claim_fresh 时先触发 OWNER_MUTATION_PAUSED，尚未进入预算断言；保留为本机 fixture 阻断，不跳过/放宽原门，也不记为通过。新的 6 项与已有路径绑定回归已进入断言并通过。
