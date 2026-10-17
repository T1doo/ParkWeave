# 获派专员相对最近审核的材料差异复核

基线 `5a1771aa337b00c4366c46a40752d1442e8ebf22`；冻结源码 `0c6e060b9661797b9bce0d1280274d3769b264ed`；开发分支 `dev/f2-specialist-material-review-20261017`。父独审对5a1771aa仅有限准入215唯一/23新增证据、五个变更文件及合成本地原链；不声称父审重哈全部221归档对。

## 用户路径与范围

企业既有差异面板只比较未提交候选与当前同槽材料，专员不可见；专员原材料历史平铺、补正请求时基线及resolution均不是最近一次已审核完整资料包与本次补正的差异。先排除重复：原双槽部分提交已保持CHANGES_REQUESTED和原待办，本片不重做它。

当前合法获派专员沿普通启动读取原事项，点击“只读核对上次审核与当前材料差异”，逐槽查看最近REVIEW所对应的完整旧正文和当前已保存正文、材料ID/版本、正文hash、来源类型/标签以及当前补正理由。正文相同、来源变化、新ID/版本分别显示。人工仍沿原REVIEW判断当前完整资料包，再由企业独立CONFIRM；比较不自动确认补正充分、采纳事实或执行审核。企业比较不能代替专员审核。

[产品设计](../sources/V1/平台产品设计%20(2).md)106、131、185–187、284行及[原开发计划](../sources/V1/分阶段开发计划%20(2).md)F2-T01/T04、F3-T01/T03为范围依据；原文没有逐字规定此diff UI。[实施合同](SpecialistMaterialReviewContract-20261017.md)保留等价入口排除和边界。

## 绑定与安全边界

原REVIEW事件只保存整包snapshot，通用历史不含旧材料UUID。新增可选GET `/api/preparations/{id}/material-review-comparison` 在原READ/REVIEW_ASSIGNED、park/org、原prep/Case/Run、精确合成目录和当前reviewer授权内读取；复用原scoped父SHARE锁和原八字段snapshot算法。最多64历史材料、1024双槽组合，必须唯一匹配最近REVIEW。无REVIEW明确首次审核；最新事件损坏、匹配不唯一或无法恢复时明确不可比较，无旧正文，不退回更早审核、不猜时间/上一版/补正请求基线、不修改历史。

投影绑定当前原专员、prep/Case/Run/service版本、revision/当前snapshot、最近审核事件/历史actor/旧snapshot与两槽材料UUID/version/正文/来源及投影hash。正文SHA是所存UTF8正文的hash，不是原文件字节hash，不证明真实性。历史审核人不构成当前读取授权。

浏览器每次entry→新GET→原material-corrections→第二新GET完整相等→末entry。所有await后复验会话代际、角色和原上下文/在途/UNKNOWN门。原主体、READ/REVIEW_ASSIGNED、父分派和精确目录的既有revision/xmin只形成opaque reader_source_sha256，不输出权限明细；检测两个观察点间的同值恢复/ABA，不是永久身份、防篡改证明或全期间原子保证。当前403清私有，迟到旧200/403不能覆盖新上下文；原UNKNOWN/key/草稿不因旧读重写。无新localStorage或恢复句柄。原写流结束后只重绘新只读按钮；原REVIEW/CONFIRM和CAS不新增门。

复用已有逐行字面差异函数，250000单元预算超出时仍显示两份全文；CR明确转义、文本渲染。复用原snapshot和差异算法，无新业务POST、表/迁移、权限模型、真实身份/Grant/分派/目录发布或批准；NativeRunAccess默认拒绝和IsolatedPlanApproval隔离边界保持。

## 实际验证

同一冻结的12个完整相关模块 **267唯一项PASS，0FAIL/ERROR/SKIP**，JUnit 1350.626秒；新增52项含在总数。732个源码/测试/脚本/配置输入零漂移。独审限定范围与命令/输出来源见[独审记录](evidence/specialist-material-review-20261017/independent-review.json)；独立内存探针不加进pytest数量，也不是实际HTTP/browser。

| 完整相关模块 | 唯一项 |
| --- | ---: |
| tests/test_material_review_comparison.py | 30 |
| tests/test_material_review_comparison_browser.py | 22 |
| tests/test_material_version_compare_browser.py | 23 |
| tests/test_preparation.py | 35 |
| tests/test_material_corrections.py | 33 |
| tests/test_material_file_import.py | 68 |
| tests/test_material_file_import_browser.py | 6 |
| tests/test_material_csv_newlines.py | 10 |
| tests/test_native_preparation_entry.py | 16 |
| tests/test_native_preparation_entry_browser.py | 5 |
| tests/test_preparation_command_recovery.py | 11 |
| tests/test_readiness_checklist.py | 8 |

普通configured_app独立进程、Chromium和隔离PG实测：企业文件候选比较→原ADD v3→专员精确看上次REVIEW v1（不是请求时v2）与当前v3→原独立REVIEW→企业CONFIRM→进程重启专员GET-only读回；读取前后业务表/授权值不变。1200/390/320px无横溢、脚本文字纯文本、CR/CRLF及大行数全文、同正文新记录/独立来源变化覆盖。实际当前撤权/改派与在途撤权/改派拒绝，READ/REVIEW_ASSIGNED/分派/目录同值恢复丢弃旧投影，迟到200/403与身份/Case ABA隔离；已提交却丢回复的原REVIEW UNKNOWN及当前403清理均覆盖。原企业比较、材料导入/CSV保真、原准备/补正/入口/恢复/准备度完整相关模块一并重跑。

冻结前原257项计划原件保留；为同值恢复/ABA新增4个API和6个浏览器节点后，精确冻结收集为267项，未移除原节点。[收集变化](evidence/specialist-material-review-20261017/collection-evolution.json)逐项列出，不在运行结束后删减集合。

各开发窗不相加，原日志、JUnit、调用与当时源码快照保留：

| 窗口 | PASS | FAIL | ERROR | SKIP | JUnit秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev-api-v1 | 26 | 0 | 0 | 0 | 35.02 |
| dev-browser-v2 | 15 | 1 | 0 | 0 | 205.92 |
| edge-v3 | 52 | 0 | 0 | 0 | 320.377 |
| final-v1 | 267 | 0 | 0 | 0 | 1350.626 |

独审Python首次因harness未注入hashlib而exit1；Node首次为functions编排层模板ReferenceError，未调用exec_command、未启动Node且无Node进程退出码。两者仅修harness，最终A/B各exit0；命令/stdout由审查者报告后根转录，根未复跑，不冒称原始capture。Node最终clearPreparation及sendPrepCommand是spy/stub，不作为实际清理或业务写入成功的证据。

原dev-browser-v2唯一失败为测试期待“已变化”，实际原补正guard已正确拒绝“不匹配”；修正断言，不放宽产品guard。静审P2为原写流结束后按钮未重绘，补充释放后只读重绘，原REVIEW/REQUEST_CHANGES实际恢复通过。新epoch/第二GET在后续窗口覆盖；不把早期WIP成绩迁到冻结。[失败账](evidence/specialist-material-review-20261017/failure-ledger.json)记录更正和每窗范围。

首份封存因根提前启动导出，漏收最终验证JSON与交付前状态快照；补充必需记录检查退出1并拦下交付。已复制211对当时文件与原件一致，整个首份目录原字节保存在私有`.runtime/specialist-material-review-export-v1`。待两进程均exit0后顺序重新封存，强制核对最终记录完整、所有当前原件/公开件指纹和267项身份；不重跑或改写已通过测试。[首轮封存失败](evidence/specialist-material-review-20261017/export-attempt-v1.json)与失败账保留原因。

## 运行缺少的输入与未验范围

| 层次 | 必须已有的合法输入或尚缺实现 |
| --- | --- |
| 当前普通合成事项 | 当前合法会话/active主体；本人owner READ/PREPARE或原获派专员READ/REVIEW_ASSIGNED；原preparation/Case/Run稳定ID及关联、park/org、service精确版本与合法preparation_catalog；读取专员必须等于当前reviewer。原业务追加/REVIEW/CONFIRM仍需原EXECUTE等授权、当前revision/key与完整双槽。 |
| 精确历史比较 | 最近原REVIEW事件及其原snapshot、原材料UUID/version/全文/来源/正文hash。缺失、超过有界历史或不唯一只给不可核实，不补造旧版。 |
| 真实材料与来源 | 合法有权使用的新旧正文、来源ID/修订/hash/版本关系与用途授权；正式材料要求与实际审核主体；source_domain/source_id、四对象稳定ID/类型/关联、owner/reviewer与park/org；preparation/plan revision、service精确版本、source_revision_sha256及规范化协议；当前head/撤销协议、合法主体映射及独立可信证明。 |
| 正式产品与宿主 | 获准只读host/backend、具体来源FormalSourceReader/IndependentProvenanceVerifier和独立绑定/当前性核验、既有方案/资源批准映射。configured_app provider注入仍不完整，仅配置对象不能成功；NativeRunAccess默认拒绝permit/writer。IsolatedPlanApproval、测试签名和本片hash均不能作为正式批准。 |
| Windows正式AT | Windows11 x64精确build、原生独立PG和本机应用角色配置、合法真实来源与原批准/分派、正式AT场景/预期及证据采集环境；本轮只有Linux隔离工程证据。 |

无合法PREPARE/REVIEW_ASSIGNED/精确目录准确拒绝。详见[正式来源](FormalPreparationEntry-20261017.md)、[普通入口](OrdinaryPreparationEntry-20261017.md)、[资源批准读取](ResourcePlanApprovalRead-20261017.md)。Windows原生正式AT、真实园区/企业业务和现实履约、生产host正向来源接线、真实模型、部署及全项目验收均未执行。SYNTHETIC仅证明本地工程路径；qualification NOT_EVALUATED、external NOT_SUBMITTED、offline NO_EVIDENCE、case_goal_completed=false。完整项目未完成。

## 证据与交付

[普通进程与重启证明](evidence/specialist-material-review-20261017/browser/final-v1/test_ordinary_owner_corrects_s0/proof.json)、[320px实际截图](evidence/specialist-material-review-20261017/browser/final-v1/test_ordinary_owner_corrects_s0/specialist-review-320.png)、[390px截图](evidence/specialist-material-review-20261017/browser/final-v1/test_ordinary_owner_corrects_s0/specialist-review-390.png)。截图为面板上部视口；完整正文由实际浏览器断言核对。

[最终gate](evidence/specialist-material-review-20261017/gate.json)、[最终JUnit](evidence/specialist-material-review-20261017/final-v1.xml)、[最终日志](evidence/specialist-material-review-20261017/final-v1.log)、[冻结清单](evidence/specialist-material-review-20261017/freeze.json)、[原件/公开件hash对](evidence/specialist-material-review-20261017/public-pairs.json)。公开件仅处理临时合成session字符串值，JSON键、JUnit身份和远端引用保留；原件与失败不覆写。

根线程逐项核对继承28905个F2文档/证据Git blob零变化，与父审有限准入分开。本轮公开215对将在实际推送后重新hash、严格解析JSON/XML/PNG，实际交付SHA/远端0/0/clean仅在正常开发分支推送后记私有delivery-verification.json和最终回复；不预填成功。不改main、不强推、不部署、不调用真实模型、不新增费用/凭据/安全网络权限、不查询已拒绝Actions、不删未知锁进程。

[重封存逐对核对记录](SpecialistMaterialReviewPostExport-20261017.json)：215对原件/公开件hash一致，最终验证记录完整，30 JSON/4 XML/20 PNG解析通过。首份未采用封存完整保全；本次不迁移或叠加测试成绩。

全暂存区空白检查返回2，6处均为新归档证据；日志、JUnit、patch及旧源码快照原字节保留。冻结源码/测试/合同与本次编写文档检查均为0。文档链接校验首试误拆V1文件名括号，仅修正validator后全部19个目标存在；未改产品。[文档与空白检查记录](SpecialistMaterialReviewDeliveryChecks-20261017.json)。
