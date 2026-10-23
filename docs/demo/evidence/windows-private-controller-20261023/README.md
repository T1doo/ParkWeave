# 私有实例新建/重开控制器候选

[`controller.py`](../../../../scripts/windows_portable/controller.py)接线原真实CREATE/schema32、冻结roles和原seed消费者，并区分初始化READY、应用运行、已确认停止和UNKNOWN。重开不调用CREATE/迁移/新会话或seed；原创建证据不序列化或冷恢复。生产新建门保持暂停，进程/秘密/安全文件/lease均为未实现的显式端口，未加入双击入口或载荷，不是可运行安装包。

`offline-tests.log`是最终一次24项stdlib离线fake检查原输出，不加计此前20/21/23项。含实际schema函数在fake连接下的SQL→rollback→close双故障、后续清理错误、2501项链/循环/异常组、部分新建和同目录重开拒绝路径。正向模拟授权与传输不构成PG/native验收。`validation.json`给出代码/日志hash、15件原门和SQL逐字保全、initialize除doc外AST相同及独审限定ACK。

未确认release后控制器不再写journal；未来生产lease须用真实锁归属保留拒绝状态或拒绝不确定handoff后的再次获取。fake检查不证明此安全实现。没有PG、Windows、浏览器、CI或用户电脑执行；旧Python/DLL闭包、原生owner/SESSION-CONFIG与成品首次运行/退出找回仍未验。
