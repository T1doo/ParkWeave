# 双槽材料包确认：冻结源码独审

审查 SHA：`6187ed2cb933a26cf3d59b846178682e4f119745`。冻结源码及本次独立补充窗通过，未发现剩余源码阻断。完整模块回归、独测最终设计映射与独立归档门仍待完成，本报告不签整批交付通过。

本片只对已有 Case 的单个 P1 MANUAL 注记明确启用双槽材料包确认。诉求摘要仅作上下文确认；目录实际变化或已建立的原文承载义务采用冻结的精确行多重集规则，义务不能通过 summary-only 确认降级。MERGE 完整保全 M。确认不成为事实、资格、业务审核、采纳或核验，也不增加发布权限。

新 schema2 请求与 proof.version3 独立分派。旧 schema1 命令、指纹、v1/v2 历史解析、原行编译器及已有图/来源采纳/模板 carry 模块已与基线逐字或 AST 核对保持；新模式拒绝旧 ACCEPT/CONTINUE 降级，旧模式不追溯扩大。B/S 均由实际两槽材料及行 epoch 绑定，历史还核对原卡片前缀、实际计划端点和事件前的原 VERIFY/ADOPT 来源。新证明不把 raw 材料包摘要当作 P1 的 review 摘要。

UNKNOWN 返回当前计划步骤的完整受影响范围、空保留范围且无动作。当前角色、owner、READ/PREPARE、写入 EXECUTE、原 action grant、卡片代次及终态均沿原门检查。最终复读同时要求来源可用、原动作仍存在、能力严格为 true 和 basis 一致。P1 锁须原 UNLOCK；下游锁不由注记确认消除，原 ADOPT/VERIFY 保持原门与 64/128 记录预算。

UI 已核对 B/S/M 展示绑定、UNKNOWN 能力一致性、Unicode 与请求体上限、迟到/身份 ABA、当前 403 清私有视图、自发刷新失败释放 busy，以及原 tracked flow/opaque handle 的互斥和恢复。未知或泛化拒绝不清句柄；只有精确原请求的 definitive rejection 可释放本次登记。恢复仅 GET，不重发正文。

本次分层证据为：

| 层次 | 本次结果 | 范围 |
| --- | --- | --- |
| 真实 API/自有 PG 起点＋纯历史篡改 | 1 pytest PASS；37 项全部拒绝 | 损坏副本未写入 PG |
| 真实 API/PG 最终 UNKNOWN seam | 1 pytest PASS | basis 不变但最终不可用，409、无计划/账本写、冷 GET NOT_OBSERVED；并非真实时钟到期测试 |
| v3 与兼容 carry 组合 | 1 pytest PASS | 原五目标夹具：两次 carry、EDIT 后重新包确认、旧 key 精确回读；不冒六目标主路径 |
| 预算分支 | 1 pytest PASS；6 项纯检查 | 已知 basis stub，非 PG 64/128 端到端执行 |
| 提取函数 VM | 29 项通过 | 假 DTO/受控 transport，非真实浏览器 |

4 pytest 本次全部通过，pytest 报告 26.79 秒，进程计时 28.0899 秒。以上补充均不进入完整模块并集，未迁入旧 WIP 成绩。VM 原脚本的 WIP 标签保留，冻结运行由本次外层 SHA、提取来源与运行回执单独证明。

617 源码路径逐一与该 HEAD 的 Git blob 相等；15418 已跟踪文件与冻结清单及运行前后逐字相等；探针自身字节稳定。collection/JUnit 的四个完整路径和函数身份唯一精确，无参数归一化。唯一采集插件实际路径与 SHA 已记录，30 个自造会话仅登记在 0600 私有文件中。

测试范围已纠正为计划中的 97 个可运行完整模块，加 1 个真实浏览器模块 NOT_RUN；原 98 提案保全。项目 `.venv` 缺少 playwright，未安装、未收集、未启动浏览器，不能泛称整台机器均无该包。40 个字面设计不是 40 个 pytest；新独测 24 项仍待最终精确 SHA trace，本文不预签全部设计执行。Windows、正式 AT、真实产品模型/B0–B2、正式治理/现实履约与生产未执行。

机器可核对结论及引用摘要见 `source-review.json`；小窗结果见 `validation.json`，完整 collection/JUnit 对照见 `collection-junit-full-identity.json`。
