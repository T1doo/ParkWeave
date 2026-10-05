# ENG-008 Windows只读文件候选：冻结范围

基线d997ba9ea1aa059b2a30eb8bd89fa5d1abee8d37，独立dev/f1-foundation。先做Microsoft官方接口核对，仅最小逻辑UUID合成文本资源访问；不扩F2、不上传/创建业务文件、不自动修改既有ACL、不启用产品Windows文件入口。

候选采用stdlib ctypes动态绑定官方NtCreateFile RootDirectory单名称打开、FILE_OPEN_REPARSE_POINT、FILE_OPEN只开已有、只读共享；type-neutral元数据句柄随后检查目录/文件类型，避免FILE_DIRECTORY_FILE与OPEN_REPARSE组合契约疑点。驱动盘根先CreateFileW句柄，验证GUID卷根/NTFS/固定盘，逐级元数据打开并保留句柄，再打开固定files和UUID.txt；任何reparse/失败拒绝，无路径重开/fallback。GetSecurityInfo按句柄读取owner/DACL；私有root/files/文件要求当前owner+protected DACL、仅已知简单ACE/可信SID allow，不改安全设置。内容同句柄ReadFile≤16KiB/单硬链接/hash/UTF8。

云端只验纯逻辑/ABI布局/注入假WinAPI调用流程，不宣称DLL语义或Windows原生安全通过。新增单独Windows候选测试脚本/自建私有fixture；只改新建测试路径ACL，不能改用户已有路径，不更改全局策略/权限或要求管理员开关。原生无证据时API/生命周期均保持拒绝，生产注册/写入仍未实现。若接口或平台不支持只报告拒绝，不引入unsafe fallback。
