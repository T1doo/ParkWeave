# 原持久步骤未知操作冷恢复合同（实现前冻结）

基线32879934025bb2148156797f39b91d22075e895e，沿原产品§5.2/§5.5/§7.1和F2-T02/T04/T05/T07，补原ADOPT、BEGIN、REPORT_FAILURE、RETRY、VERIFY未知结果核对；这些仍是原注册适配器的协调/来源核验，不执行业务动作，不代表现实履约或Case完成。

0新业务写命令、0表/迁移/Grant。既有actor/key/fingerprint幂等、原版本CAS、原事件64与替换历史8保持。新增GET原key核对，在当前认证/READ、原owner PREPARE/EXECUTE、原专员REVIEW_ASSIGNED或原执行者合法Run指派/到期/当前本人offer和原动作角色范围内，先原parent及同key锁，再按已认证actor查原事件。不得借句柄获得权限或用NOT_OBSERVED推断失败。撤权或到期拒绝；原key其它Case或重复/损坏/不一致的事件证明拒绝。核对旧计划事件保留历史，不重绑定成当前有效核验。

恢复GET专用最小投影且严格无业务写，不调用普通计划GET的观察失效写入。原事件用既有fingerprint与ADOPT来源/前代计划或命令step/revision/source重建核对；只返回原事件ID、动作、plan/step/revision与本人actor不透明引用、旧/当前标志、当前计划最小状态及ID/依赖/历史引用。不输出理由、目标正文、资料/事实/回执正文、verified_sources、私有源快照或其它企业记录。取完所有可能等待的源锁后再采样数据库时钟，并在返回前复核当前身份/Run到期，历史已保存不变成当前可写或有效业务来源。原普通计划读写合同保留。

浏览器原提交前保存新有界不透明句柄：版本v、事项id、Case/Run UUID、原随机key、本人actor_ref（服务端从principal ID生成，与token无关）、action、原plan/step UUID或null、提交前计划revision、expires。最多8条，每事项/actor一个，640字节、最长24小时；严格字段/UUID/action/revision/期限白名单。同原句柄重试不得延长期限或改元数据，不保存reason、目标/材料/回执正文、token/凭据或凭据派生值；存储不可用/满时提交前拒绝。到期/损坏只清句柄，不称原提交失败；旧历史仍可经原合法入口人工核对。

热页未知按钮改为GET历史核对，不再POST原未知提交。刷新/重开/后退后重新认证，从原资料/分派/回执进入此Case再按本人actor_ref读句柄，只GET恢复；当前计划视图由同次GET只读返回，不自动调用普通GET观察写入。恢复COMMITTED须匹配原Case/Run、action、step、原plan/前代plan与expected revision；不匹配保留待核对。NOT_OBSERVED只表示查询时没看到，迟到原请求仍可能提交，原CAS/幂等继续保护显式新操作。用户明确结束核对后才清句柄并重新读取原计划，恢复过程中不自动ADOPT/BEGIN/VERIFY或重发正文。未知句柄保留期间原写/导航/目标结果门锁住，私有草稿不被只读核对覆盖；切换身份/Case或当前403强制清私有内存/DOM，句柄留给原合法身份。旧200/403/POST迟到不覆盖新上下文或清另一个原请求。

真实PostgreSQL/HTTP/Chromium验证ADOPT与四原命令保存后丢响应、保存前未观察与迟到CAS、冷刷新/新页重开、重新认证、来源/资料/请求换版和替换历史、撤READ/PREPARE/EXECUTE/REVIEW_ASSIGNED、执行者撤指派或到期/换offer、跨身份/企业/园区/Case、同key重复/不同body冲突、并发只读恢复与原在途写、最后等待后过期、存储不可用/8条/期限/损坏及隐私负例。GET业务快照不变、原事件次数不增，不用真实数据/模型/外部通知。故障原日志私有保全，普通候选push后精确SHA独审，通过才正常dev整合/普通push。main、部署、权限/凭据/安全网络不改；正式发布/真实履约/多用途分享/Windows/fullAT/fullrepo/a823仍另列待补。
