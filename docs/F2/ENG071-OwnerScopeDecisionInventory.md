# ENG071 owner 范围集中决策清单（只读，不执行权限变更）

本轮保持原授权：只有固定 SESSION/CONFIG 首次新建可执行既有 verified-owner 事务；不修复任何既有 owner/ACL，不新增其他对象 owner 设置。实际 Restart 对象及原生 owner 子阶段以同次CI安全annotation终态为准。本清单是完整源码路径盘点，不能把未实测对象标为失败。

| 对象 | 源码创建路径 | 当前边界及将来最小目标 | 风险 |
| --- | --- | --- | --- |
| SERVICE_LOG | Start 普通 append 打开首次产生 `.runtime/windows-services.log`；Stop保留 | 若实测owner mismatch，额外授权仅首次新建的固定日志，先验证owner、DACL/control保持才允许日志流；已有日志拒绝、不修复、不覆盖 | 私有诊断可能含服务内容；必须防重解析/竞争/共享句柄，不能对已存在日志重设owner或削弱ACL；需要明确既有失败日志如何由用户处理 |
| PROCESS_RECORD 初始 | Start `write_exclusive` 的固定 `.runtime/windows-processes.json` | 额外授权仅本次Start独占创建的新对象，仍校验runtime/root及固定路径 | PID/创建时间/命令是私有身份绑定数据；Owner改变不能削弱DACL/control或允许提前写入；既有记录仍拒绝 |
| PROCESS_RECORD 原子临时 inode | `save_execution_bindings` 独占 `.process-binding-UUID.json`，核对本次原记录字节后 `os.replace` | 必须与初始记录一起评估：新临时对象在写绑定/replace前验证owner，replace后保持owner合同；不对既有目标inode SetOwner | 如果只修初始记录，replace仍会换成默认owner的新inode；必须防目标内容竞态、临时泄漏及放宽generic任意path；用户授权须明确本次自有记录的原子替换，不代表修复其他既有文件 |
| FILES | 便携文件后端仅在已支持的平台且显式 `create=True` 时新建固定 `.runtime/files` 目录；Windows当前failclosed，LOCAL app env删除file_root，Windows生命周期不创建 | 只有原生固定FILES对象实测或未来独立文件阶段确有需要时，另行授权首次新建目录；不含任意文件/子目录递归权限修复 | 目录CREATE_NEW/重解析/句柄与继承规则和普通文件不同；不能从配置/Session helper绕开固定路径，不能自动开启文件生产分派或递归修改ACL |

ROOT已有首次新建保护逻辑保持原授权与原代码，不请求修改既有ROOT。SESSION/CONFIG当前授权保持固定首次创建，失败后既有空文件也不能自动修复。任意其它诊断临时文件、fixture目录、业务文件均不因本清单被赋予新的owner事务。

若最终确认SERVICE_LOG为Restart根因，集中决策最小完整生产新建对象集合是：固定SERVICE_LOG、PROCESS_RECORD初始及其受限原子临时对象；FILES仅作为独立未启用候选列出，不默认执行。需明确用户同意的精确对象及新建/替换边界后才实现权限相关修复。本轮不夜间询问、不执行这些额外事务。
