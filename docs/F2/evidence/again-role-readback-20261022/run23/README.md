# run23：不同新输入采纳与三个新角色会话读回

[官方run23](https://github.com/T1doo/ParkWeave/actions/runs/39787958372)，job `119856010803`，attempt1，受测完整SHA `c34668fe8d6dc2448917642b24800d5e337e6903`。**本轮完整候选实际限定PASS**：最终[result.json](result.json)为PASS，job及所有step成功，无error／finalization_errors／violation／page_error；不拼run22片段。[run22 FAIL及修复原件](../run22/README.md)保留不改。本次只重绑定23门号，业务／字体／权限／预算逻辑与已审修复逐字一致，未重跑pytest或collection。

同一新合成实例中，A五目标／B单材料目标各用不同新诉求、双槽材料、Run／Case／preparation／NO_MODEL候选／采纳计划；不是复制旧Case、材料、授权或核验。A原P1/P2及本地资源批准仅作必要前置，原专员OFFER、本人ACCEPT后真实生成一个回执步骤，未提交P4正文；B经独立REVIEW、原DOM本人CONFIRM与明确ADOPT，仍P1 PENDING。三次DOM的原key／主体／动作和真实SQL事件保全；ACCEPT成功后原键GET COMMITTED。此处不重签P1/P2/TXT，不称完整第二办理。

三个全新浏览器context分别重新输入原既有会话，起始localStorage为空。owner／专员各精确读回A/B新材料，owner另读两份各自计划／候选（必需目标5／1）；A显示VERIFIED／VERIFIED／PENDING／BLOCKED／BLOCKED，B单P1 PENDING，不继承核验。executor正读A真实dispatch及receipt.step，Case／Run／preparation／step精确，AWAITING_RECEIPT、revision1、`current_receipt=null`、原assignment deadline不续、Run访问仍false。

对真实存在的B，executor `GET /api/preparations/{B}/dispatch` API403；原已有记录入口 `.../{B}/entry` UI403。原导航已清屏，拒绝后preparationView／servicePlanView／dispatchView／receiptView保持null，不冒充403单独导致清屏；未伪造B回执ID、未用404充权限拒绝。只读阶段46 GET＝42×200＋4×403，0 POST；六次主流程403中其余四次fact-clarifications拒绝单列，不当成功、不绕过。

结束时源码实际重取两Case命名业务投影并与sealed前快照精确相等。result保存两份sealed投影及成功标记，**未另存post快照**；独审确认运行时断言，不称离线独立重算after或全DB不变。另A before／after B投影原件可独立比较，仅global cases排除新增B一行，其余命名投影相等。

总29POST全部成功＝26API＋3DOM；109 GET/HEAD＝90主流程＋19就绪，主流程84×200＋6×403。业务完成40.057s，40.11s计至附件扫描，非全部最终化时长。原10min免费job／270s工作／360s绝对收尾、40POST／26API／8DOM／400GET／2worker、Chrome正常sandbox、固定Noto/OFL私有使用及10文件／8MiB门保持。

五张原图：[B新材料](01-new-input-confirmed.png)、[owner B计划](02-owner-distinct-plans.png)、[专员B材料](03-specialist-distinct-materials.png)、[执行者A空回执](04-executor-own-record.png)、[B拒绝后界面](05-executor-denied-cleared.png)。当前五视口1200px、中文可读，无横溢；02只B计划而非两计划并排，三角色完整数据由JSON支撑，不签390px／手机实机／整页像素。三次真实CDP字体检查分别16／15／21可见节点通过；动态“培训大纲”按实际可信face原charset覆盖，非全部码点逐glyph视觉归属证明。

191包文件逐字对应受测Git树，wheel仅在[官方ZIP](artifact.zip)内，构建／安装零依赖下载（原bootstrap另列）。两个worker exit0；一个API／PG代次及wrapper均exit0，marker消失、监听拒绝、无清理错误；setup PG亦exit0，不是服务冷重启。字体二进制未放证据包，未新增模型调用／凭据／权限／费用。

ZIP1718959B、8原成员、解压2576320B，SHA256 `672cfa2e9d81aa165e9bbee1d16f2c18591801ea1a20ced75f405cd1185c479c`；[完整decoded API job日志](ci-original.log)1047970B，SHA256 `ea95aeae67739947e3e65cad6190bc23d74e6c9e18262eb30cce031497845207`。stdout PENDING规范化与最终result逐项相等，不把PENDING当PASS。日志未出现旧summary size-abort，summary正文／上传未独读；不把allsteps success冒充正文联合验真。

[run](run-api.json)／[job](job-api.json)／[artifact](artifact-metadata.json)元数据、[原件核验脚本](archive_run23.py)、[限定回执](validation.json)、[仅门号差异证明](binding-validation.json)、[等价源码发布映射](source-publication-map.json)与[校验和](checksums.sha256)均可读取。全局9521项仍只属原collect记录，不加计为PASS。

仅关闭本次AT35工程子门：不同输入采纳、对应角色持久读回与不串单。B全部履约、正式外部来源／正式AT35、Windows原生／owner门、LIVE／真实模型、C0实际材料及冷重启不在本轮；Case目标未全部履约。
