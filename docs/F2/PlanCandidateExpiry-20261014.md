# 有界合成候选的期限与历史恢复

基线 `0d2be9f15be97aa0d381c0644e2f25b4917660dc`，源码 `0dc2135e2e885c3fac736fb08c22c7c7f343e3cd`。沿原产品§5.2、§7.3、§7.4和F2-T02，只为原注册合成候选的新采用增加固定15分钟服务端期限。provider继续关闭，无模型、付费调用、目录发布、Grant、迁移或部署。

生成使用原身份、来源与parent→dispatch→Case锁顺序，在授权等待后取PostgreSQL `clock_timestamp()`，保存版本2的UTC创建/截止时刻与900秒窗口；窗口与原保存文档互核。请求不接受客户端期限。同key同参读取同一候选，不续期、不追加；同key异参仍冲突。GET原key返回COMMITTED并可显示EXPIRED，过期不代表原生成未提交。

新的ADOPT核当前来源及窗口；最终授权复核之后、原计划与事件保存之前再次读取数据库墙钟，过期或时钟早于创建时刻拒绝并全回滚。验证摘要绑定固定窗口而不绑定不断变化的当前时刻，因此正常预览可被明确确认；实际POST仍重查时钟。

消费证明保存原accepted_at与期限，首ADOPT事件保存消费证明摘要。历史核对使用原accepted_at及原adoption_preview；当前时钟、后来的材料变化或方案替换不抹掉原成功事实。有效区间为[created_at, expires_at)，重算一个摘要不能使区间外的历史时间通过。候选过期不失效已采用方案，不释放预约，也不创建或执行业务动作。

V1候选无期限证明，实时候选显示LEGACY_REVALIDATION_REQUIRED，新的采用需明确生成当前V2候选。原V1记录、validator_version=1原摘要和已消费历史保持可读；不修改旧记录或凭空补期限。兼容验收在自有夹具中重建前一版本的确切持久格式，不宣称迁移了历史生产数据库。

原页面显示服务端期限、过期与时钟未核对状态，并说明只约束新采用；生成/采用丢响应仍仅GET原key，冷页重新认证，不自动重发。图比较只比较原注册步骤ID与实际依赖边：材料、目录或registry内容版本变化而闭包相同时明确显示未变化，仍要求来源重验。

开发窗13PASS和候选/API/原页扩展窗73PASS分别记录，不相加。真实PG锁等待验收对自有未消费夹具窗口一致老化，使真实数据库时钟跨越截止后释放parent锁，ADOPT409且全业务快照不变；这不等同等待生产15分钟。最终授权后过期、历史expiry/cold页使用明确时钟故障注入；原页面为完整HTML脚本NodeVM→实际ASGI→owned PG，不是浏览器渲染验收。

独审第一次错误指定仓库内basetemp，原创建票据检查拒绝`owned ephemeral test cluster directory evidence required`，28setup ERROR、exit1，产品断言均未执行。该次执行停止并保留原件；测试驱动修正为原默认系统临时目录的新自有夹具，继续原所有权与创建票据检查，不复用拒绝集群、不改检查/权限/凭据/TMPDIR。各执行结果独立列示。

浏览器历史拒绝及prepare Forbidden持续停止；浏览器、native Windows、全仓、真实/付费模型、生产迁移、部署、目录发布NOT RUN。本片不签收完整T02/AT07/AT14、通用DAG或真实履约。下一段接原同Case多目标总览的已采用方案来源追溯，实际办理仍由原角色从原入口明确执行。

冻结最终主测10模块 **341PASS、0FAIL/ERROR/SKIP、2WARN、222.469秒、exit0**；候选15项原页包含在341中，不另加总。514源文件首尾哈希无漂移。范围、模块和原件见[validation](evidence/plan-candidate-expiry-20261014/validation.json)、[export-index](evidence/plan-candidate-expiry-20261014/export-index.json)。

独审合法夹具首窗 **27PASS/1FAIL、0ERROR/SKIP、2WARN、20.503秒、exit1**：原ADOPT正文在持锁后才同步准备，准备GET被自身锁阻塞，返回无revision导致驱动KeyError，未启动ADOPT。修正请求在持锁前构建，产品源码不变；完整28项重新执行。原首setup拒绝和驱动FAIL均独立保全，公开导出只将四处夹具会话repr赋值行（preparation_fixture与f，各在log/XML一次）脱敏，保留错误正文、断言及状态，其余字节不改。

精确冻结独审最终 **28PASS、0FAIL/ERROR/SKIP、2WARN、18.091秒、exit0**，含10原创runtime API/PG、13明确复用期限测试和5原页面；不把首窗27+单例拼合，也不和根341相加。新的默认系统临时owned PG真实blocking_pid等待跨越截止后409，业务digest不变；514源前后无漂移，两原approval哈希不变。详见[独审原件](evidence/plan-candidate-expiry-20261014/independent/review.json)。

归档首审HOLD发现同一驱动失败展开另有f的Store tuple会话repr行。公开导出仅额外脱敏这两条log/XML赋值行，总计四条repr行；raw和其余字节不改。首审HOLD保留，最终复核另列。首个额外脱敏断言因XML使用转义尖括号而失败，未改raw；已按实际语法从raw重新生成两件导出与索引，错误保留。

最终[归档独审](evidence/plan-candidate-expiry-20261014/archive-review.final.json) PASS：49项精确哈希/字节与必要脱敏差异、全公开目录会话残留扫描、514源冻结通过。[首审HOLD](evidence/plan-candidate-expiry-20261014/archive-review.hold.json)原件保留；两审查原件在49项索引之外单独附上。浏览器与原创建票据等边界保持上述范围。
