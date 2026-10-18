# 本 Case 受限步骤站内通知验证

基线 `06186eef397a26bcf8ed8b6b3f07d6b1e9aa5cc5`；产品源码/合同冻结 `928be187f4513d3821b7b96ec3baba0bb30a2089`；修正原离线执行器依赖后最终受测提交 `1da2e6c28024e3d7f518a2b8d62ce271c5ddb749`；开发分支 `dev/f2-case-step-notices-20261018`。两提交的产品src树完全相同，为 `969c30783c586a6d1230b06693c071eece4d775a`。本片接原V1§5.5的notice.create及F2-T04站内协同，复用已接受CaseStep片，不重跑或转计原129项。根是唯一受控文件与Git写入者，独审只写私有运行时原件。

## 原业务路径与实现

完整原HTML从实际“我的资料准备事项”按钮、资料行、此事项内部分派按钮进入OFFER；指定执行者点击“刷新我的站内通知”、通知卡片、“打开原事项”，读当前原步骤后再独立点击“确认已读”。原Case/资料由原API和worker在HTML前准备，不称零设置新安装或全程新诉求DOM。通知列表、详情、OPEN与MARK_READ调用实际loopback HTTP/ASGI/自有PG；没有用模拟fetch替代正向服务，也没有真实浏览器或视觉结论。打开不自动接单、记回执、核验或完成Case。

复用原事件、dispatch_notice_outbox、dispatch_notices、Navigation和原时间戳事务。API显式把同一个原精确CaseStep对象传给原通知方法；受信调度也须显式传该对象给原consume。没有新授权框架、角色、Grant、凭据、policy、endpoint或外部消息通道。普通CLI/worker不发现或构造依赖；configured_app保持关闭。

候选队列在SQL的LIMIT前按整dispatch历史的marker分lane，涵盖自身无marker的后续ACCEPT/DECLINE/WITHDRAW。默认consumer跳过并保留受限/未知marker意图；显式consumer不吞legacy或foreign issuer意图，FOR UPDATE后再次核lane和原件。分流SQL/marker只选候选，不授予权限。损坏/未知原件保持PENDING；只有完整核为本依赖原件后，当前recipient撤权、终止或到期才可SUPPRESSED。原cursor保留；consume False只表示本次有界扫描没有进展，不证明排空。调度须继续独立扫描，不能无界循环或用SUPPRESSED清理未知意图。

consumer只取原队列recipient的当前principal行，不读取或生成会话token。复用CaseStep同域/角色/父Case/Run、当前权限与原marker校验；来源证明核候选OFFER本身为rev1首事件、ACCEPT→CREATE及DECLINE/WITHDRAW完整前缀、状态、原指纹，fresh event/source坐标与actor/action一致。API仍认证原真实会话；最后锁等待后重核当前会话、原件、权限/代际与原数据库期限，失败回滚送达/已读修改。FOR UPDATE SKIP LOCKED或失败savepoint丢弃本候选待复核回调，避免未处理Case污染其它Case提交。没有物理COMMIT触发器或跨系统原子性主张。

executor只能读本人当前有效OFFER/ACCEPTED lineage；原首次截止、授权/资料/目录变代、终止及Native/legacy污染继续拒绝。旧送达行不缓存权限。owner/负责专员按当前本Case权限在原依赖整体有效窗内读最小历史；actionable仅当前live OFFER的本人执行者。OPEN只写打开请求，独立MARK_READ才记已读，重复操作保留首次时间戳。列表/详情不含原goal、材料、分派reason、会话或正文；分页绑定原provider contract_id/模式，每页重核权限。

普通Store/默认API不继承通知权，旧guard未删，原分派/回执模块原字节；不存在捕获Native拒绝后fallback。生产默认关闭，普通SYNTHETIC不被额外要求正式外部五证明。[合同](CaseStepNoticeContract-20261018.md)定义全部边界。

## 实际窗口

最终1da窗口根63项全部通过：28项本片、32项原通知模块、3项原离线页面定向回归；setup/call/teardown与JUnit各63一致，0FAIL/ERROR/SKIP。pytest225.384秒，外层228.938秒。独审最终9项全通过，含6项自有probe、3项完整原HTML重叠；pytest94.742秒、pytest.main101.665秒、外层105.028秒。按实际collection交集核去3项，最终69唯一项通过；旧129项未重跑/转计。[根跨窗核对](evidence/case-step-notices-20261018/runtime/cross-window-verification.json)独立计算合并结果，独审在根完成前签下的combined字段null原样保留，不替独审改签。

两最终窗口各792项Git选定输入的共享树、镜像前后及跨窗哈希全同，当前文件仍相同。根105个受测模块来源全匹配镜像；独审104个来源为103个冻结输入加1个独立probe，全匹配。独审计划在实现前冻结，oracle SHA `67a0c177ebebd603a50a0a8c800c77f20e4a9d3b149c6840f7536fcd8c1c2c81`，probe SHA `a1f947a10b5fb45d72336842fa62fe38f766856b80f8dc6f83d61c35d3dd6ec8`。[独审报告](evidence/case-step-notices-20261018/independent/independent-final-review.json) SHA `60034fcc57a8371f7da3bd344374b74e9b1d79b38f8092b87b5110ad8730ff28`；本有限自有合成范围无开放P1/P2。

首冻928根窗63项为62PASS/1callFAIL、0ERROR/SKIP，178.720秒；唯一失败是旧离线切片执行器current_denied缺少原页面entryFailureFlows/failEntryFlow定义。原061页面配不变旧执行器也实际复现同一ReferenceError。1da仅增加一行，提取原有定义，原断言与产品源码不变；直接Node复核退出0后，完整重验相同63项。旧根红窗、基线诊断、机械修补以及旧928独审9PASS均分别保留，不转计最终结果。跨窗证据核对器初次把独审空问题数组当成计数0，修正类型检查后退出0；初次脚本/stdout/stderr保留，不计业务测试失败。

完整HTML五流NORMAL/LATE_LIST/LATE_OPEN/LATE_MARK/LATE_403均从原列表按钮实际导航；LATE_403为真实SQL撤权后的实际服务403。LATE_MARK是合法已提交已读响应在界面切换后晚到，未冒称服务端撤权。独审另核SKIP LOCKED的Case A回调不污染Case B、伪OFFER rev2、SCAN_LIMIT=1前缀隔离、实际PG锁等待跨2秒首次截止及22条通知20+2真实分页。整个测试只使用自有合成PG、loopback HTTP及完整HTML的Node VM。

开发窗分别19PASS/80.69秒、7PASS/43.79秒、3PASS/17.18秒、2PASS/14.32秒，原stdout/stderr/JUnit保留。开发源码未冻结、导入来源未插桩，中间源码前像未完整保存，不声称开发窗零漂移，不计入最终冻结唯一数。设计/静审期间收紧了整dispatch队列分流、可读与可办分离、cursor绑定、完整原件后才能抑制、SKIP LOCKED回调清理、伪OFFER候选及LIMIT前分lane；修补前静态反例不伪称实际运行FAIL。只读rg不存在的test_notice通配路径exit2独列，不计业务失败。

31项保护检查与基线相同：Store、roles/permissions、全部Native/普通runtime/正式来源、原图算法、固定AT/绑定、conftest、原分派/回执/worker及旧CaseStep合同；普通configured_app函数原字节。34,533份继承F2证据Git受控差异为零，本片未重新声称逐件全SHA扫描。新增验证不覆盖原129、全仓、正式AT35或真实部署。

公开证据含160对原件/公开文件，160对字节相同，0对脱敏、0次替换；其中62份独审选定原件按其规范映射逐字节复制。另有manifest、archive-validation、confidentiality-validation三份归档控制文件，共163份证据。全部配对SHA与结构文件解析通过；180个已捕获合成会话值的全值及16字符前缀扫描0命中。私有会话清单、PG数据/config、运行镜像及非规范草稿不发布，原件保留。原HTML基线副本仍在私有目录；其Git对象与哈希、旧原执行器及前后诊断原件可复核。详见[归档清单](evidence/case-step-notices-20261018/manifest.json)、[归档验证](evidence/case-step-notices-20261018/archive-validation.json)、[公开保密扫描](evidence/case-step-notices-20261018/confidentiality-validation.json)。

推送前实际远端与起点127个分支头逐项一致，main仍为 `31e7acb7e53bb1ab6465b9daae59de28757f7583`，本开发分支尚不存在；原请求db108及本片061基线均为最终受测提交祖先。交付提交只新增本报告及证据；最终远端与源输入复核写入本地 `.runtime/case-step-notices-20261018/delivery-and-remote-verification.json`，不改写已冻结证据。

## 当前运行与真实交付缺口

当前可验入口依赖原fresh owned临时PG证明、同一个已发行CaseStep对象/Store及其最多1小时有效窗、原合法会话与READ/PREPARE/REVIEW_ASSIGNED/EXECUTE、当前目录/资料和固定最多300秒offer；API及受信consume必须各自显式绑定，不由数据库marker自行恢复授权。原业务初始化只在已允许的自有合成fixture中进行；本片未新增真实身份、Grant、目录或批准。

普通configured_app仍没有CaseStep的生产准入/安装接线，这是项目后续代码与合同工作，不能把本测试开关接入环境变量便称生产可用。已有合法普通SYNTHETIC输入的原资料准备路径继续复用，无须正式外部五证明；缺PREPARE/REVIEW_ASSIGNED/精确目录准确拒绝，不自动修权。

正式资料入口仍无来源专用成功分支；首个实际来源域/合同版本与获准结构样例、四对象关联/修订/指纹、原ADOPT/Run回执语义、源主体/权限映射及既有信任/current-head/撤销协议尚需明确，再由项目实现专用读取/独立核验。正式资源批准映射另列，不用IsolatedPlanApproval、Run READ或本通知已读代替批准/履约。

Linux普通writer客户端、已有安装启动profile和精确安装器代码已有，实际受保护安装/启动、原policy/key/批准/pin与已有受限身份仍未验证；本片未安装、发行、调用或重试root/seal拒绝。Windows原生传输/保护适配及实际Windows11正式场景仍有独立缺口。

未改main、未强推/部署、未增加费用/凭据/安全网络权限、未调用真实模型、未发送外部通知、未动未知锁或进程。Windows、浏览器/视觉、正式AT/AT35、真实业务/来源/履约均NOT_RUN；项目整体尚未完成。
