# LOCAL_SYNTHETIC受控停表合同

实施前合同，基线a8fef37edee329b3ef51cb5f8026498fc668785b。原AT29要求UTC/业务时区、半开区间/缓冲、无来源不编SLA、非法暂停拒绝；原产品要求有权且留痕，没有要求新建独立签名信任根。原计划允许明确合成目录。真实授权未知只阻塞对应真实样例。

本片只提供显式测试fixture接口，不修改真实权限、准备记录、Case/Run状态或原规划/采纳/资源算法。已有READ、PREPARE、REVIEW_ASSIGNED本身不产生停表权。额外能力由测试宿主明确配置，复用原IsolatedDeadlineSources签发临时数据库证据，精确绑定同Store、同进程、同PG实例/OID、同事项和来源/日历/材料/请求版本；禁止普通启动加载、环境开关、已有真实库、IsolatedPlanApproval替代或新真实Grant。

1. 只允许已存在且仍受派的park_specialist，当前READ和REVIEW_ASSIGNED必须有效；宿主明确给该原reviewer有限fixture能力。owner可只读。能力有效期必须显式给出且在原来源有效期内，最多24小时，不从角色推断真实业务权。
2. 仅PAUSE/RESUME，固定理由AWAITING_SYNTHETIC_INPUT；有理由说明、当前fixture revision和原definition SHA。服务器在锁后取clock_timestamp，不接受客户端时间/claimed_legal。最多16对事件，不嵌套；完成目标、取消/调解Case、权限撤回、来源/材料绑定变化或能力过期均拒绝新写。
3. 原UTC工作窗遍历不变，先从半开工作窗减去受控半开暂停区间，再沿原函数算已用秒和截止。暂停不能追溯移走已完成的目标；开放暂停只冻结已用工作秒，截止UNKNOWN直到显式恢复，不猜恢复时间。补件/技术Run暂停仍不自动停表。原raw.pauses继续拒绝。
4. 独立SQLite fixture日志只由显式拥有证据的构造器新建，不复用/覆盖已有路径；保存绑定、原请求key/指纹、actor、动作、UTC、受控理由、连续revision、前事件hash与事件hash。SQL不可UPDATE/DELETE；每读验完整链。最多16事项、每项32事件、单次key不超过100字符。日志不存token/源原文/材料。
5. PG身份/父事项锁贯穿SQLite提交，SQLite锁后重查当前权限、绑定、时刻和有效期。GET只读，不补写/重发。重复key同指纹返回原事件，异指纹409；显式GET按原key恢复，缺失只表示NOT_OBSERVED，不证明迟到写不存在。不声称PG/SQLite分布式提交，PG业务无写入。
6. fixture服务不支持重启续权；新API进程没有能力，原日志保留为证据，PG实例重启旧能力拒绝。无自动rebind/迁移/恢复批准。原只读deadline接口在该事项启用独立停表接口时准确UNKNOWN，防止同时显示未扣停表的旧截止；受控时钟走明确synthetic-pause-clock子路径。普通UI不增加真实停表按钮。

验证仅选本片纯计算、新fixture实际HTTP/PG和原只读兼容节点；不跑B/C、历史风险动态窗口、真实模型或全仓。独审先冻源盲oracle再静审最终源码，不把静读计动态PASS。历史B/C仅复核原文件/日志，当前SHA未复跑；不宣称正式AT29/33、Windows或真实场景通过。
