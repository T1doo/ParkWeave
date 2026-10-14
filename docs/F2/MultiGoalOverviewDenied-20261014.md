# 多目标入口两次读取之间撤权窗口修复

父审对交付 `cf07e3d78e897e1921a5b51324107278d702c02b` HOLD，限定修复已有读取清理边界。冻结源码 `40be1d3770528cb5ef0dc299a7d8c606df1c529c`，510个src/tests/scripts文件。本轮不新增人工状态或业务功能，仍保留UNSUPPORTED/PARTIAL、Case未完成、原权限及原key恢复合同。

原完整HTML在离线NodeVM调用实际ASGI/owned PG，先读总览200，再于目标GET前撤销原owner READ。人工读取真实403被mgRead内部处理后，旧总览3目标与旧计划1步骤仍留页。单独red窗保留原页面chain、stderr、log、XML和exit，未覆盖旧证据。另red-fact窗证明事实GET403后旧资料辅助链继续请求case-cancellation并再次403。最初red-fixture窗是桥把页面虚拟身份令牌直接送API造成初始403，属于测试桥错误；改为映射原夹具真实令牌后另开red路径，三个失败窗均保留，不冒充同一产品失败。

人工目标跳转显式使用mgRead的propagateDenied，只有当前调用者403会传给原openGoalResult清理边界；不改变其它人工读取／恢复流程。mgCurrent及独立导航代次仍先于处理，迟到403不擦新身份、新Case、新总览或新草稿。总览、旧步骤和相关私有资料按原清理器清除，opaque原key句柄保留；没有自动重发或删除恢复记录。

loadCaseFacts的403可能是字段读权、EXECUTE、PREPARE或Case READ拒绝，不能一概视为Case无权。当前403先GET原资料入口核对其现有读取权限，不重试已拒绝的事实GET：资料403则按原prepError清相关私有视图，停止辅助链；资料200则仅按原事实区拒绝处理，有权总览／计划保留。其它读取失败传出并停止该链，不把失败当作权限成功。检查等待返回后的prepCurrent，迟到事实403不执行scope探测、不清新面板。

支持目标原入口审查：P1资料主GET、P2资源link/candidate、P3dispatch、P4dispatch/receipt及P5localcase直接传错至原目标边界；P1 readiness/corrections/material reuse/objections及取消／对账原当前403已清相关资料及总览。本轮补充实测P1主读取、readiness及facts的两次读取撤权；P2–P5当前撤权窗口仅源码审查，原一般功能回归保留，不宣称本轮全部403分支实测。

开发green窗11PASS，覆盖人工当前403、同Case刷新迟到403、实际新Case迟到403、真实专员身份切换迟到403，P1主读取/readiness/facts当前与迟到403，以及字段READ单独撤销而Case读取200。页面全部GET、0POST；测试桥撤权／恢复及新Case原API建单仅为明确setup，记录与页面操作分开。迟到窗核新view引用、草稿、存储和无继续HTTP；全窗比较原11业务表、9资源表当前夹具及Grant，权限setup变更另更新预期，不宣称已占用资源容量完整矩阵。字段拒绝窗继续原有取消读取且不触业务写。

冻结最终回归与独立验收数量、耗时及范围以随附validation及review原件为准，开发窗不相加。根计划重跑原17模块472项与补充11项；独审另行执行，不以根结果替代。原源码／报告diffcheck通过，失败证据pytest原尾空格保留，归档空白检查单独披露。

浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR及prepare Forbidden持续停止、没有换工具／URL重试。全仓、浏览器、prepare、Windows/native、部署／生产迁移和真实／付费模型NOT RUN；未变更Grant/registry机制、凭据、网络或安全配置。main、F1及原F2不写；正常开发分支交付待最终核对。

独立新增原页5窗：人工当前403、迟到身份切换、迟到实际新Case、事实全局撤权及事实字段拒绝；分别12/11/11/13/10断言、5/6/9/11/13 GET，均0POST。DENIED授权审计分别新增1/1/1/2/1条，真实拒绝审计正常保留，不宣称所有GET零数据库写。11业务表不变；Grant变化仅显式权限fixture和新Case setup，未由页面扩大权限。[独审原件](evidence/multi-goal-overview-denied-20261014/independent/review.json)。

冻结根18模块 **483PASS、0FAIL/ERROR/SKIP、2WARN、400.226秒、exit0**（原472+补充11）；独立 **5PASS、0FAIL/ERROR/SKIP、7.790秒、exit0**，执行范围见独审原件。根26页窗均在483中，不另加总。冻结510文件hash零漂移，原两approvalhash不变。模块及每窗HTTP计数见[validation](evidence/multi-goal-overview-denied-20261014/validation.json)，原件/脱敏哈希及字节见[export-index](evidence/multi-goal-overview-denied-20261014/export-index.json)。

最终[归档独审](evidence/multi-goal-overview-denied-20261014/archive-review.json) PASS：72项原件／导出SHA256与字节一致，两个产品红窗及桥错误原件完整保全，无未决源码或hash阻断。归档diff-check exit2仅原三个失败窗log/XML共14行pytest E尾空格；源码范围与报告exit0。归档审查原件在72项索引之外另附。
