# ENG092：有界依赖规划预览与精确同步

本轮已核实原 origin 的 dev/f1-foundation 为 797f426dc2f6274a973a82bb7909dc5d820b8f79，确认祖先关系后仅普通 push 九个已验证提交至 e03dbf78c4b1daeafbd93cd7b6dc50ba9d923ecb，并再次读取精确远端 SHA。默认沙箱首次连接代理失败，正式获批的同一网络/代理/身份调用成功；没有更换策略或凭据。唯一现有 Windows Server engineering run [37593296690](https://github.com/T1doo/ParkWeave/actions/runs/37593296690)，attempt 1、精确 e03dbf7、completed/success。只读 run 元数据，未获取日志、artifacts 或直接测量 JSON，未 rerun。此独立 Job 成功不代表完整 Windows 工程或 Win11 验收。

## 本地规划切片

读取原 V1 §5.2 和 F2 T02/AT07/AT14 后，新增确定性注册适配器依赖闭包预览：全部已保存必需目标参与映射，按目标选出 1–5 步，而非始终四步。注册表限制 16 项，拒绝循环、未知依赖、未支持适配器/版本及重复步骤；客户端不能提交任意 DAG。未知、未支持、缺少可信合成目录来源的目标保留为 UNKNOWN/UNSUPPORTED，不能通过删目标换取覆盖。

每步分别给出请求所属服务/版本、实际适配器/合同版本、当前输入、现有 HTTP 动作路径/角色/命令、责任、前置、产出、验收、补正入口及当前缺口。P5 使用既有本地生命周期入口，包含 REVALIDATE、CLOSE_LOCAL_RECORD、REOPEN。这只是注册子图的工程预览，未创建通用 CaseStep、执行器或新业务状态。

所属 enterprise_operator 的现有 READ/PREPARE 可读；保存还要求现有 EXECUTE，同 Case/Run/owner/tenant/SYNTHETIC 和当前权限独立校验。migration021 只给既有 preparations 增加 nullable、最多 16 条的 planning_previews JSONB；没有新表、SQL GRANT、角色或 assignment。package-data 同时补齐遗漏的 migration019/020/021，避免安装包缺迁移。迁移仅在本轮隔离测试数据库应用，未部署。

保存请求严格绑定资料 revision 和服务端 SHA。源包含原诉求/全部目标、目录版本与来源、注册步骤/动作、材料/资源/接单/回执事实、已有资源授权及 Run 授权、Case 状态和生命周期 revision/cycle/state/verified SHA。来源变化使历史显示 STALE；旧 SHA 的首次保存 409。同 actor/key 已提交的同指纹重试在 CAS 前恢复历史，来源已变也只返回 STALE 旧记录，不新增、不执行。跨 Case 或改变请求复用 key 拒绝。CURRENT 仅表示当前输入 SHA 匹配；若事实精确恢复也可重新匹配，不能解释为已批准或可执行。

页面目标按钮只向待保存原诉求添加显式目标。刷新、编辑、Case/身份切换与迟到响应隔离清空旧预览；观察到 403 清整个私有计划。持久化历史可重新读取。既有四步执行合同与覆盖门独立保留；新增 COVERED_PREVIEW_ONLY 不启用旧计划、不替用户确认或授予权限。该 JSONB 是规划元数据，不能据此宣称 AT14 的完整预览执行隔离已实现。

## 验证与剩余范围

最终完整 Linux 回归 1612 PASS / 0 FAIL / 9 原生 SKIP / 2 WARN，331.76 秒；231 源文件冻结差异 0。相关回归 44 PASS，旧库升级相关 14 PASS；最初未来版本夹具重用了真实版本21导致1项失败，改为22后完整重跑通过。浏览器1 PASS。231 源文件冻结 SHA、浏览器与独立复核详见 [证据](evidence/eng092-bounded-planning-sync.json)。真实缓存 Chromium 使用新隔离合成 PG/API/web Case 6593e3f0-ff70-4039-9b36-e7be4091c2dc：1 步目标、5 步闭包、外部目标不省略、持久化刷新、历史失效、403 与迟到响应隔离均通过；1200/390/320 无横溢。资料诉求及规划元数据会变化，权限行逐项不变，未创建 assignment、controlled plan、dispatch 或 resource hold；自有服务已停止，原演示 PG 未启动。

T02 进展限于离线确定性注册子图，仍缺正式服务目录、模型规划、通用分支/并行计划及完整 AT07；AT14 完整执行隔离仍未验收。T01 真实性/跨材料冲突/授权复用、T03 正式规则与 Approval/ServicePlan 全组合绑定、T04 通用步骤交接/合法新 Run 实际授权/真实履约、T05 全链 outbox 与未知结果核对、T06 正式参数化发布及无 fixture 权限冷输入、T07 同一新 Case 完整 V1 用户签收仍缺。历史局部证据不能拼成完整冷启动验收。

本轮新增源码只做单独本地提交，不第二次 push。真实生产目标未知，激活关闭；F1 未签收、F2 并行探索，Server 非 Win11，R4 关闭，模型调用/预算 0。原环境与备份保留。
