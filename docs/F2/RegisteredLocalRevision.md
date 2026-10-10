# 原注册步骤的显式局部修订

沿原§8、F3-T03/AT25，从已推开发基线 `ee646825b2bb9a00418b7a708e6b638187f61da2` 继续。先行[有界写入与存储合同](RegisteredLocalRevisionContract.md)提交 `da1a89ee21c89a0fbf0ae8f3b9c749c1eb409f7e`，先冻结字面应变/保留集合，再实现。精确运行源码 `d12afaa6258dd89a539e3a859b965ca9441e2111` 普通候选推送后获独立 LIMITED_PASS；之后只整理证据/文档，343路径源码与清单保持相同。原资料包导出及资料交付异议已完成，不重做；旧Windows a823a28未推修复未迁移，也不作为阻塞或Windows验收依据。

原P1–P5计划现在保存版本化注册依赖、实际前置边与资源/既有Run访问集合的有界指纹。资源集合变化只影响P2及实际下游，既有Run访问集合变化只影响P3及实际下游；回执和材料仍按原来源处理。未知声明、旧清单、257行溢出或版本差异扩大到本Case全部步骤重验。企业必须在原页明确采用局部修订，再到原入口逐项VERIFY。未受影响步骤和人工锁保留，受影响锁先由原主体明确UNLOCK；采用与解锁均不自动核验。计划、稳定步骤ID、原步骤正文、原产物及不可变事件历史保持。

采用仍使用原READ/PREPARE/EXECUTE及owner范围、Case/资料revision/诉求版本/目标/预览hash/计划revision CAS、原幂等键与64事件/8旧计划上限，并预留活动锁解锁空间。每次局部ADOPT记载前一清单、当前清单、原请求、完整影响分区与请求指纹；读/恢复/目标核对拒绝结构损坏和语义分区伪造。历史声明按其保存合同验证，当前声明换版只使本Case待明确重绑，不将合法历史降为不可读。旧VERIFY内容缺证据仍按原合同显示UNVERIFIED，不扩成新权限或隐式成功。

丢响应只保留原11字段不透明句柄（640字节、8条、24h）；热/冷/新页和实际自有PG/API重启后只GET查原事件，不自动POST。撤权先重新校验并清私有视图；跨企业/角色、迟到响应、新Case或身份切换不能复活原私有投影。页面影响列表包含尚未VERIFY的受影响步骤：真实初次257行未知→当前已知的320像素原页显示“4个受影响、0个保留”，避免保留集误导。

## 精确源码的实际验证

| 独立运行窗口 | PASS | FAIL / ERROR / SKIP | JUnit秒 / 受控秒 |
| --- | ---: | --- | --- |
| 根：两个完整功能模块与CI diagnostics | 104 | 0 / 0 / 0 | 188.688 / 190.320 |
| 独审：两个完整功能模块 | 45 | 0 / 0 / 0 | 185.447 / 187.093 |
| 独审：旧阻断复验及动作边界 | 5 | 0 / 0 / 0 | 20.014 / 21.598 |
| 独审：原目标/恢复/人工锁兼容选择器 | 24 | 0 / 0 / 0 | 17.953 / 19.464 |
| 独审：自写原页、字面影响分区/CAS、实际PG重启 | 4 | 0 / 0 / 0 | 27.357 / 28.499 |
| 独审：不同configured API PID默认禁止新Approval写 | 1 | 0 / 0 / 0 | 4.061 / 5.160 |

各窗均自然exit0，不相加成一次全量；最终一行投影修复未重跑原12/13/27完整相关模块。真实HTTP/PostgreSQL/Chromium覆盖资源新增/移除/未选规则/容量、既有访问集合变化、回执换代、实际本地产物重验、未受影响锁保留/受影响锁拒绝、两键CAS与同键重放/异body拒绝、撤权/越权/跨企业、迟到响应、丢响应冷热只读恢复、损坏证明与隐私负例。独审真实独占PG停启记录不同postmaster/API PID，保持数据库身份/数据和原恢复句柄，旧键COMMITTED且无读路径业务写；不是重签fixture能力。新PID默认关闭探针仅验证schema-valid APPROVE返回403、无安装/业务写，未重验未消费Approval账本或完整生命周期。

冻结清单SHA-256 `1c8d0bb193e82ed236b4185e40ac7f9cba6185fb4166a3ddfa874cccc280ce46`；1499个CI函数ID与实际源AST对应。独审报告SHA-256 `449785c57cf290763d17c0e9cb91b449285efe58909743952ec5ee12b8f17bda`。见[机器核验](evidence/registered-local-revision/verification.json)、[独审原报告](evidence/registered-local-revision/independent-review/report.json)、[公开文件hash](evidence/registered-local-revision/artifact-hashes.json)及[真实原页320截图](evidence/registered-local-revision/independent-review/browser/independent-boundaries4/test_independent_boundaries/fresh-all-case-320.png)。独审证据封存时公开63份安全文件、62个hash锚；未公开其他截图和任何失败原始日志，原报告路径与公开映射均保留。

## 失败史与限制

- `ecf5d793311bd9d14853be2320c45f1c48fced69`：根895PASS/4FAIL，旧串链在明确RunAccess APPROVE后须显式局部ADOPT；独审3真实FAIL发现事件revision损坏读放行、合法UUID影响分区交换放行、初次溢出未知→已知漏全Case重验。已修，但该轮仍BLOCKED。
- `3cda6019fec72c842e039cd739bf84ab75b04079`：根907PASS；独审实际技术VERSION变化1FAIL，合法历史GET/恢复409。改为保存声明验历史、当前声明验新写；该轮BLOCKED保留。
- `5bc5a2b5be52f0ab7f99bd8319f055508695bc2e`：根440PASS、独审相关381PASS；独审原初次溢出场景仍1产品FAIL，尚未VERIFY的P1被投影错误归入保留集。最终d12修复该投影并用真实257行及原页面复验。旧通过数不抵消失败，也不覆盖d12。

开发期所有失败XML/log、首个未启动pytest的launcher拒绝及三轮BLOCKED报告在忽略的0700 `.runtime/registered-local-revision` 与对应独审目录保全，不覆盖、不公开可能含合成令牌的原始失败诊断。未来VERSION探针中普通owner GET可以按原规划观察合同保存失效标志；并非所有普通GET均零SQL更新，但不可变历史/步骤正文/业务产物保持。恢复/冷GET无业务重放另有真实快照证据。

LIMITED_PASS仅签收原合成注册适配器切片；一般动态图/完整依赖类型、全仓/fullAT25、正式Release/真实履约/Case完成、Windows仍NOT_RUN或未签收。没有新角色/Grant/Schema/政策审批、自动资源释放/停表、模型调用、真实业务或外部通知；没有main改动、强推、部署、凭据/安全网络配置修改。原冻结[覆盖映射](PR0-CoverageAt-a1e6022.md)不改。正常整合及实际远端引用见[整合记录](RegisteredLocalRevisionIntegration.md)。
