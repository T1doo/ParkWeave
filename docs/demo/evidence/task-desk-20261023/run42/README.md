# run42 新模板页必要呈现候选：未执行

直接父 `4406f5f254bb53e53ca08ba8bd50ea228e36b67e`。实读最新 run41／39997338997／completed success，预期下一编号42、attempt1；执行ref仍a3813ca8。本轮只发布不匹配任何现有 workflow 的审查分支 `dev/ui-template-entry-run42-review-20261023`，不推进执行ref、不启动原生采样／CI。真正执行前仍须再读最新编号与精确ref，不能复用旧run或旧PASS。

## 隔离入口与安全差异

新增精确模板HTML指纹，三页均须与直接父原字节相同，另封存原 `template_isolated_app.py` 和 `template_candidate_api.py` 的SHA。前者真正挂载 `/template` 前要求显式 engine/consumer 合同、同Store/engine和fixture校验；本驱动不调用该工厂，不创建假生产者或接通部署。原API、路由、权限、安全门及产品代码不变。

本窗口沿用已有自有回环静态呈现服务器，仅新增精确GET `/template` 返回冻结模板页，以及 `/api/template-candidate/status` 两次关闭态只读 **UI投影**；它不是完整API DTO或生产状态证明，缺额外领域字段不当作空事实。enabled_for_isolated_tests=false、无personas，原banner明确“候选未启用”。没有新隔离服务、产品API、PG、模板引擎、身份、Grant、凭据或批准被构造／启用；旧资源响应夹具移除。完整原网页script照常执行。若要求真实factory／服务启动，应另核对应材料与执行范围，不能由本片冒充。

为看长文本、PARTIAL提示、禁用态，显式UI_STATE_FIXTURE只调用原renderPlanning/buttons并填入虚构草稿，再以原cp对象布置SUBMITTING／UNKNOWN；不是实际发出过的请求或真实partial资格。instance/catalog/confirmed/view始终null，治理及创建／继续／确认／保存／采纳／收尾始终disabled并反复断言。原关闭banner保持DOM可读，局部截图不保证同时入镜；每张模板PNG可见“候选未启用”fixture标记；原对象、body、十三字段、goal选择和存储基准不变。对禁用草稿的受控DOM变更交给原input恢复handler，不能称真实键盘可编辑。无创建、采纳、发布、重试或收尾点击，两层POST拒绝和未知GET 404维持。

## 最小七图与原生观察计划

|图|严格局部范围|
|---|---|
|01/02|1200/390原h1、关闭banner、两个定位入口在视口内，不称整页|
|03/04|1200/390企业两fieldset完整原说明、checkbox/限制及禁用状态；marker在legend后，不缩字、不裁警告|
|05/06|1200/390原找回/继续区域完整局部；只是入口呈现，不读取实例或证明恢复成功|
|07|导览390的原文件加载就绪按钮稳定终帧，不打开popup或重跑旧八图|

两fragment指向企业/审核整个section，并非专用恢复表单。两个宽度正常态均真实mouse与Enter；核同文档sentinel、hash、历史、原activeElement、Tab第一控件、Back及请求增量0。Back保留一个forward entry，下一次原生导航可能替换该项，不能误要求history.length每次增加。按Tab前就记录原目标h2的真实矩形并断言可读落点，不能拿后续compose/frame代替原生滚动证明。SUBMITTING/UNKNOWN只额外用Enter验证企业链接，比较同一个对象/body/草稿/存储和禁用门，不夸大为全状态全导航矩阵。

700/899/900仅几何，finally恢复原viewport/scroll；原长PARTIAL checkbox另做可见矩形及字体观察无专门PNG，仍非实际partial读取／确认／授权链。人工取景只移动fixture标记和页面滚动，frame_required留16px；其他entry图仅核必要节点在1000高视口内。无法完整入镜即失败，不缩字号、不扩视口。

导览仅用原set_input_files处理合成六身份文件，不测OS选择器。保持原动画，等实际getAnimations完成，再双RAF，捕获同按钮color/background/opacity/transitionDuration/property/animations与viewport；opaque实色对比须>=4.5，截图前后computed相同。新稳定帧不解释旧08的中间色成因，不取消动画、不改产品色，也不是全WCAG签收。

## 固定预算、离线证据和未验范围

原公开hosted Linux、正常Chrome sandbox/CSP、只读仓库、固定字体/许可、job10分钟/依赖3分钟、90秒工作及清理/85秒worker/360秒绝对发布、每侧最多39GET/POST0、最多10文件8MiB不扩。7PNG+result+预留失败图共9个允许名称。仅两次模板初始化投影GET和三次页面导航，favicon仍算累计；导航与状态检查不新增GET。字体同已批准文件和大小/blob校验，仅extra_text增冻结模板页以核其全部码点，实际glyph仍按参与face核验，不据字符集合称全页视觉通过。

三上下文、无业务服务或popup，正常预估字体/启动约15–25秒、导航/状态/七图约20–35秒、清理约20秒；这不是实测或独立新增额度。原15秒等待/30秒新context准入及所有总时钟不缩减；不足即失败保全并停止，不能自动加时或删场景来过。本候选尚无实际耗时、PNG、glyph、导航或清理通过结论。

实际离线：来源正反约束/三页与入口源码hash、原预算监督函数字节保全、所有JS片段语法和真实SDK等待签名、opaque对比正反、原Handler内存静态页/两关闭投影/超额与业务GET404，以及完整未修改模板script+当前夹具的机械DOM/fetch状态保全。原始命令/exit/stdout在preflight，非HTTP、factory或浏览器，未运行PG、pytest、collection或CI；不重复旧三个Node或run41八图。提交前快照明确NOT_EXECUTED；真实postcommit gate随后另存并全文回报。
