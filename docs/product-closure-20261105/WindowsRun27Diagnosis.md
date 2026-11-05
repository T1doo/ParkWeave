# Run 27 后续启动定位与 r15 候选

## 已取得的失败位置

run 27 的受控结果绑定源码 456bbea0：native_cluster._run:65 已进入服务端适配器启动，WindowsJobProcess.create:206 在原 backend.resume 抛出 OwnedJobError。该位置在 initialize_protected 返回之后，说明执行推进到服务启动，不能单凭调用顺序签收完整初始化。

原诊断没有 ResumeThread 的前一暂停计数、Win32 错误码和原进程退出状态。r14 补齐有限数字字段，仍只接受暂停计数恰好为 1，不重试、不增加权限、不读日志原文。错误后只读取本次创建并仍持有的原进程句柄，不发现或重开 PID。r14 在本机构建成功，但没有单独发起云端运行。

## r15 的路径修正

核查发现通用 WindowsJobProcess.create 仍使用 GUID image。已有普通 Windows 版本探针证明本包 initdb 的 GUID image 不兼容；不能据此断言 postgres 的 ResumeThread 错误已完全定位，但同类路径问题仍应修正。

PinnedExecutable 现在从原安装根句柄与原可执行文件句柄分别查询 DOS 表示，核对“同一根＋固定相对程序”完全一致。原文件哈希、GUID/NT 名称、目录绑定、ACL 及创建后的进程图像核对仍保留；每次 verify 重验 DOS 表示；未知、其他根、路径逃逸、ADS 或非规范路径拒绝。新字段仅供 Windows 加载器启动，不作为新增业务授权。

源码冻结 39ab9b218a09d4cf0fd5eac9460a13154d53796e，候选 b566ea7b…，完整绑定见 ci-frozen-candidate-r15.json。run 29（42088432491）是 r15 的单次隔离验证，审批提交 5be93e8d831759b95eacf02ce20ddc9d13ccb860；本记录不预判结果。

## 本地检查

- 路径、进程协议、映射来源与受控诊断：60 passed，19 Linux-only skipped。
- 线程恢复数值、Job 拒绝与关闭、诊断协议：126 passed，1 deselected。
- 未计入通过的用例 test_tree_cleanup_safe_projection_keeps_timeout_and_rejects_untrusted_metadata，原始失败是正式目录 SOURCE_SET_MISMATCH，完整初始结果保留在 thread-resume-diagnostic-tests-r14.xml。
- 其他初始原生 Job 测试失败源于测试子进程没有开发依赖 psutil 的搜索路径；仅为开发测试设置 PYTHONPATH 到已存在的工具与包内 vendor 后通过，没有修改产品子进程的最小环境策略、安装系统依赖或放宽清理断言。
- 正式诊断目录当前实际 503 文件、登记 405 文件，98 个未登记。只建立只读清单 diagnostic-catalog-inventory-20261106.json，没有把全套回归说成通过，也未绕过原目录守卫。

界面与录屏软件包没有改动，所有这些诊断只在工程记录中。
