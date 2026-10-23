# 原生schema初始化候选：仅离线控制流

在`69345dee47845c8173be0ccbff150ef3b611f046`上新增独立的[`initialize.py`](../../../../scripts/windows_portable/initialize.py)，未接双击入口、构建器、默认Store或原生命周期。原OWNER_MUTATION_PAUSED仍在所有重依赖/SQL读取/连接前拒绝，没有开关或伪造凭据。不是可运行Windows成品。

`offline-tests.log`为本轮最终11项stdlib测试原输出；正向显式mock暂停门、CREATE、原25迁移和授权。只证明候选的原SQL顺序、逐版检查、事务/失败控制流。原未发行凭据拒绝使用真实注册表逻辑；未发行成功凭据。SQL阶段异常回滚与COMMIT结果未知分开，后者不重试或声称仍在25。暂停检查预先导入lifecycle，不能称冷导入实测。

`validation.json`列出最终代码/日志hash及14件未改原生门、发行器、Store、入口/构建器/锁和SQL的逐字核对。`verify_scope.py`为原核验脚本副本，原输出路径指云端私有scratch；不是给用户运行的安装步骤。405原测试文件、367实现文件指纹匹配；9521仅历史collection，没有重跑全套或Windows。

首次离线运行9项通过、1项测试ERROR来自误用`BoundaryError.reason`；已改为原`parkweave_lifecycle_reason`。随后补COMMIT未知结果反例；本目录仅最终11项原件，不把中间次数累加。

真实私有PG进程/认证、角色秘密持久化、SESSION/CONFIG/owner创建门、roles/seed、native LOCAL批准存储、受维护Python运行时和真实Windows DLL加载仍未完成或未验。没有PG/Windows/浏览器/CI/用户电脑执行，也没有新权限、费用或协议接受。失败不删除或接管已有数据库。
