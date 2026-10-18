# 普通合成演示初始化与两次新办理：有限交付验证

源码/测试/README/合同/操作说明受测 SHA：`5b36291a22aae8dd74346ae9f2b54c148a4b1ef0`。基线 `6067cd3070ef3987d9013b1f47768df667d3f612`；分支 `dev/f2-ordinary-synthetic-demo-20261018`。合同先行提交 `5e61cb1d84dd3e5c9523921be1d82856c3c45f83`，独审先冻结9条原文字面oracle和22份输入，然后才读取实现。既有44项admin配置验证不计入本片成绩，完整项目未完成。

原功能依据是产品§4.1、§12.4、§15、计划F1-T01/T03、F2-T06/T07与§13：真实外部来源属于独立依赖，不应阻塞可运行合成软件；完成普通流程不应要求用户手改数据库。已核原`test_ordinary_case_goal_results.start`有新资料→诉求→旧确定性planning-preview→明确ADOPT→普通P1–P5。本片没有重写规划，也没有删除V4/demo/Native与CURRENT_PREPARATION互斥。实际断点是旧源码ZIP和material-only启动器不能提供全新完整配置。

新增 [普通合成演示启动器](../../scripts/ordinary_synthetic_demo.py) 与 [用户操作说明](../demo/OrdinarySyntheticDemo.md)，详见 [合同](OrdinarySyntheticDemoContract-20261018.md)。`setup`仅创建新的私有 `/tmp/parkweave-ordinary-demo-*` 集群和必要SYNTHETIC初态，走原fresh creation receipt/migrate32；`serve --state-dir`核对并复用同一库，普通API/worker不隐式初始化、补权限或续期。启动只需已有Python/Linux依赖；没有依赖安装下载、DSN/身份/SQL导入参数。所有实际初始化和负例只发生于本轮新拥有合成集群，未执行真实安装/赋权。

初态为3主体、4 capability、1 action、2 preparation Grant、1明确SYNTHETIC资料目录、2资源及4 READ/HOLD资源Grant，共17行业务配置；field_grants、Run assignment和业务记录为空。普通进程使用独立非owner/non-superuser app，只给原流程所需SQL权限；新库PUBLIC数据库/模式默认权先撤回，app无schema/public/temp DDL。会话只保存在私有文件，源码/URL/stdout不含token或DSN；会话无自动到期，停止服务不撤权。

serve绑定实际源码内容（src运行文件+3个所用脚本）、原cluster system identifier/数据库OID/schema32、业务权限/目录/资源摘要、session文件哈希及实际app角色/成员、database/schema/table/column ACL。该状态绑定是自有合成现场校验，不是生产签名/批准，也不是完整宿主/全部SQL权限审计。初始化helper再次要求原精确live FixtureDatabaseEvidence并核对当前连接；落盘creation-observation不能恢复票据。serve不调用该issuer或migration；重新启动的普通worker仍可按原授权继续已有排队任务，不能把初始化的只读校验解释为worker全程只读。

根最终同SHA单窗 **11 PASS，0F/E/S**，pytest122.480秒、外层126.09196573700319秒，exit0：新入口8节点，另3原回归（Native read config互斥、LOCAL_SYNTHETIC_DEMO profile互斥、原普通资料/接单/回执/通知正向）。没有用多个开发窗口拼成该11P。

主链真实运行两轮API/worker，setup产生空库后由用户HTTP提交A新诉求，原worker实际完成Run/Case，双材料、指定专员REVIEW、owner CONFIRM、明确五目标及ADOPT、原P1、两资源组合/Case关联/P2、专员OFFER/本人ACCEPT/P3、手工SUBMIT/owner ACK/P4、本地REVALIDATE/CLOSE及明确P5全部完成。随后停止API/worker/PostgreSQL，物理重启同库，A的结果和原TXT字节一致；再以B不同诉求/材料完整走第二条P1–P5。A/B的Run、Case、preparation、plan、dispatch均不同，A历史/结果保持，权限摘要和state marker不变，Run assignment始终0。测试未调用Store.finish、旧ready.assign_status或隔离Approval代替用户链。

该主节点只有2个普通API和2个普通worker进程；原完整HTML在NodeVM中核对与导出共19+19=38断言，均是只读GET，停库前后TXT字节相同。NodeVM提供DOM机械替身，不是实际浏览器；普通HTTP完成了全业务链，未声称全链浏览器点击验收。原300秒OFFER截止保留，重启不续期，关闭不释放原资源，仍不代表Case真实目标完成/外部受理/线下履约。

其余新节点覆盖被占端口不接管/终止监听器、没有live receipt不得初始化、源/schema漂移在PG启动前拒绝、业务Grant和SQL ACL漂移不修复、initdb故障只尝试一次并保留目录/日志、worker spawn故障停止精确owned API和PG且保留状态。正向与负例数据库均独立合成，未更改已知旧material-only库。

814 frozen输入shared/mirror PRE/POST四map相同，archive SHA256 `f13477a3e32ecbaf77009e4d8633837bacee2322136fc6e29d8476f2bbcc6222`。根112个parkweave/test/support导入来源均位于mirror并重hash；该旧hook未收scripts.*或安装到API/worker子进程，不扩称其逐模块import审计。另从主链实际owned marker核对189个runtime文件内容摘要全部与814输入吻合；这也是源码内容绑定，不代替子进程逐模块审计。796个原src/tests/scripts/pyproject文件逐字节等6067，原src tree仍 `69c81c4e939095208cb5992a931400bd46156aec`。旧material启动器、Linux fixture server、业务SQL、角色、conftest、Native和规划算法都未改；只有README接新说明及新增脚本/测试/合同/操作说明。

独审同SHA单窗 **5 PASS，0F/E/S**，JUnit53.603秒、pytest.main55.30403263300104秒、外层56.530067405998125秒，exit0，无失败/重试/补测。9条先冻结oracle的SHA256为`8ccb2646fee739d14173b3d7055c446fe90a4d9829fad5d21ed7a70380f6be06`。3个独立负例节点覆盖无Git完整源码内容绑定及helper漂移、私有会话权限漂移；持有锁/未知postmaster PID/旧material目录前缀均Popen0拒绝且不接管；自有新集群app角色成员漂移准确拒绝且不修复。另重叠根主链和live receipt两个节点，因此 **11+5−2=14个唯一PASS**。无开放P1/P2发现。独审同814输入PRE/POST四图也全等，private probe前后未变；68实际导入来源为67冻结+1私有probe，已实际核对3个生命周期脚本SHA。API/worker未另装逐模块import hook，不扩大审计结论。

独审4个自有状态和12个会话值均私有保留；3个状态无postmaster marker，另1个仅保留测试主动写入的未知PID负例marker（Popen0、非活进程、不删不杀），均无stop-unconfirmed。负例状态含主动权限/marker变化，保留并不等于可再次正常启动。稳定[独审结论](evidence/ordinary-synthetic-demo-20261018/independent/independent-final-review.json)、[原文oracle](evidence/ordinary-synthetic-demo-20261018/independent/literal-oracle-plan.json)与raw映射已逐字节归档。独审报告、发布清单、raw/public map、raw manifest的SHA256依次为：`2660b876455a8631558a529ffc7f35689e5270fca394c05540097e94bdecc3d3`、`74d9ee162c0e322e317b988cba98213bd02b819a63bcfa18b35ffd0b47a1a0dc`、`30fab4a58fe66ee2c21e44b63b0055d287bb45a3cdac1c9aa8eb0963dc60cdd4`、`d60e80c2d9a6a4bd6cac1be66293dca9447d8ca6614b4a4b65d0309a72757411`。

开发保全：初版setup实际成功并保留其独立状态。首主链1FAIL/9.944秒，是新测试误从原步骤视图读取不存在的request_intent字段；当时普通worker、资料核对及planning-preview已完成。只将测试改为保留request-intent保存响应的revision，未为该错误改产品算法。随后开发6PASS/57.236秒，两项故障控制2PASS/4.092秒；后续加入实际DDL限制、会话/文件绑定后，由最终11P重新覆盖。开发工作树窗口没有完整冻结输入/导入映射，不归属于最终SHA或新增唯一通过数。初始pytest traceback曾含自有合成会话，raw仅私有保留，公开副本按已登记值脱敏；之后测试用PrivateTokens隐藏repr。

[公开证据目录](evidence/ordinary-synthetic-demo-20261018/publication-files.json)共224文件：221对raw/public加3个控制清单，其中219对逐字节一致、2对因会话脱敏变化，共10处替换。独审72个canonical文件全部逐字节复制，不二次脱敏。全部JSON/JSONL/XML解析成功，XML节点与失败结果保留；78个登记自有合成会话及其16字符前缀、traceback截断片段均0命中。raw配置、session、创建票据和PG data不公开。脱敏映射记录原始与公开SHA256，首个开发失败仍保留原结果。[归档校验](evidence/ordinary-synthetic-demo-20261018/archive-validation.json)与[映射](evidence/ordinary-synthetic-demo-20261018/raw-public-redaction-map.json)可复核；这224文件不含本验证报告。归档后再次核对814实际工作区输入仍等受测映射。

运行边界：仅已准备依赖的Linux合成环境；setup和serve分离，既有目录不重置、故障不自动再建，状态与日志保留在/tmp，不承诺永久存储。未知锁/PID/监听器不接管、不删、不杀，只停止本次实际创建的子进程；停止无法确认就保留marker并拒绝后续启动。部署、真实身份/Grant/capability/分派/目录发布/批准/凭据配置、真实模型与费用、安全网络权限扩大均未执行。V4注册服务选择/模型与普通CaseStep的组合仍未交付；正式来源backend/验真/映射仍等待具体协议，但不再阻塞本普通合成入口。Windows、WSL、浏览器正式场景、正式AT35及真实业务均NOT_RUN/未验收，完整产品和比赛交付未完成。

正常开发分支推送后的完整交付SHA、远端heads差异、显式0/0与工作区状态以最终回复和私有 `.runtime/ordinary-synthetic-demo-20261018/delivery-and-remote-verification.json` 为准；不在推送前预填成功。

运行所需输入：普通合成入口现在只需已准备的非root Linux/Python3.12仓库依赖、完整匹配源码、一次setup产生的私有state_dir、可用loopback端口和本机session文件；这轮A/B已实测，不需要外部DSN或手工SQL。要在已有真实配置库运行，仍须由有权方提供当前身份/来源修订可验的PREPARE、REVIEW_ASSIGNED和同scope preparation_catalog及匹配provider；本入口不会替真实库产生这些授权。正式外部来源分支还缺具体reader/provenance验真协议与可核验来源对象/修订映射，Native permit/writer和正式安装授权也未提供；缺任一必要输入继续准确拒绝，不借用IsolatedPlanApproval成功fixture。

最终封存检查：产品源码/合同/说明/报告的whitespace检查0项；原始证据中23项空白诊断保留（initdb尾空行、原patch/pytest输出），不修剪原件。首次暂存校验器误将失败traceback中两条`+tests/...`上下文也当成Git诊断，发生1次机械断言失败；修正仅该解析器后再核验，未改源码、证据或重跑业务测试。该封存失败记录私有保存在`staged-verification-attempt1.json`，不计入11/5/14业务测试结果。
