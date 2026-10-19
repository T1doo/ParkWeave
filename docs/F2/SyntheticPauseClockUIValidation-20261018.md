# 原页面受控合成停表闭环

基线`8cb957dfd3e546f6b24410a005c75a2cddfb211e`；最终受测`1373cd74b7a9ab775f707ad194e43a9ce6cd5a5b`；开发分支`dev/f2-synthetic-pause-clock-ui-20261018`。本片复用原HTML资料准备页面和已有显式合成能力，补齐按钮、历史与原键恢复；没有重做后端停表算法或开放正式provider。

## 用户可以怎样操作

前提是**当前临时合成服务实例已完整注入上一片IsolatedPauseClock及其原拥有证明、来源/日历、既有受派主体和有限能力**。页面不会生成这些能力；普通LOCAL_SYNTHETIC启动若没有该注入，仍不显示操作。并非拿普通REVIEW身份即可使用。

1. 在原页面填当前已有会话及原资料准备编号，点击原“读取已有资料准备记录”表单；仍按实际身份、目录和范围只读核对，不创建记录或批准。
2. 点击“只读核对办理期限”。只有原服务准确返回已有合成时钟标识时，出现“读取已绑定的合成时钟”；此时还没有读取新能力或发送操作。
3. 再点击该入口，核对当前事项、身份、资料版本、Case/Run、来源/日历和能力期限。owner只看历史；只有服务端给出明确有效合成写能力、完整当前投影的原受派专员能看到操作表单。
4. 填说明并单独勾选确认，分别点击“暂停合成时钟”或“结束合成暂停”。动作互斥，使用原key/fp/revision；每次POST后GET原key核对精确事件、指纹和历史。不代表现实园区SLA、Case结束或真实批准。
5. 响应未知时，原编号保留，点击“以原请求编号只读核对结果”。重开页面后重新认证、从同一原记录表单读回原事项，再显式GET核对。NOT_OBSERVED保持未决，不自动重发、换key或释放写门；COMMITTED精确历史可核时才结束原句柄，即使该事件已不是历史末尾。
6. 当前期限投影UNKNOWN始终无操作按钮；它不否定已合法提交的历史，原key证明完整时可只读核结。核结后如果继续原材料/审核流程，请点原“刷新当前事项”重算旧fieldset；本片不会自动推进或即时重绘全部旧表单。

界面明确标为LOCAL_SYNTHETIC、非现实SLA。已用秒、UTC/业务时区、当前期限和事件原编号均按实际响应展示；历史说明用textContent输出。浏览器只保留最多8份opaque事项ID/key/actor/revision及原请求fp，不存会话、说明或来源正文，不静默丢弃未知句柄。冷恢复证明的是原请求指纹、事件SHA和历史一致，不声称逐字比对未持久保存的原说明。

## 改动与保留的门

后端只增加`read`元数据actor、资料revision、原能力结束时间，并将`fixture_write_enabled`收窄到当前有效、可计算/暂停且Case可写的投影。原context、command、journal、events、projection、能力证明和日历计算不改。handling_deadline、API、权限/角色/schema/migration32/33、固定spec/bindings字节保持基线。

所有原业务写入口与新操作共用未决门。原记录冷重入例外仅忽略**精确已存pause事项ID的pause-stored这一项**；pause忙、其它原未决、实际entry GET认证及范围均保持。不把标记或句柄当作授权。切身份/事项及A→B→A作废旧回调；迟到成功或403不能清除新视图或核结原未决。

日历coverage结束与来源不足的后端拒绝原样，没有新增该范围动态节点或放宽未来日历。UI将当前可操作投影与已提交历史证明分开；UNKNOWN仅允许已授权的历史核对，不恢复期限、日历或停表权。

## 按窗口保留的实际证据

| 窗口 | 实际结果 |
|---|---|
| 初页面开发 | 1 FAIL，JUnit5.190秒。摘要适配先canonical又调用会canonical的旧工具，导致fp不匹配；实际PAUSE201、原key GET200，句柄保留，不能称零效果。完整失败日志/JUnit保留。专用HTML输出helper被第二开发窗复用过同目录，第一窗逐调用轨迹以原JUnit/log为准；以后按窗口分目录。 |
| 修指纹后开发 | 10 PASS，JUnit28.068秒。 |
| 追加既有历史推进/事项切换 | 2 PASS，10 deselected，JUnit10.841秒；不是完整12窗。 |
| 首冻结`e4c4f1a289668f711e0974948475726a91e96843` | 52 PASS/0FES，JUnit90.793秒；817输入四图一致，108记录模块全来自私有镜像。独审随后找到2个UI P2，所以此窗成功不表示无缺陷。 |
| 独审修补开发 | 12 PASS，JUnit33.066秒；开始/冷恢复改走真实原记录表单，并核对当前UNKNOWN下已COMMITTED的历史。 |
| 最终冻结`1373cd74b7a9ab775f707ad194e43a9ce6cd5a5b` | **52 PASS/0FES**，JUnit91.686秒：12个新页面节点＋35个原停表节点＋5个原只读兼容节点。817输入在共享目录/私有镜像运行前后四图一致，108个记录模块均来自镜像。 |
| 独审 | 先冻10条源盲oracle，最终SHA有限静审通过；2个P2闭合，无开放P1/P2。独立产品import、动态、DB/HTTP、锁、browser及文件写入均0。 |

两项P2：一是原key恢复被当前UNKNOWN投影挡住，二是原记录表单被新未决门自锁，初测试直接loadPreparation未覆盖该用户入口。旧源、52窗及静态发现保留，修补后才复核最终SHA。各窗不相加、不与上一片92 PASS或B/C历史数字累计。

证据目录：[发布清单](evidence/synthetic-pause-clock-ui-20261018/publication-files.json)、[最终JUnit](evidence/synthetic-pause-clock-ui-20261018/frozen-1373cd74/results.xml)、[最终collection](evidence/synthetic-pause-clock-ui-20261018/frozen-1373cd74/collection.json)、[根核对](evidence/synthetic-pause-clock-ui-20261018/root-verification.json)、[作者结构化转录的独审结论](evidence/synthetic-pause-clock-ui-20261018/independent-final-review.json)、[首失败](evidence/synthetic-pause-clock-ui-20261018/development.xml)及[首冻结P2](evidence/synthetic-pause-clock-ui-20261018/independent-e4c4-static-findings.json)。共228文件，含226组原始/导出hash配对与2份发布元数据；224组字节相同，2份初失败输出移除已知fixture会话显示，原始文件私下保全。两冻结窗捕获的456个精确fixture会话值均不在导出文件中；旧开发窗捕获不全，另移除六个已知fixture字典键的显示前缀/完整值。此检查不声称扫描所有未知凭据。残留4种43字符候选均与受测源码中的固定符号相同，未发现未分类候选，见[发布会话检查](evidence/synthetic-pause-clock-ui-20261018/session-publication-check.json)。

12个页面节点复用原ordinary_case_step_real_html.js的完整HTML机械DOM/HTTP驱动，连接真实拥有HTTP/PG；没有复制业务响应或新造权限。覆盖显式两次操作及owner只读、无能力隐藏、四种坏metadata拒绝、失响应冷GET、NOT_OBSERVED、身份/事项ABA、迟到成功/403、原事件后已有更新历史等。实际历史和14张业务/权限表的行值及日志条数由原fixture独立查询核对。

失响应、迟到403、未发送及当前UNKNOWN的相关分支是明确**传输/投影FAULT**，不冒称真实撤权、系统时钟或日历coverage故障。advanced-history沿已有实际原key及事件，只把客户端当前投影改为UNKNOWN来核UI只读证明；没有新增日历或clock时间条件。Node DOM不等于实际浏览器，未运行被拒的旧Chromium/风险窗口。

## 剩余软件与真实输入

本片完成的是已有临时显式能力实例的原页面接入。**普通持久停表provider、真实授权来源适配及真实规则消费接线尚未实现**；并非只差凭据。普通configured_app和未注入该能力的LocalDemo仍无停表入口，不能拿fixture批准替代正式权威。

若推进真实运行，仍需其既有停表主体/用途/理由/事项范围及结束撤销语义，合法政策/日历/时区/起算目标，和实际来源合同/版本/样本/关联/撤销机制；按现有信任机制实现适配，不要求创造新Grant或信任根。普通已有preparation读取仍需合法PREPARE/REVIEW_ASSIGNED与精确preparation_catalog，不足继续准确拒绝。

未验真实Windows11、本机PG/test-owner及已审native回执/ACL条件，未验实际浏览器、正式AT29/33、真实园区SLA或真实业务效果。未调用真实模型、部署、改main/强推、增加费用或安全网络权限。旧风险窗和HTTP UNKNOWN_OPEN未重试/关闭；项目未完成。最终交付SHA与远端差异另以Git回执核对。
