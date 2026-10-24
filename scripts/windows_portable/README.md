# Windows x64自包含封装候选

目标是用户双击即可用，用户不安装Python、PostgreSQL、SDK或编译器，不输入开发DSN。本目录是云端构建代码，**当前不是可办理的成品或已验Windows安装器**。

`credential_envelope.py`和`windows_user_protection.py`新增独立的纯字节封装/FakeAPI合同候选，未接目录、controller、构建器或入口。前者不加密或落盘；后者无DLL/native调用，原生入口继续拒绝。新数据库凭据持久设计及严格格式、CONFIG非自引用、SESSION三身份、漫游与同用户边界见[安全配置](../../docs/F1/SecurityConfiguration.md)。本片没有真实保护、凭据文件、ACL、PG或Windows验收；存储能力、CONFIG发布、UNKNOWN持久化与initdb非明文输入仍待后片。定向隔离命令：`python -B -m unittest scripts.windows_portable.test_credential_envelope scripts.windows_portable.test_windows_user_protection -v`。

`fixed_secret_store.py`接续三个固定对象的存储算法，仍只接受显式内存Fake capability与Fake保护器，不接controller或原生路径。复用原FixedDirectoryLease entry门直至关闭，拒重入/竞争；先核DATABASE、SESSION再独占写CONFIG，短写/同步/读回/关闭不明时UNKNOWN/poison且不覆盖重试。精确对象名、保护观测及不能证明原生持久性的边界见上述安全配置。定向命令：`python -B -m unittest scripts.windows_portable.test_fixed_secret_store -v`。测试没有实际凭据文件或Windows/PG运行，不把替身通过称安全存储完成。

`build.py`只读取已下载的锁定资产，不联网、不运行安装器、pip、PE或数据库。它核对源码commit、构建器/校验器/资产锁blob、每件资产及原许可证hash，将内嵌Python、Windows wheel依赖、PG最小进程载荷和原页面/SQL封装进候选。三个启动文件来自同一冻结commit。PG选initdb、postgres、pg_ctl、默认plpgsql/文本搜索/编码转换动态模块及其私有静态依赖，排除pgAdmin、StackBuilder和开发工具；不承诺可选扩展或任意动态模块能力。

云端离线命令（需已有Git/Python，**不是给端用户准备开发环境**）：

```bash
python -B -m unittest scripts.windows_portable.test_payload -v
python -B -m scripts.windows_portable.build --source <完整冻结commit> \
  --assets <已准备资产目录> --lock scripts/windows_portable/runtime-assets.json \
  --output <不存在的新候选ZIP>
```

资产目录须保留锁中相对文件名；命令不下载缺项或接受协议。`runtime-assets.json`记录实际官方Python/EDB/PyPI来源、精确版本/大小/SHA256、26件原许可文件hash及22个Windows运行依赖的28条已核依赖边。原许可证随对应资产进入载荷；这些原文和hash不等于再分发义务、安全或原生运行已签收。pytest、Playwright、SDK和编译器不是运行载荷。

双击`ParkWeave.cmd`仅绝对调用包内解释器，`-I -B`与固定`_pth`隔离用户site/系统Python。入口核完整清单后加载原`lifecycle.py`，只读取原`setup_readiness()`，不调用setup/main/doctor，不创建数据库/角色/会话、不改ACL。当前退出2并显示`OWNER_MUTATION_PAUSED`；即使未来原门READY，也继续拒绝未实现的私有实例bootstrap。`usable_product`始终false，不能称安装成功。

完整性清单检测意外漂移、缺项和多余文件；它不是发布者签名，分发仍须可信来源的外部ZIP摘要。Windows路径检查拒绝越界、ADS、设备名、尾点空格、大小写别名及链接/reparse对象。PE核验仅做AMD64与普通/延迟导入名检查；只匹配模块目录/本进程私有exe目录。API-set名称不证明OS提供，符号/转发导出及真实加载均未验。

已核真实资产仍有明确未完成项：官方Python3.12.10嵌入包已被3.12.15取代，仅供静态检查，不能当安全可发布运行时；PG缺私有Microsoft C++运行库，不从PATH/CWD补缺或执行系统安装。原生SESSION/CONFIG安全创建、角色与seed初始化及真实端用户首次运行/退出重开仍需实现和独立验收。不会把Linux证明、假PE fixture或源码help转签为Windows成品。

`initialize.py`是另一个**默认暂停的schema候选**，未接入双击入口或载荷构建器：先调用原`require_setup_readiness()`，当前在依赖导入、文件读取和连接之前拒绝`OWNER_MUTATION_PAUSED`，没有override。将来原门另经审查允许后，只能由原发行器真实CREATE、取得同进程原始`NativeDatabaseCreationEvidence`，沿原Store到25，再使用原锁/原精确类验真和冻结原SQL，在单个事务扩展026–032并逐版核对。默认Store原生跳过分支和七份SQL未改；这是新增原生消费者候选，**不是原Windows已支持迁移**。失败回滚仅覆盖026–032；真实CREATE和已提交25保留，不DROP、不重试、不读取时补签旧库。函数不负责私有PG启动/认证、受限角色及秘密持久化、SESSION/CONFIG或ACL，返回Store也不表示安装完成。

SQL阶段异常请求回滚026–032；COMMIT或回滚连接失败时结果可能UNKNOWN，必须保留原异常和数据，不重试或断言仍在25。该候选单独运行`PYTHONPATH=src python -B -m unittest scripts.windows_portable.test_initialize -v`。正向控制流测试显式mock原暂停门、CREATE、25迁移和授权；只验证顺序、单事务、失败保全及提交结果未知。暂停测试预先导入lifecycle，不是冷导入实测。真实未发行凭据由原注册表拒绝。离线通过不签收原生迁移、首次运行或重开。

`controller.py`接续新建/重开流程：新建沿真实schema候选→原roles.sql→原安全路径独占SESSION适配器→原Store.seed→独占CONFIG→文件/物理库只读验真；随后才启动应用。初始化READY与进程STOPPED_CONFIRMED分别记录，只有两者成立才能同目录重开。重开仅加载已有秘密、原文件/owner/ACL/物理库绑定与schema32，不CREATE、迁移、补seed、补会话或重发原生凭据。部分初始化、COMMIT结果未知、启动/清理未确认均拒绝自动重开。目录记录只防重试，不授予DDL权限。原安全门仍暂停，Windows目录持久化、进程启动/就绪接线及秘密/SESSION-CONFIG端口尚未完成，也未接入包或双击入口。离线fake验证命令为`PYTHONPATH=src python -B -m unittest scripts.windows_portable.test_controller -v`；不代表真实PG/Windows首建或恢复成功。SQL叠加rollback/close及随后进程/lease清理错误私有保留完整异常链，公开报告只给有界阶段/类型，不输出秘密。

`directories.py`提供真实Linux `openat/O_NOFOLLOW/flock/fsync`租约实现，显式私有base下仅接一个新子目录，不修改已有权限。永久锁文件与有界原子journal分离，持目录fd逐次复核祖先/根/锁物理身份和journal快照；目录记录不含秘密。READY_STOPPED仍持锁，release写入并同步RELEASE_PENDING后单向冻结，只关闭本次原句柄，不显式解锁后写文件、不重试未知fd、不删除锁或猜PID。下一获取须真实内核排他成功，再核身份/合法旧交接，并在返回前落盘新代OWNED。崩溃遗留OWNED、UNKNOWN或部分初始化不得补办。Linux观察限本次文件系统及合作进程，不宣称内核可防同UID恶意改名、管理员或断电恢复。

`windows_directory_handles.py`已有原WinAPI祖先/根句柄、share-none锁、相对NtCreateFile/WriteFile/FlushFileBuffers/FileRenameInfo具体代码；owner/control/raw DACL只读比较，不改ACL、不请求WRITE_OWNER/WRITE_DAC，不称整个SD全字段验真。原生新建仍首先拒绝OWNER_MUTATION_PAUSED。尚无已接受的目录元数据持久化屏障，真实Windows在根open/写入前拒绝WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED，不从文件flush推定目录rename耐久，也不请求管理员卷flush或降级路径锁。相关依据：[NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)、[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)、[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)。运行`PYTHONPATH=src python -B -m unittest scripts.windows_portable.test_directories -v`：最终21项中16项Linux真实文件/进程（含其他端口fake的控制器接线），5项Windows ABI/替身；不能签Windows互斥/崩溃恢复或成品可用。

`processes.py`新增未激活的自有进程句柄核心：固定私有相对exe/大小/SHA256/参数目录，launch只接受冻结名称；可执行文件句柄及根/子目录身份在启动前再验。对外仅无资源属性、不可序列化的opaque token，真实句柄/状态留在本实例私有登记；注册回调不能在创建中重入stop。创建即登记、一个启动时限/停止时限，仅精确本次token可停止；未知退出保留最后观察句柄、记录真实lease UNKNOWN并阻止新adapter重开，不按PID猜目标、不自动重试或删除锁。公开诊断只给有界阶段/异常类型，不输出环境/命令/秘密。

Linux参考后端明确只允已有`/usr/bin/sleep`、`true`原字节的私有副本，sleep至多5秒，无shell/PG/任意进程树；预检单内核线程/默认SIGCHLD、真实fork后EOF可取消的执行门、返回子进程pidfd与birth绑定、注册后才fd-exec，CLOEXEC错误管道记录已收到的exec错误；空EOF仅表示未报错，另核原目标映像，快速退出不补签exec成功，业务就绪仍NOT_CHECKED。WNOWAIT后精确reap。TERM/KILL均使用同一个pidfd；pin失败只关闭GO门并等本次尚未reap子进程，不按数字PID发信号。这是目标环境的真实无业务子进程检查，不是Linux沙箱、同UID攻击防护或PG验收。

`windows_process_handles.py`提供原生Job候选：CreateJob立刻登记后配置KILL_ON_CLOSE；CreateProcessW暂停创建，返回process/thread句柄先保存，再核出生时间/映像、精确AssignJob/成员身份后resume。Job未绑定时须先用原创建句柄终止并确认该子进程，再核Job空；空Job不能代签未入Job子进程退出。stdio/配置/关闭双故障保留主因及UNKNOWN。Windows API真实执行仍为零，现有目录门仍拒绝；DLL闭包、秘密、SESSION/CONFIG、PG/应用就绪和控制器高层接线均未完成，未加入载荷/双击入口，也未改变原OWNER暂停门。定向检查命令：`PYTHONPATH=src python -B -m unittest scripts.windows_portable.test_processes -v`，精确实测与替身范围见对应原始日志，不能签原生安装或成品。

[`fixed-journal-design.md`](fixed-journal-design.md)现对应`fixed_journal.py`的固定8192字节双槽codec/storage和`fixed_directories.py`的显式新格式lease：真实Linux pread/pwrite只用0/4096偏移，文件inode不替换，文件fsync后两槽完整读回；严格原状态/代际、canonical JSON、hash链、根/锁/journal ID。任一坏槽拒绝，不回退旧PENDING；读取/绑定/写入失败均poison且不重试。取得内核排他后先提交新代OWNED，才返回lease；缺初始名字不补建、不自动fresh或迁移旧v1，默认v1实现不变。`fixed_windows_journal.py`现有独立前置路径：实际Win x64、现有本地NTFS drive句柄、既有SD和固定文件API必要事实，与后续file flush、首次名称缺失拒绝分开；不再通过旧rename acquire。事实核完仍由不可通过env/布尔开启的`WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED`拒绝实例root获取。旧v1的`WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED`不变，不rename、不请求卷flush/管理员权限；Linux/替身不能解除新旧门。命令：`PYTHONPATH=src python -B -m unittest scripts.windows_portable.test_fixed_journal -v`。

`application_readiness.py`新增默认未激活的生产就绪消费者。控制器要求两个精确API/worker token、原有受保护Bearer及预期主体、同次challenge/当前DB app-role与schema、前后真实进程身份；独立物理库/目录绑定在探针后再次核对，不能由同名DB/OID代替。API新增只读`GET /api/runtime/readiness`，沿原active Bearer身份且拒绝不走audit写入；worker显式`--readiness-stdio --readiness-challenge`在第一claim前用私有pipe报告WAITING_GO，原业务循环仅GO后进入。RUNNING落盘失败不发GO，未知GO不重发，失败沿原owned cleanup。不会生成新token/secret或授予业务能力。

`instance_processes.py`新增高层**应用对接线候选**，未接双击入口或构建器。一个调用实例只接一次NEW或REOPEN、同一个租约及集群端口返回的原`DatabaseInputs`对象；NEW再次经过原OWNER暂停门，REOPEN仅委托独立的既有集群端口，没有initdb/迁移/seed/session补办命令。集群固定进程编排现有下述独立候选，但完整生产路径仍缺安全输入与真实就绪实现，不以委托接口冒充私有PG已可启动。候选约定集群数据位于持有根下`data/postgresql`，应用文件位于`files`；不迁移旧路径、不创建这些目录。

应用仅使用固定包内Python的`-I -B`命令：回环uvicorn原`configured_app`工厂及带原stdio/challenge的worker。原`PrivateProcessAdapter`只额外接受冻结的三项显式LOCAL环境（app-role DSN、LOCAL、同根files），不继承其他项目/PG/provider环境；DSN不进入argv/repr/公开诊断。创建回调即时把原token转交控制器，部分失败仍由原token逆序清理，未知清理不向所属端口重发。返回`RegisteredApplication`不表示就绪；真实身份核验、RUNNING落盘及唯一GO仍全部在原控制器。定向替身检查和准确未验范围见[原件](../../docs/demo/evidence/private-application-processes-20261023/README.md)。这不是集群、安全文件、原生Windows或自包含成品的验收。

`cluster_processes.py`的`FixedClusterProcesses`接续固定包内initdb/postgres编排：NEW原门→必需受保护输入→initdb确切int退出0→同原token确认整个Job退出→检查新树→前台回环postgres→真实维护库/物理集群检查端口；REOPEN目录中只有postgres命令，缺文件/UNKNOWN交接不补初始化。四项`ClusterPrerequisites`仍无生产实现，必须覆盖密码文件与后续path-open保护、树/配置/旧进程退出、发凭据前的端点出生身份及真实维护库/物理集群。现有角色安全初始化亦未实现：原issuer在CREATE DATABASE前仍要求安全的parkweave_app已存在，roles.sql只GRANT，不创建该角色。源码候选没有SQL/角色/session操作，不进入原entry/build，不能据编排签成PG可运行。

集群候选共享30秒协作式启动截止，显式传给四项检查；initdb观察每片≤5秒，预留原创建/停止时间，真实检查返回迟到则拒绝。没有把未实现的检查回调或内核IO变成可强制取消的硬实时操作。原句柄/Job清理只证明进程退出，不承诺干净PG停机；正常WAL恢复仍需后续真实ready等待，不能拿它补schema/session。11项受控替身检查、两层控制器接线和原始错误/清理双故障证据见[本片原件](../../docs/demo/evidence/private-cluster-processes-20261023/README.md)。未启动PG/集群/Windows进程，未生成或配置凭据，没有新CI。

`runtime_payload.py`提供下一个独立静态前置组件，尚未接入cluster provider或entry。外部冻结的manifest摘要/source SHA与当前精确fixed lease/snapshot绑定后，仅读manifest列出的完整PG载荷子树（包括bin/lib/share与许可文件），通过原相对根句柄pin核所有文件hash/身份，并两次held-fd枚举拒绝额外对象、别名、链接和不匹配文件集；不会读取根下data/files/secrets。复用原manifest/PE导入解析与builder的有限bootstrap模块口径，PG-only快照不证明Python、OS API-set、符号/转发、动态加载或initdb内部bootstrap/standalone/管道执行闭包，外部摘要也不是发布者认证。

只读`PinnedPayloadFile`复用原私有根/祖先/文件验证，允许数据文件0600/空内容；其spec不是Command，原进程目录仍只接受精确Command并使用默认可执行映像检查。末级POSIX读取加O_NONBLOCK，先拒FIFO等非普通对象，不等writer；普通文件仍核原权限/身份/hash。Windows缺已接受的held-directory枚举时拒绝，不退回路径遍历；即使Linux静态快照通过，require_for_cluster仍拒绝NATIVE_RUNTIME_LOADING_NOT_ACCEPTED，不能激活。实测范围和关闭双故障原件见[本片证据](../../docs/demo/evidence/runtime-payload-prerequisite-20261023/README.md)。同UID并发双扫不是原子快照或加载期sandbox，不据此放行实际运行时。

Windows worker profile仅继承三份精确stdio句柄，两个匿名pipe的原fd进入私有resource登记，确认进程退出后关闭；本轮仅真实Linux pipe fd加Win句柄替身，未实测Windows容量/继承/PeekNamedPipe。发送Bearer前必须核已连接socket反向四元组的ESTABLISHED唯一行与原API hProcess出生身份；`windows_endpoint.py`只读SYSTEM32 GetExtendedTcpTable，有界缓冲，不输出系统表，不查询/操作外来进程。缺native支持零HTTP调用，连接归属不符零应用字节。新门仍关闭，端点和进程API源码不是原生验收。

消费者共享5秒就绪准入/激活时钟，HTTP按同一余额接收且不代理/重定向。`polling_database.py`使用非阻塞libpq connect/send/flush/consume/result与显式只读启动配置；超时finish原连接，不同步cancel或COMMIT。`isolated_pipe.py`把同步pipe操作放进冻结命令的自有辅助进程，同一绝对截止内预留0.5秒核退出与清理，不留timeout线程；GO写后迟到/解析/OS失败均UNKNOWN且不重发。根进程不再PeekNamedPipe，确认全部helper及父端writer关闭后才读有界结果；任一关闭未知保留原cap与lease UNKNOWN。真实Linux helper及synthetic wire限测见[原始证据](../../docs/demo/evidence/transport-deadline-candidate-20261023/README.md)，不签所有内核/文件系统操作硬实时保证。worker自身10秒准入以及真实Windows管道/Job、DB/物理绑定、安全SESSION/CONFIG、高层启动、端用户运行仍未验或未闭合，双击入口继续拒绝。

本组件14项stdlib离线测试单独运行，PE为明确不可执行fixture；不并入原405文件/9521项历史collection，也不称全回归。真实资产静态检查另列，不累加为测试通过。无新浏览器、PG、Windows、CI或用户电脑运行。
