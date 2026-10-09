# 同Case资源确认交付：实施前冻结

基线`92f08839ddde699cca61c276dd0b20a984fc8aa3`，已确认本地/远端一致、已知88403af祖先、无未提交文件/挂起Git操作；平台锁保留。原产品§5.4及F2-T03/T05/T07要求必需资源全成功或全不提交，并绑定当前Case、服务/资料/方案和明确确认。当前组确认与Case关联是两次独立提交，确认后关联失败会留下未关联实际占用；新切片补其首条资源交付的同事务闭合，不重做资料包、异议、替代或模板。

正式ServiceRelease与通用方案Approval不存在可启用主体合同，继续BLOCKED。最小选项为保留明确合成范围，或提供已有正式合同的主体/精确对象/职责分离/期限/撤回；后者也不自动授权本轮权限变更。现有资料专员REVIEW不推出发布/批准权。此次依据已有SYNTHETIC资料服务修订、受信P1–P5适配器及owner READ/EXECUTE/PREPARE和本人逐资源READ/HOLD，只做本人明确本地资源执行确认；`formal_approval=NOT_IMPLEMENTED`，`formal_release=false`。

范围：原同一Case，现有已采用注册计划含P2、全部原必需目标保留且P1当前VERIFIED；双槽当前LOCAL_CONFIRMED、现有原专员REVIEW/企业CONFIRM有效、服务目录已知工程合成来源/修订和当前计划定义匹配。仅首次Case资源关联（link revision0），选择3–8不同本人已有HELD占位；已有资源的多会话，不新增资源或Grant，不执行旧关联替代/释放。旧直confirm/bind/cancel路由语义保持。

新增只读POST预检、POST明确交付、GET原actor/key恢复。预检无业务写入，返回成员/当前服务来源版本及精确源指纹、资料/计划版本、至多120秒DB时点期限（不晚于任何占位期限）。明确交付绑定原Case/Run/request、服务ID/修订及目录sha、资料revision/审核hash、已采用计划稳定ID/定义hash及当时revision、P1源hash、全部hold UUID/修订/实际区间/数量/规则与当前授权、期限/理由。客户端不能上传发布/approved/verified标记；不能删原必需目标。当前写权限先于原键回放。

原principal锁→Case/资料/计划→actor/key→去重资源稳定序→hold/Case记录锁；等待后重验DB时点、当前资料/目录/计划/P1、占位期限/版本/窗口/峰值容量/授权及link0。同一PG事务生成组、全部HELD→CONFIRMED、不可变初始CONFIRM（scope仍为原bundle合同并增加delivery_binding）、Case claim、不可变Case link。新增私有事务内helper仅供可信服务器组合原confirm/bind逻辑，所有原入口仍独立auth/typed验证。关联/回执/来源校验失败必须连确认占用一起回滚；无部分组或未说明新占用，无额外schema/table/GRANT。

独立结果检查不是接受“已交付”字段：重新读取实际CONFIRM证明/manifest、实际成员状态/资源版本/容量、Case claim/精确link、当前服务/资料/计划定义/P1，核对delivery_binding双边关联与请求指纹。原独立P2 VERIFY继续核对实际本地源，不能由新增接口自动标VERIFIED。P2核验的运行revision增长不使稳定计划定义自动失效；定义/资料/来源/取消/后续关联变化时仅历史COMMITTED、当前NEEDS_RECHECK，原事件/占用保留，不自动重新确认/解绑/完成Case。无真实预约、机构受理、外部/线下履约或目标FULFILLED声明。

同key同原参数只读返回原回执/实际状态，不受旧预检期限自动重执行；不同Case/body/动作或旧pair/bundle/hold键冲突。恢复GET不执行、不需EXECUTE/HOLD但仍需当前READ/PREPARE归属及全部资源READ。NOT_OBSERVED不是未提交证明。篡改/缺失证明拒绝，应用不能UPDATE/DELETE组成员、回执、claim/link。原owner和协作锁、管理员源到COMMIT窗口的信任边界不改变。

页面从原资源区本人选择加入占位，显式指定Case与预检再明确交付；显示服务修订、资料/计划、时段数量及真实结果，不要求JSON。未知结果仅保存最多8条opaque actor/key/Case句柄，不存token/body/成员方案/正文；未知/损坏/NOT_OBSERVED锁住新的相关写入，冷刷新/重启只GET原键恢复。身份/Case/草稿/代次变化迟到结果不得回填当前私有视图；403清视图而保留原句柄。旧操作不会自动升级为此合同。

完成判据：真实API/PG3/8成员首次明确交付，同事务实际占用和同Case link；同Case原计划P2独立VERIFY；实际HTTP/Chromium预检/交付/读回/冷恢复与三宽度；服务/资料/计划/P1/占位换版、过期、撤权、越权/跨企业、并发/原键重复/不同参数、等待到期、关联/回执写故障均严格无部分写入；历史取消/来源变化/原键GET恢复、不可变与隐私负例；必要原资源/Case/计划/资料兼容。候选普通推送→独立只读审查→通过后普通dev推送，单源码写入者。正式42AT/EX、Win11、真实模型/业务未由工程测试签收；不改main/强推/部署/凭据/安全配置。
