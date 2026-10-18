# AT22 有限接口验收与 AT23 已有证据复用

本片先按原固定 oracle 排重，产品 `src` 完全不改。只在原 `test_synthetic_rule_readiness_api.py` 增加一个业务节点，并更新原 ATBindings 的工程定位；没有新模块、权限或验收框架。新增覆盖为正常 ASGI 路由上的地区、指定业务时点、候选版本与历史组合，不把旧组件成绩重新累计。

业务冻结为 `3c0ba9bb816b270116ddcca771829443dac6dd1e`；最终绑定冻结为 `b232570e7f48a12d0b4747a664009bdb74066f4c`，后者只删除 AT23 中不可在本轮复跑的旧浏览器 selector。两者 `src` tree 均为 `e5b11851af710b6dd620ec61b22851c2852cb509`，`tests` tree 均为 `9cfbb4a9988aa0caf575957ae0f823fd71cdaec6`。768个选定输入跨版本唯一差异为 ATBindings。全42项 `whole_status` 和固定规格保持 NOT_RUN。

## AT22 实际新增覆盖

使用原自有临时 PostgreSQL fixture、原 candidate/journal SQLite 工具及两个原 FastAPI TestClient。SYNTHETIC 初态和 Mock REVIEW/PUBLISH 与真实治理分开；这是进程内实际路由，不是浏览器或外部HTTP服务。业务日期是显式 `as_of`，没有用等待真实到期代替。

| 原 oracle | 实际有限结果 |
| --- | --- |
| 不混用地区或失效版本 | 原 REGION_A/v1 得 TRUE；模拟配置改 REGION_B 得 UNKNOWN/REGION_NOT_APPLICABLE。业务日期早于 source 开始一秒、恰到 source 截止均得 UNKNOWN/EXPIRED_OR_NOT_YET_VALID_SOURCE；Mock 当前权限区间未先到期。 |
| 未审核候选不直接用于承诺 | 经原候选HTTP命令 SAVE/SUBMIT/REVIEW/PUBLISH，逐步核 DRAFT/REVIEW_REQUESTED/REVIEWED/PUBLISHED、可用性及release数量。前三阶段不出现v2 release；旧binding在四阶段均拒作当前规则。全程 formal_review/business_publication=false、资格UNKNOWN/NOT_EVALUATED。 |
| 历史按当时规则留存 | 用原精确模拟适配器构造器与同journal显式更新 RuleBinding/epoch，实际v2比较值17→3后得FALSE。原键GET仍返回原v1 TRUE及原receipt SHA，当前truth另列UNKNOWN；当前v2与历史原结果分开。 |

场景JSON保留9个读取阶段。原authority/business/preparation_records/assertions四组快照逐阶段及最终相等；它们不是全库快照，不含runs/operations/controlled_plans/preparation_catalog等全部表。允许的场景写入单列为候选SQLite事件/release及两个simulation评估。原临时fixture初始化本身包括合成身份、角色、GRANT、资料与原API前置；不把初始化算作GET-only，不产生持久真实授权。

## AT23 排重后未重跑

实读4份原JUnit并核SHA，共定位13条历史PASS记录：其中6条说明AT22旧适配器/原API范围，另外7条覆盖材料缺槽、无已选事实时不生成草稿、仅已选自述生成UNVERIFIED正文、缺目录REVIEW拒绝、独立人工REVIEW/CONFIRM后仍非资格批准，以及实际文本下载/未分享事实隔离。这些是各历史冻结成绩，本轮新增测试数为0，不转签当前源码或组合为一个新全链PASS。

来源见本片[历史证据清单](evidence/at22-23-finite-20261018/root/reused-historical-evidence.json)；原 [材料草稿](MaterialPreparationBrief.md)、[清单](ConditionMaterialChecklist.md)、[文本包](MaterialPreparationTextPack.md)及原XML不修改。AT23工程绑定只保留3个已有API/PG节点；旧浏览器下载仅作历史引用，未执行其浏览器fixture。真实资质、财务、签章、正式材料要求和真实性审核均未验证。

## 实际窗口与独审

| 窗口 | 实际结果 |
| --- | --- |
| 根3c0首窗 | 收集ERROR，实际0tests/0PG；私有启动器遗漏mirror根目录导致scripts导入失败。原日志保留，补正常模块路径。 |
| 根3c0第二窗 | 静态1PASS、业务1SETUP ERROR，业务call为0；启动器把PG basetemp放工作区，原临时目录证明门正确拒绝。改回原支持的/tmp范围，保护门未改。自有PG已退出、data已删。 |
| 根3c0有效窗 | 2PASS/0FES，pytest11.93秒、outer15.220270409秒：新增业务1＋因绑定改动必要复验的原静态1。 |
| 独3c0有效窗 | 同2个实际ID均PASS/0FES，pytest13.34秒、outer17.847486276秒；与根重叠2，不相加。 |
| 根b232补窗 | 实际再次执行同2节点并PASS/0FES；调用遗漏static-only参数造成额外重复业务执行，按真实nodes记录，不按目录名binding-only推断范围，不增加覆盖。 |
| 独b232补窗 | 仅精确静态绑定1节点PASS/0FES，pytest0.24秒、outer3.893125670秒；业务0、未请求PG。不把3c0业务成绩转签b232。 |

各有效窗768输入PRE/POST无漂移。根记录的103个选定项目模块、独记录的105个本地模块origin/hash与各自镜像相符；动态按路径加载的run_acceptance未作为常驻模块单独仪表，范围依原mirror相对loader。独审开放业务P1/P2为0。根/独自有测试均退出，创建的临时PG均退出为Z且data删除；Z条目待PID1回收，未操作未知进程或锁。

独审业务报告SHA256为 `b87fbb5e9d0cef9f9c2ff7cb582036da5c0b764a4c6746617f3ce7702aeee1e4`；最终绑定补审为 `221e463be78752a8ce35b7c299e7d0d0fff7f9bd14e4bdfedeb091072aeec93a`。原日志、JUnit、调用、输入摘要及分窗对账归档；不发布私有PG日志、PGdata、SQLite或凭据。

本片未再次执行已知受source_bytes门拒绝的通用runner，也未改其上限/绑定算法；定向pytest不能冒充whole_AT_EX。未启动root host、操作sealed FD、发行普通policy/key、真实安装、真实模型或浏览器；Windows正式AT、真实来源业务、现实履约、全部固定AT及完整项目仍未完成。发行/运行分支保持阻塞，其他原计划允许的有限合成用例仍可分别推进。
