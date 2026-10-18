# 普通资料事项步骤办理与进程重启验证

基线 `7b98f454bee96947f2bc1c824a2b50c10939e77a`；先行普通合同 `b260c6f0`；最终受测提交 `954825efb66d16f7e41087e1c108b45042732703`，开发分支 `dev/f2-ordinary-case-step-20261018`。本片沿原V1§5.5及F2-T04，在原普通应用上办理已有合法资料事项的一个人工回执步骤；项目整体仍未完成。

## 原入口与普通业务接线

API和原worker均通过 `case_step_assignments.from_environment` 读取显式 `PARKWEAVE_CASE_STEP_MODE=CURRENT_PREPARATION`，普通缺省路径保留，未知值及Native read/write、独立demo、正式来源/批准provider混合拒绝。模式选择业务路由，不签发身份、Grant、permit、policy或批准。当前普通协议仍是原LOCAL/SYNTHETIC资料准备，不追加正式外部五证明。

原CaseStep事务抽为共用核心，原IsolatedCaseStepAssignments保留原构造/fixture证明/nonce/有效窗门。普通服务按每次操作的数据库原preparation绑定局部上下文，参与方不存入共享服务对象；现有owner/reviewer归属、当前READ/PREPARE/REVIEW_ASSIGNED/EXECUTE、执行者当前同域角色和READ、原Case/成功case.create Run/VERIFIED operation及目录/资料/fence均重新核验。原分派、回执、Store、权限、SQL/迁移和全部Native模块保持原字节。未增加权限框架或业务算法副本。

普通首次OFFER记录独立业务合同、精确UUID/来源/hash/身份Grant代际及最多300秒截止，普通API和worker从原事件独立读取。没有全新空库门、fixture nonce、启动时重新计算的寿命或tainted_runs缓存作为普通授权。现存active/inactive run_assignment、Native列历史、legacy/隔离/未知或损坏marker继续拒绝；不承诺识别受信管理员绕合同删除的历史。原legacy guard保留，不捕获拒绝fallback。

执行者仅本人当前步骤；撤权、期限、材料/目录/身份代际改变或终止使后续读写拒绝。owner/reviewer按当前READ/PREPARE或READ/REVIEW_ASSIGNED读取最小历史、OPEN/MARK_READ，不继承隔离1小时寿命；owner业务写仍需EXECUTE及完整当前绑定。负责专员WITHDRAW按当前权限终止，不依赖目标仍有权或offer未过期。每Case仅一个OFFER，无自动续授/重派/ACCEPT/回执/ACK。原业务门使用observe=False，本片不宣称P3–P5或完整Case目标通过。

原通知outbox/inbox表、幂等消费及OPEN/MARK_READ复用，SQL在LIMIT前按合同隔离队列；普通consumer不能接管旧隔离/legacy/未知原件。完整证明后才按当前recipient权限送达或抑制，最后锁等待后再核权限/原件/截止。原期限写入后重启不变，重复消费与已读保留首次时间戳，False仍仅代表一次有界扫描未进展。

原HTML从“我的资料准备事项”实际列表按钮、原资料行、内部分派入口发起OFFER；新API/worker进程后执行者从原通知卡OPEN、明确已读、本人ACCEPT，从回执列表SUBMIT；企业从本人回执列表独立ACK。第三个API进程只GET读回原UUID、ACK和已读/截止。普通DECLINE沿原严格终态事件/offer/actor/revision证明清除旧视图，不再自动GET已终止步骤。页面对普通受限步骤显示原截止和未授予Run访问权。

## 实际验证及失败保留

冻结954根48项全部PASS：新增普通两完整模块39项、原共用事务/隔离/通知/页面定向9项；collection、setup/call/teardown及JUnit逐节点完全一致，0FAIL/ERROR/SKIP。pytest194.574秒、外层198.885秒。798项选定Git输入的共享树与镜像前后均零漂移，112个根进程模块来源逐文件匹配冻结镜像。

独审首窗9项为8PASS/1自有probe时间设计FAIL（pytest82.285秒、main84.754秒、外层86.003秒）：自设3秒原截止已在消费和冷API启动期间耗尽，在inbox[0]空列表失败，尚未进入锁等待，未证明产品故障。原probe、stdout/stderr/JUnit及实际原截止全部保留。仅将该私有测试的首次原截止改为15秒，先在冷API实际OPEN，等到同一原截止前约1.1秒才发起实际PG锁等待；只补该1个selector，21.982秒PASS（main23.515秒、外层24.634秒），验证403、已读回滚、原截止不变，产品源码不改。

独审两窗有效PASS并集为9项：6自有probe、3根重叠，不称单窗9PASS。根侧按实际节点核交集3，**本片54唯一项通过**；[跨窗结算](evidence/ordinary-case-step-20261018/runtime/cross-window-verification.json)保留两窗失败/补验及两版probe SHA。两独审窗各798项共享/镜像前后及与根图一致；模块来源分别110=109冻结+1probe、108=107冻结+1probe，全部逐文件匹配，独审私有输入跨窗仅probe文件变化。先行18条oracle SHA `04c02fef368ede67e907d33debc99bf37099e2d5eef8026de1254f12c3231d39`，它是规格数，不是另18项测试。

[独审当前v2报告](evidence/ordinary-case-step-20261018/independent/independent-final-review-v2.json) SHA `391751c4c8fec70f270c32d3dce1467efa58201e2227d3e3bca5f94ccd80b28f`，本有限普通合法SYNTHETIC准入范围无开放P1/P2；报告与123项规范公开清单/脱敏映射经根逐项哈希核对。原v1报告SHA `4a4724069d9b39e1e3987061aa3dd0ab0aa2d29f342efa6e329b1658c8bf3cb1`及全部旧metadata不覆写；v2仅修正脱敏XML序列化，测试及结算不变。

真实普通子进程与原HTML证据包含三次API及三次worker串行重建的完整办理链，另一个API验证普通DECLINE终态；两个短截止/旧隔离负例另启动两个原worker。实际4个唯一API PID均与health匹配，经原stop_children对本次拥有child发SIGTERM后退出-15；5个worker退出0。pytest *_current别名产生的重复原件路径照存，按实际PID及非别名路径去重。API子进程的import来源未额外插桩；以固定镜像cwd/PYTHONPATH及实际独立普通factory/health PID核对，不把根模块来源记录转签给子进程。

开发窗口1项/6.600秒、36项/84.070秒、2项/22.460秒均PASS；未冻结且未插桩全部来源，分窗保留，不累计最终唯一数。开发中独审静读确认普通DECLINE会成功后再GET403的P2，先修原精确终态分支再作实际完整页验证；修补前没有实际运行的失败，不伪称红绿测试。工具连接曾在合同编辑时中断，只读确认未落盘后有限一次重做；只读不存在路径的检查exit2保留于工具历史。根进程metadata核对器曾错误要求SIGTERM退出为0，检查实际-15后按原生命周期记录并退出0；不计业务测试失败。

53份原文件保护比对与基线相同，含Store/权限/roles、原分派/回执/资料准备、全部Native/普通runtime、迁移SQL、原来源算法、conftest及固定AT。继承34,696份F2证据的Git差异为零；本片没有重新宣称完整逐件SHA扫描。上片69及更早129不整批重跑或转计，本片只选相关旧项回归。

公开证据240对raw/public，236对原字节相同、4对脱敏共7次合成会话替换；全部配对SHA、JSON/JSONL/XML结构校验通过。另有manifest、archive-validation、confidentiality-validation三份控制文件，共243份证据；其中123份独审规范公开文件按v2映射逐字节复制，不再次脱敏。100个已捕获合成会话全值及16字符前缀扫描0命中，截断值依独审精确映射去除。私有会话清单、PG数据/config、镜像及开发源码前像不发布，原件保留。见[归档清单](evidence/ordinary-case-step-20261018/manifest.json)、[校验](evidence/ordinary-case-step-20261018/archive-validation.json)和[保密扫描](evidence/ordinary-case-step-20261018/confidentiality-validation.json)。

归档首轮错误地按路径名拒绝26份已规范保留的子进程日志/proof，尚未创建公开目录；修正精确文件分类后，第二轮发现独审v1脱敏JUnit把尖括号占位符作为未转义XML文本插入，解析失败。原私有JUnit有效；第二轮228份部分输出、两次脚本/stdout/stderr和坏shadow均保留，不提交部分输出。独审从raw仅在ET的text/tail/attr替换已捕获会话值并序列化，验证原9节点、8PASS/1FAIL、suite/testcase属性及脱敏树一致；新XML SHA `46c42eb3cb3ee1166e646e24f05f5498d89e2af2f88cfdde92b27b1261229be3`。坏shadow以[v1-packaging-failure文本](evidence/ordinary-case-step-20261018/independent/v1-packaging-failure/invalid-results-xml.shadow.txt)保留完整字节并明确不是JUnit。第三轮完整归档通过，无业务重测或源码修改。

推送前128个实际远端分支头与基线逐项相同，main仍为 `31e7acb7e53bb1ab6465b9daae59de28757f7583`，本开发分支尚不存在。最终交付提交只新增本报告与243份证据；最终HEAD/祖先、远端差异、0/0、干净状态及798项源输入复核写入本地 `.runtime/ordinary-case-step-20261018/delivery-and-remote-verification.json`，不改写已冻结原件。

## 仍需实际提供的输入与未验范围

普通启动须已有受限DSN及schema32/33/原业务SQL权限、当前合法会话、同域企业/原获派专员/执行者及当前原Grant、精确版本SYNTHETIC preparation_catalog、原Case/Run/资料确认与独立人工核对。API和worker都须明确选择相同普通模式；缺输入准确拒绝，无后台seed、修权或目录发布。既有资料可读不表示执行者获得整个Run或企业材料访问。

项目已有CLI企业seed、资料fixture helper及material_only_demo的两角色演示setup；它们并非普通生产的合法管理初始化。本片未执行真实身份/Grant/目录初始化，也未把演示setup增加为另一套普通包装。实际首次管理流程仍需既有管理主体、受控目标及明确授权清单，属于项目后续实现/交付缺口。

Linux普通writer客户端、已有安装启动profile和精确native存储安装器代码已有；实际受保护安装、policy/key、独立安装/启动批准、不同UID/role及sealed FD环境仍另需原真实条件。普通CaseStep人工业务不发行这些对象，本片未安装或重试root/seal拒绝。正式来源的来源专用读取/独立验真、主体映射/current-head/撤销与ADOPT/批准语义仍未完成。

完整HTML仅Node VM配实际loopback HTTP/自有PG，非真实浏览器/视觉验收。Windows、正式AT/AT35、真实来源/园区/身份/履约、模型、外部通知和生产部署均NOT_RUN。无main修改、强推、费用/凭据/安全网络权限新增、roles扩张或未知锁/进程清理。
