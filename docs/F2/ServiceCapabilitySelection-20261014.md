# 受信能力目录、紧凑选择与第二园区本地成果

承接基线 `7227f5ac320c9a6d481fa50efa025fc158facbb9`。最终源码（含包清单）冻结于 `31d98d1ee4be407aa3af2a5c737fd1d2bd75c6c7`，548个源码/测试/脚本文件；最终门禁及Git交付核对在下文单列，不合计不同测试窗口。

实现原产品§§6.1–6.3、7.5、8所需的有限纵向切片：三个受信合成服务能力、独立园区配置、紧凑声明式选择、服务端重建、原候选明确采用及实际原P1–P5本地成果。原prep/Intake/TemplateDraft单建单服务Literal保留；没有任意service_id、脚本、适配器、Grant或执行器注入。不是完整F2-T02/T06、F3-T05、AT或PR0签收。

ServiceRelease绑定稳定release/revision/hash、六个有限本地目标的合法子集、已有adapter@revision及依赖、材料/资源/责任/产物/核验条件，以及原审核来源和有效期。ParkInstance独立绑定精确release/hash和config revision/hash，仅配置该园区已有角色、资源及新输入字段映射。原TemplateEngine当前审阅/发布head、source、registry和有效期提供权威；自己重算hash不构成审阅。

独立oracle穷举最小合法服务组合，保留UNKNOWN、UNSUPPORTED和硬条件；完整来源集合指纹包含未选、撤回及跨园区可移植来源journal。唯一合法解如实显示，同图不同来源只统计绑定变体。模型仅在exact MockTransport/原离线usage预算边界内返回六字段版本引用；不再回显完整固定P1–P5期望JSON。V4保存原响应、原key、预算、900秒窗口及冻结证明，服务端重新核合法性和重建步骤；明确原ADOPT在当前授权、来源和期限下同事务保存原计划及事件。V1–V3历史公式及默认路径保持，V4不得剥离证明退回旧版本。

原模板持久SQLite发布租约只围住短PG保存/采用事务，模型等待不持PG/业务/来源锁。集合写与资源锁遵循实际原业务顺序；已用PG_BLOCKING_PIDS观察真实等待和赢方重核。033保护journal前缀、scope、DELETE和TRUNCATE，并拒覆盖篡改retained函数/trigger。普通`Store.migrate()`完整保留032；只有显式`migrate_service_capability_fixture()`在同原迁移锁、genuine Linux自有创建票据和同事务下安装/修复033。构造器不安装，应用身份及native创建票据不能申请此扩展；原默认/native前置不被隐式升级。

新冷输入facade只准备原业务请求体和不可变原key，不代发、不重发、不自动采用。用户明确调用原Case/材料/诉求入口；丢响应只GET核对，NOT_OBSERVED不证明未提交。原页面展示所选Release/config精确版本及映射，单独确认后复用原ADOPT和持久恢复；未知、坏状态、撤权和迟到响应均阻止继续写。已COMMITTED但资料版本已变的历史候选，经严格核对原subject/key及冻结引用后，只清除原恢复句柄、保持不可采用；不会因当前版本不同而永久卡住原key，也不会自动重新生成。既有有权冷读保留，不因今日来源或registry失效改写旧计划证明。

第二园区测试以一个实际完整A本地成果Case作为已有历史前置，再用B的新材料、不同原有人员、两项独立B资源、新Run/Case/分派/回执/重验，执行新三能力链；A材料、完整历史和结果响应字节保持。A旧链只作隔离前置，不冒充本批B新功能。每个双园区全链场景的额外owned fixture种子：资源权限4条，A/B执行者Run分派各1条、共2条；该场景B测量边界后的权限/分派表变化0。这不是全部测试夹具的累计数。实际成果仅LOCAL_OUTPUTS_VERIFIED，Run技术SUCCEEDED不等于原目标完成、正式审批或真实履约。

验证窗口分别记录：

| 窗口 | 来源 | 实际结果 |
|---|---|---|
| 主回归 `final-permitted` | 行为源码50d34b8a535016fc3fe3bcf0c5f2a9c820b49122；包清单7410ada3eef76c9fd8d04f29794f0976c09a88f7 | 1462 PASS，0 FAIL/ERROR/SKIP，2 WARN，631.08秒，548文件零漂移 |
| 独审 `frozen-77` | 上述行为源码，69个实际加载模块均来自独立镜像 | 77 PASS，0 FAIL/ERROR/SKIP，2 WARN，42.23秒，550文件零漂移（含2个独审探针） |
| 最终主回归 `final-source-31d98d1` | 最终31d98d1源码；同46个获准模块 | 1476 PASS，0 FAIL/ERROR/SKIP，2 WARN，635.95秒，548文件零漂移 |
| 最终独审 `frozen-91` | 最终31d98d1源码，69个实际加载模块均来自私树 | 91 PASS，0 FAIL/ERROR/SKIP，2 WARN，38.77秒；550文件（root548+独审2）零漂移 |
| 最终离线包 `frozen-wheel-31d` | 最终31d98d1源码与包清单 | PASS，exit0；152个package文件与源逐字节一致，缺失/多余/改变0 |

最终wheel SHA256：`5c1e8a7005a581fb1ec46ca833c3b9e3c213683263854ddab314b6a2adabb255`。其中migration-033 SHA256：`a3dd64f31acef4aaa04bc7b31d8b6085dcc5c4dbac047e2906c41135c6a10b41`，web SHA256：`54367ccb25339d9a297ce4431751b79ec276762b0bf430180eb70d408edf04de`。

早期真实失败全部原样保留，包括PG不可变历史旁路、资源UUID锁别名、历史冻结证明、页面历史恢复首红，以及测试接线/过度断言失败；不同归因在各handoff记录。第一次主门清单误含历史浏览器模块，因缺少Playwright发生1个collection ERROR、exit2，未执行测试、未启动浏览器。该模块随后明确NOT RUN，不安装或重试。包全文件核对第一次发现既有两文件未打包，FAIL已保留；仅补齐原fault-schema.sql和template_upgrade_web.html包清单。

封存518个原件导出，root逐字节、长度、hash及安全路径核对PASS，无替换或未索引文件。最后独立归档审核在命令启动前遇到工具基础设施断连，单独标NOT RUN，完整工具报错见[归档核对回执](ServiceCapabilitySelectionArchiveAudit-20261014.json)；没有重试该动作，也不把root核对冒称独审。此前91项源码独审与152文件wheel核对已实际完成，不受影响。

原始PASS/FAIL/ERROR/SKIP、日志/XML/exit、来源manifest、PG等待及页面traffic在[证据索引](evidence/service-capability-selection-20261014/export-index.json)；失败原件不覆盖、不把修测试接线错误记成产品失败，也不抹掉产品缺陷首红。

实际发现并修复：迁移函数正文/retained标记、runtime schema完整检查、资料映射状态键、撤权与资源引用、完整来源集合、DELETE/TRUNCATE历史旁路、UUID SQL等价写法造成锁别名、冻结目标覆盖/oracle证明、旧候选不应租新来源、当前registry失效时原计划历史页退化读取、前端误将PlanID收窄成UUID、V4安全失败码及精确所选版本展示。模型响应已取得但来源变更、最终候选未提交时明确FAILED_SAFE/SOURCE_OR_ATTEMPT_CHANGED；TIMEOUT/transport仍UNKNOWN。同key只返原尝试，不再调用模型。

源码与报告diff空白检查exit0；归档保留原pytest失败输出的尾部空白，全归档diff检查实际exit2，不改写原证据。交付只正常推送`dev/f2-worklist-entry-isolation-20261013`；交付后核对本地HEAD、tracking及直接远端SHA一致，71个远端分支中其余70个与开工快照一致，main/F1/原F2保持原SHA。最终交付提交SHA由推送后回执及本轮答复给出；交付提交与上述冻结源码的src/tests/scripts/pyproject差异须为0。

真实provider/凭据读取、LIVE/执行网关、真实服务目录业务发布、生产迁移/部署、权限扩大、真实业务/运行期新增registry或Grant、强推及主线修改均为0；上述owned fixture初始化另计。Chromium渲染浏览器NOT RUN：保留历史`data:`导航`ERR_BLOCKED_BY_ADMINISTRATOR`拒绝，本批不启动或换工具重试。历史prepare Forbidden不重试；两审批文件保持false/null及原hash。native Windows、完整PR0和真实园区正式投用NOT RUN。

下一步在另行授权的真实园区治理范围中完成正式目录审核发布、实际园区原有映射核验及原生环境验收；本批只交付默认关闭、可复核的owned synthetic开发链。
