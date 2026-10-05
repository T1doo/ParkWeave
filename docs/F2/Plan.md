# F2并行开发计划：本地资料准备与个人待办

## ENG016 当前本地切片：个人资料准备待办

实施前范围/依赖/状态表/验收冻结在 [ENG016-PersonalTasks.md](ENG016-PersonalTasks.md)。只读个人待办复用已落库的合成资料准备链，企业补交/确认、专员核对；不新增通知/资格/履约。仅项目内本地commit，不push/CI/恢复包/上传，旧备份授权不适用于本轮。下方ENG015/014保留历史。

## ENG015 历史本地增量：资料准备 UI 请求与草稿绑定

在恢复分支 `dev/f1-foundation` 的 `6ff160a` 上处理独立复现的页面响应竞态。请求绑定代次、身份、选中 Preparation/Case 与 revision；切事项清空材料/来源/说明草稿，刷新保留本事项草稿。切身份、列表、目录/New 和导航使旧请求失效；迟到写响应不得覆盖新选择或新编辑。后端角色/tenant/CAS/历史与真实履约边界保持。仅本地独立提交，暂不 push 或为此重跑 Windows CI；等待 run 37324704568 的失败子项后统一安排。验证与实际计数见 Log.md 的 ENG015 和 evidence/eng015-ui-race.json。F1 未签收、F2 正式准入 NOT_PASSED、R4 DISABLED、真实模型/预算 0。

以下 ENG014 计划保留为历史切片。

用户授权在GitHub/Windows阻塞期间继续本地功能开发。本计划是并行工程切片，不表示F1 PASS或正式F2准入；F1 IN_PROGRESS、真实模型链/Windows11门BLOCKED、R4未启用，完整35任务/36AT/6EX仍是待实现定义。原文设计与阶段门保留，F2完整PR0-alpha未交付。

来源：已归档完整ParkWeave V1产品§3、§5.1/5.3/5.5与开发计划§4 F2-T01/T04/T05/T07；本轮新建工程规格，不声称收到原验收包。原件与manifest逐字保留。只做一个无需资格条件的明确SYNTHETIC“企业资料整理”服务，目录/材料要求来自版本化合成夹具，候选资料是用户自述或文档摘录，不自动提升为真实权威证据。

## 切片与依赖

复用F1本地case.create真实PG/worker，Run成功后取得Case，企业显式选择资料准备服务；创建Preparation链接Case/Run。两个必需材料槽为诉求摘要与材料目录。企业按版本追加带来源的纯文本摘录；获派专员只能读其资料准备事项，做补正或当前快照人工核对；企业确认已核对资料包，或有理由重开。后续补件使旧核对失效，旧版本/审核/确认均保留。

使用现有本地API、低权限parkweave_app、PG事务/授权锁；新增显式F2 Grant与同园区/同企业获派范围，角色由后端身份确定。专员无全企业档案/Run执行权；企业不可代专员核对。写入同事务保留不可变事件/回执，刷新与进程重启读回。未知资格始终NOT_EVALUATED，外部受理NOT_SUBMITTED、线下履约NO_EVIDENCE；local preparation确认不关闭原Case。

无需新增模型/外部连接/付费服务/原生文件入口；文本资料不经过R4，不导入真实文件，不执行生成代码。目录/reviewer仅owner的显式合成setup可创建，应用无DDL或Grant修改权。UI仍服务/协同/资源：目录与入口、获派核对、资料来源/历史。无通用ServicePlan/资源预约/真实政策发布，本轮不扩其余F2任务。

## 冻结工程验收（不计整项AT PASS）

- P01：实际case.create/worker成功，链接Case，资料准备状态与Run/Case/外部状态分开；新输入不复用旧资料。
- P02：两个槽位完整、来源/版本清楚；未补齐不核对；专员补正→企业追加→专员核对→企业本地确认→重开有完整历史。
- P03：跨园区/企业/非owner、未获派专员、resource_admin/service_executor、角色伪造拒绝；当前Grant/身份撤销立即拒绝，专员不能读全企业facts。
- P04：幂等相同输入不重复、不同指纹冲突；乐观revision拒绝旧页核对/确认；并发补件/核对只基于完整当前快照；无资格自动通过。
- P05：失败事务不残留半资料/半事件，DB应用无历史UPDATE/DELETE；迁移重复/升级历史保持；重启读回。
- P06：Linux Chromium真实页面表单/双角色切换、补正/补件/核对/确认/重开、来源可见、320/390模拟窄屏和纯文本注入检查。Linux结果不当Windows通过。

测试规格见TestSpecification.md，真实失败/修复/NOT_RUN/BLOCKED见Log.md。阶段成果只本地安全commit，不访问被拒GitHub/Actions、不push/登录/改代理或权限；真实模型请求/预算0。成果结束时只更新一次私有Library恢复备份，含本轮commit及恢复说明。
