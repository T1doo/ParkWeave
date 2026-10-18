# 第二企业、第二园区首次普通办理：有限交付验证

受测完整SHA：`b5f3a4a491a7f7c70c0c7ca23c35bb6b3d89c595`。基线`a396f63eed027d4ccf8dc1ed6f591766915449ae`；合同先行`03685a1af1ff83f591353eb3d5cd8c95163c1afe`；新分支`dev/f2-ordinary-synthetic-scopes-20261018`。上一片14唯一项为历史证据，本片未选其中同企业A/B主链，不叠加旧成绩；完整项目仍未完成。

原阶段计划F1-T03要求至少两个企业和两个园区配置，F2-T06要求新企业冷会话、新材料与独立Case，AT04要求后端跨范围隔离。已先读原主计划、F1/F2阶段计划及产品设计，独审用a396 Git blob固定813份基线输入后冻结10条原文字面oracle，SHA256`47be183682aba5a4b015141308e276f6f1c045370cbc6887d9110b75a29d902c`，再读新实现。[本片合同](OrdinarySyntheticScopesContract-20261018.md)限定普通合成最小项，不把两组配对范围当完整园区×企业交叉矩阵、F3跨园区迁移、正式模板审核发布或AT08/35完成。

[原启动器](../../scripts/ordinary_synthetic_demo.py)的全新setup在同一个自有合成集群/数据库里准备两套固定范围；各自有企业/专员/执行者、独立随机会话、现有同scope能力及资料Grant、各园区资料目录和两资源及本企业READ/HOLD。初态6主体、8 capability、2 action、4 preparation Grant、2目录、4资源、8资源Grant，共34行业务配置；field_grants、Run assignment、Run/Case/资料/材料/计划/分派/回执为空。SQL权限种类、角色属性、PUBLIC撤权、live creation receipt/migrate32及后续源/库/权限摘要核对均复用上一片，不给app新增任何SQL权限。没有真实身份/授权/目录发布/批准或凭据动作。

用户按[操作说明](../demo/OrdinarySyntheticDemo.md)在私有sessions.json选择原enterprise/specialist/executor或独立second_enterprise/second_specialist/second_executor，使用原页面的会话输入、目录、专员、执行者和资源列表。就绪输出available_scopes仅含标签/键，无会话值；页面和后端不新增自动登录/选角色或包装界面。state schema升级为`parkweave-ordinary-synthetic-demo/2`并绑定完整固定scopes；缺失/改动范围，在启动PG前拒绝。旧`/1`状态不迁移、不seed、不补第二范围，保留用原5b36291a源码启动；本片只创建全新自有状态。

根同SHA单窗 **7PASS/0F/E/S**，JUnit84.355秒、外层87.69179229000292秒，exit0，7 collection与21 setup/call/teardown完全一致。新2节点为实际双范围主链和范围元数据缺失/漂移拒绝；另5节点是原provider互斥2项、live receipt初始化拒绝、initdb一次失败保留、worker spawn故障精确owned清理。没有重跑上一片同企业A/B节点或旧大矩阵。

主链只有一个实际CLI setup和同库两轮API/普通worker：第一企业一Case用于跨范围对照，双新材料、独立REVIEW/CONFIRM、原确定性预览明确ADOPT、原P1–P5、两资源关联、本人ACCEPT和手工SUBMIT/ACK、本地重验/关闭。物理停PG/API/worker后，重启同system identifier/数据库OID；第二企业冷会话列表为空，然后以新诉求、新材料、自己的专员/执行者/资源独立完成第二条P1–P5和TXT。两Case的Run/Case/preparation/plan/dispatch/receipt/evidence UUID均新建；没有Store.finish/fixture assignment/复制旧Case或证明。重启冷读第一Case的TXT字节相同；第二Case办结后第一Case结果和原deadline保持，state/authority摘要不变，Run assignment始终0。两组资源时间窗重叠但各自独立资源；未声称容量并发竞态验收。

实际40次拒绝作为主节点内部断言，不计40个用例：双向Run、资料、规划、目标结果、本地记录、资源组合/占用、dispatch和三角色receipt直ID读取；第二范围不能用第一Run建资料、选第一专员/执行者、使用第一资源/组合或拿第一预览source hash给自己的新计划采纳。分别得到原403/旧source409，原业务表摘要保持；审计写入与业务无副作用分列，不声称所有数据库字节不变。第一与第二当前列表各只含自己的事项。六类scopes缺失/园区/组织/主体/资源/会话键漂移的负例均在PG前拒绝，0进程创建，不自动修复。

原完整HTML的NodeVM核对/下载分别19+19+19=57断言，均GET，只读导出；DOM为机械替身，不是实际浏览器。本次没有全链浏览器点击验收。普通原300秒OFFER、独立占位期限、人工明确核验和关闭语义保留；暂停/重启不续期或撤权，Case目标完成仍false，资格NOT_EVALUATED、外部受理NOT_SUBMITTED、线下履约NO_EVIDENCE。

820 frozen输入shared/mirror PRE/POST四图全等；源码archive SHA256`ae493fac96375fd8c0c4e1c601ed587abd1c7d417369d00d1b23f5bb609b92e8`。116个实际主pytest模块来源均在mirror并重hash，包含ordinary/material/Linux fixture三个脚本；API/worker未另装逐模块import hook，不扩称子进程全面导入审计。3个root实际owned marker的189 runtime文件SHA全部对上820输入。798原src/tests/scripts/pyproject文件中796逐字节等a396，仅启动器和原测试helper改变，另增新测试；186个src、SQL、业务角色、conftest、旧material/Linux helper及provider/规划算法全等，src tree仍`69c81c4e939095208cb5992a931400bd46156aec`。

独审同SHA串行单窗 **5PASS/0F/E/S**，JUnit69.891秒、pytest.main71.0620920049987秒、外层71.89239962899592秒，exit0；5 collection、5 setup/5 call/5 teardown及JUnit完全一致，无失败/重跑。3个独立小负例分别验证双向外国父项与source proof拒绝且业务不变、同精确区间的各自资源组合及混合/外国组合拒绝（0Run/Case）、当前缺失/交换scope metadata及亲自拥有的旧schema1前置拒绝。旧0spo1vlc状态仅以opaque文件字节hash前后核对，不解析旧会话、不开旧PG、不写failure.log，PG/Popen尝试均0，全部旧文件哈希相同。没有再造旧库或另跑一条私有完整正向链。

独审另执行根新2节点，与根7精确交集2，所以 **7+5−2=10个唯一PASS**；不加上一片14或开发重复节点。69个独审实际导入来源为68冻结+1私有probe，含3 scripts；shared/mirror八图820输入及archive相等、probe未漂移。5个独审新owned状态、30会话均私有保留，均无postmaster或stop-unconfirmed。无开放P1/P2；首次开发超时仍UNKNOWN，不以最终通过代称根因修复。

[独审结论](evidence/ordinary-synthetic-scopes-20261018/independent/independent-final-review.json)、[原文oracle](evidence/ordinary-synthetic-scopes-20261018/independent/literal-oracle-plan.json)与93份canonical原件已逐字节归档、未二次脱敏。结论、清单、raw/public map和raw manifest的SHA256依次为`136ea8381fdb65143ff0e872949be723d130a974f519156ee57c82b68219a4cf`、`fb0d0c6f4232351c6986583a98b66ef0768cac153cc6856bca9b5c433433892d`、`477716802b09a8e47c9fec722175b6eaa4f67b2832523fcd1e15483438b60838`、`e9eddc44b08f0be53fd123462567a26904cb5c11b9e4ab3802db762f49a2f8c4`。

开发保全：首WIP两节点1PASS/1FAIL、0E/S，JUnit168.798秒，输入前后相同。第二企业在原local-case命令HTTP20秒读取超时，trace缺action/key；只读重启其已停自有PG后可见第二REVALIDATE已提交、ledger READY/rev1、没有CLOSE。该观察不能判断超时发生于REVALIDATE已提交但响应未读，还是之后CLOSE；PG preparations FOR SHARE锁超时也出现在成功第一Case，不能据此认定环境或产品根因。没有重发未知POST，没有提高20秒HTTP/3秒锁/300秒OFFER期限，没有修改业务算法。后续只增加测试HTTP action/key/path/单调时间（不含token/body）及ReadTimeout一次有界只读activity/blockers采样，再冻结并执行最终7窗；最终通过不作为首失败已修复的声明。原目录、请求失败、PG/application日志及只读观察保留，后来的取证PG日志另快照不覆盖首窗日志。

初次证据采集因pytest-current父符号链接重复枚举同一状态而FileExistsError，首状态日志已复制；已保留失败说明，改为跳过链接/按实际状态去重并核已有副本字节，再补另一个负例状态。没有删除或重建任何失败数据。根最终4个新owned目录（3有state共18会话、1initdb故障无会话）与开发2目录均保留；root已核无postmaster或stop-unconfirmed marker，负例状态主动篡改的配置保留不等于可正常启动。

[公开证据](evidence/ordinary-synthetic-scopes-20261018/publication-files.json)共209文件：206对raw/public加3个控制文件，206对全部逐字节一致，0文件脱敏/0替换，所有JSON/JSONL/XML解析成功，XML节点及失败结果保持。80个登记的自有会话值、16字符前缀及可归属于这些值的traceback片段扫描均0命中；主体ID不当作会话片段。会话值、配置票据和PG data未公开。独审93个canonical逐字节等原件；820当前输入在归档后再次相等。首开发1FAIL和证据采集FileExistsError保留，不改写成功。[归档校验](evidence/ordinary-synthetic-scopes-20261018/archive-validation.json)和[原件映射](evidence/ordinary-synthetic-scopes-20261018/raw-public-redaction-map.json)供核对；此209文件不含本报告。

运行输入：已有非root Linux/Python3.12及仓库依赖（含pgserver0.1.4）、完整匹配源码、全新setup产生的私有state_dir、可用loopback端口及按范围/角色选择的本机session；启动器不下载或安装依赖、不接受生产DSN或导入身份/SQL。真实既有库仍须有权方提供合法PREPARE/REVIEW_ASSIGNED、同scope目录/来源修订及匹配provider；正式来源协议/验真/主体与采纳映射、Native permit/writer和正式安装授权缺口保持，不能借IsolatedPlanApproval测试fixture补齐。provider互斥保留。

Linux演示不等于安装器、Windows/WSL、正式AT35、真实浏览器、真实园区/企业/模型或生产验收，以上NOT_RUN/未验；全项目未完成。没有main修改、强推、部署、费用/安全网络权限或真实身份/Grant/分派/目录发布/批准/凭据变化。未知锁/PID/监听器不接管、不删不杀；只停止自己实际创建的子进程，失败和/tmp状态保留，不承诺平台永久存储。推送后完整交付SHA、远端差异和未提交状态以最终回执及私有delivery-and-remote-verification.json为准，不预填成功。

最终暂存检查：产品源码/合同/操作说明/本报告的whitespace检查0项；证据目录50项原始空白诊断保留（原patch/pytest上下文、initdb尾空行等），不修剪原件。209证据文件与本报告逐Git blob核对后再提交，检查记录私有保全。
