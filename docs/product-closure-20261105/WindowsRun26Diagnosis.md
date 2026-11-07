# Run 26 启动路径定位

## 直接观察

2026-11-06 对 r12 原包 PostgreSQL bin 文件逐个核对清单哈希后，仅执行 initdb --version。普通 Windows 进程下四项对照：DOS 程序路径配 DOS/GUID 工作目录均退出 0，输出 PostgreSQL 17.11；GUID 程序路径配两种工作目录均退出 3221225485（0xC000000D），stderr 为零字节。这复现了 run 26 的退出码，但不是受限身份初始化验收。

首次沙箱探针在 GUID 启动上超时，并出现用户可见应用程序错误框；已停止该探针。随后普通进程完成上述对照。检查未发现仍存活的对应 --version initdb；Computer Use 当前窗口列表未找到 initdb 错误窗。不能据此声称曾实际点击关闭。

缓存探针现补进程局部错误模式并在 finally 恢复，不改系统设置；不继续在用户桌面重复失败启动。原始结果见 initdb-path-version-probe-20261106.json。

## 最小修正

restricted_initdb_candidate 保留原 GUID/NT 文件身份、文件哈希、私有 ACL、PGDATA 全路径持有与重验。用于 CreateProcessAsUser 的 image/argv 改为从已核验 PGDATA 的 DOS 安装根推导，并要求与同一已持有 executable 文件句柄查询的 DOS 路径逐字（忽略大小写）一致。每次 freshcheck 都重验，不接收调用方任意路径。工作目录和其他令牌、Job、管道、就绪、退出守卫不变。

新函数只做路径表示转换，不发放身份或文件权限。源冻结提交 456bbea0f2303fbda52b535639dfd1464680adee，工作流禁用、执行记录 null。

## 验证与限制

32 项定向检查在普通 Windows 进程下通过，包括中文空格路径、其他安装根/数据路径/可执行文件/ADS/UNC/非规范表示拒绝，以及原路径共享冲突回归。沙箱执行原生用例时得到不同的访问拒绝；普通环境首次遇到旧 pytest 临时目录权限冲突，改用工作区新的专属临时目录后 32 项通过。记录保留，不把这些环境失败隐藏为产品通过。

尚未证明新路径在 GitHub 隔离身份下完成 initdb、数据库/API/worker、真实办理与重开。候选构建进行中；未发布、未修改 main。

官方 API 参考：[CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw)、[Windows 路径表示](https://learn.microsoft.com/en-us/dotnet/standard/io/file-path-formats)。API 文档没有证明本包对 GUID image 的兼容性结论，该结论来自以上实际对照。
