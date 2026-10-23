# Windows自包含封装候选：离线成果

冻结源码`00d62b1273f99c7fb7d879c939907ba6e63d74eb`；[构建器/双击入口/校验器/资产锁/定向测试](../../../../scripts/windows_portable/README.md)。本次是正常开发分支源码与证据归档，不是部署或端用户成品。

实际完成14项stdlib离线检查；首轮12与后续重复检查不加算。完整正例使用明确不可执行PE fixture和临时Git；真实24资产的静态组装单列，不称测试或Windows通过。真实PyPI依赖核查发现原筛选遗漏opentelemetry-api和Windows tzdata，已补齐后逐条核28个依赖边。

真实候选51,408,348B，SHA256 `d95f50c146889221f0156584c324b7e955995c3e63ac4c61fa76b8a84df12fa4`，2958成员/2957载荷；209件应用/launcher源码与冻结Git逐字相同。原PG八份默认文档引用的26项动态模块全部原字节入包，80件PE只做AMD64/普通/延迟导入静审。316条未决导入引用包括OS API-set、私有库寻址和MSVC缺项，不等于316个物理缺失DLL，更不是加载通过。

真实解压包完整性前后相同。禁止Popen/socket/urlopen后，仅加载原Windows生命周期模块并读取原setup_readiness，仍为OWNER_MUTATION_PAUSED；未调用main/doctor/setup，没有Windows二进制、PG、原生加载、安装、CI或用户电脑操作。

[evidence.zip](evidence.zip)含原检查日志、完整当前manifest/静态DLL图、实际获取及核验脚本、官方PyPI原JSON和26件原许可文本；[validation.json](validation.json)记录hash与范围。候选二进制仅留云端私有目录，不作为可用下载包分发。旧5a15候选保留且不转签；此包仅供后续编码/独审。

未完成：维护中的Python安全运行时、私有C++运行库与原生加载、SESSION/CONFIG安全创建及普通schema32/角色/seed初始化、干净Windows首次办理/退出重开。今天不占用户电脑窗口验证已知拒绝，也不在其电脑安装开发工具。下一切片应实现在原门保持下的私有实例初始化；具体安全权限的实际执行仍另核。
