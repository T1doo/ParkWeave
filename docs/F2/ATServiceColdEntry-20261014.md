# 受信配置原页冷输入与固定AT重放

承接交付`3bc1e96ccc6b6d73a5f1488bee644f92a15ddd97`，本批最终源码`6ac59ad0a2c2434bc85dccbf323b707ba23c9db4`。本批补上实际产品缺口：企业不再必须自己编辑JSON或借用已有Case，才能从当前受信ParkInstance准备新事项。原页面提供本人实例发现、新材料表单、逐阶段确认和原key恢复，然后进入原资料、服务选择、明确采用与本地办理入口。

默认仍关闭；未注入精确owned fixture facade时GET403。目录最多16项，当前本人READ/PREPARE/EXECUTE及原case.create、原审核来源/版本和角色/资源映射须有效；不泄露其它主体、材料或资源ID。成功GET的46张PG表及两个consumer journal全不变，不占模板源写租约。拒绝仍按原HTTP handler写DENIED审计，其余45张表不变，不能笼统写所有拒绝零写。没有迁移、Grant、registry、凭据或生产配置变更。

新材料按两个原槽位的当前input_field映射输入，必需目标完整保留，包括额外不支持目标。facade仅准备原命令；原Run、资料创建、诉求保存及两次材料提交都须各自确认。Run由原worker处理，页面不能finish或赋权。stage key严格核原tc派生键、正文规范化SHA和subject；plain actor_id与opaque actor_ref各核原意义。localStorage只存opaque actor/key及最多10个已发送标记（准入1、描述4、原命令5），不存材料、token或正文。

发送前写入标记，响应丢失只GET原cold key；未观察到不证明未提交，跨刷新仍不能重发描述或业务POST。只读恢复展示原诉求、全部必需目标、两份材料及来源。没有当前配置/办理权限时不能进入办理入口，但READ历史保留；已核实五阶段的原输入可由本人明确结束，清除已解决句柄，不发任何请求，也不阻挡随后切换专员。403统一清私有缓存，保留未知opaque。迟到响应不回填新身份。

各原业务请求仍由其原权限/资料版本合同独立提交；目录、准入和阶段描述核配置，跨这些独立HTTP动作不宣称统一事务。配置变化不自动迁移或撤销已发生的原Case效果；后续准备/选择/采用必须重新核当前来源。未知阶段不自动换key、改正文或继续剩余步骤。

固定判据来自原`docs/验收规格.json`和V1产品§4.3、§5–8，原steps/oracle没有改动；[逐字快照](evidence/at-service-cold-entry-20261014/gap/fixed-oracles.json)单列来源hash。

| AT | 本批实际工程范围 | 完整判据仍未验部分 |
|---|---|---|
| AT-07 | 原受信三能力、六必需目标、离线compact refs、服务端重建与预检；原明确采用、执行及实际回执反馈重核 | 真实模型效果/LIVE未验，不签完整AT |
| AT-08 | 原页面从无Case新输入；两次不同冷输入形成不同Run/Case/材料/候选/结果；10类错误输入拒绝且46张PG表和3张journal不变 | 正式生产ServiceRelease治理与真实企业投用未验 |
| AT-14 | 本批仅owned SYNTHETIC隔离PG；不能把只读目录/候选或这条原业务链当预览执行隔离验收 | 完整预览写后对照LIVE命名空间、生产资源与Grant的独立门未在本批执行 |
| AT-33 | 第二园区业务A有限原办理；C子集原资源组合取消令P2/P5当前证明失效、六目标和另一Case历史保留 | A/B/C是三类业务，不是Case编号。B缺受审规则与授权事实闭环；现readiness工程规则MANUAL且DRAFT/ENGINEERING_ONLY，不能用材料TRUE/FALSE冒充准备度。C替代提议及执行未验 |
| AT-35 | 两次不同输入、原V4采用→P1–P5；REQUEST_CHANGES→v2 ACK→REOPEN/v3使P4/P5当前证明失效后明确重核恢复；第二次不改首历史 | 原生产授权准备、真实履约和完整正式AT未签收 |

初始owned synthetic fixture种子与运行期分列：两轮全链使用既有受审模板fixture和第二园区资源初始化，额外资源权限4条及各新Run原fixture assignment均是测试前提，不是应用运行期授权。原页冷输入7模式不需Run assignment，运行期新增Grant/assignment/model调用均0；Run由测试侧原claim/finish驱动，不冒充自然人/真实模型。

| 验证窗口 | 实际结果与来源 |
|---|---|
| 目录后端完整三个模块 | 63 PASS，0 FAIL/ERROR/SKIP，2 WARN，25.57秒；产品Python与最终源码字节相同 |
| 最终页面跨入口四模块 | 154 PASS，0 FAIL/ERROR/SKIP，2 WARN，12.62秒；web为最终2e6de9，549文件零漂移 |
| 实际PG/API→全HTML七模式 | 7 PASS，0 FAIL/ERROR/SKIP，2 WARN，13.59秒，552文件零漂移；正常、准入/Run/材料/阶段描述丢回复、阶段描述未送达未知、撤EXECUTE只读恢复 |
| root早期c8回归 | 191 PASS，2 WARN，43.95秒，553文件零漂移；其后独审仍发现3项反例FAIL，不能把该窗提升最终签收 |
| 最终root九模块 | 195 PASS，0 FAIL/ERROR/SKIP，2 WARN，49.03秒，553文件零漂移；精确最终6ac59ad源码 |
| 最终独审 | 212 PASS，0 FAIL/ERROR/SKIP，2 WARN，54.68秒；554 tracked（553源码+pyproject）与4私有probe共558文件零漂移，70个实际加载parkweave模块均来自独立私树 |
| 最终离线wheel | PASS；152 package文件精确一致，无缺失/多余/改变；SHA256 `fab34986200e0f59124c0b75d8fe9df46eddf03edce60c2e854a558b1eb72664` |

各窗独立，不加总。旧1476/91及152文件包核对仍仅对应上批冻结SHA，不重跑或转签新源码。原始FAIL/ERROR/log/XML/exit与traffic保留：真实stage key/主体/角色接线问题，持久阶段描述未知和403缓存产品缺陷，以及测试DTO/fixture/过度断言错误均分别记录；不把脚手架失败当产品缺陷，也不删除产品首红。

518归档已补完独审：首次FAIL发现8个实际临时fixture会话，两个导出共16处，精确替换后518件新独审PASS。原runtime与旧NOT RUN回执未改，原FAIL和新PASS均在[补审结果](evidence/at-service-cold-entry-20261014/archive518/audit518-corrected-result.json)；原索引修后SHA`0aa134d3272b404a09c6e4accfe0f36376492aa3f93bc8aef801d50a8de396d6`。

有界免费CI资格核实首次`gh repo view T1doo/ParkWeave --json nameWithOwner,isPrivate,defaultBranchRef`返回`Post "https://api.github.com/graphql": Forbidden`。已停止该API动作，无重试、替代端点或新workflow绕过；CI NOT RUN。正常Git开发分支推送仍独立获准。浏览器历史管理员拒绝不重试，Windows、真实模型、付费调用、生产迁移/部署均NOT RUN。

完整原始证据与来源manifest见[新批次索引](evidence/at-service-cold-entry-20261014/export-index.json)。284件已独立逐字节/hash/长度/路径与43字符候选上下文核对PASS，无实际会话或替换；15份非零exit失败原件保留。首次保守扫描12个候选待审exit1与复核PASS另存，[最终归档审核](evidence/at-service-cold-entry-archive-audit-20261014/audit284-context-reviewed-result.json)在索引外，避免自校验递归。

源码与报告diff空白检查exit0；原始pytest失败证据的尾部空白保留，归档diff检查exit2，不为格式改写失败证据。

完整批次后仅正常推送原开发分支，核本地/直接远端/tracking一致、源到交付无代码差异、工作区干净且无未推差异；main/F1/原F2及其他远端分支不改。下一批应补独立预览namespace门、受审合成规则/授权事实的准备度与变化替代执行；真实模型、Windows及正式治理须保留未验，不用工程PASS代替。
