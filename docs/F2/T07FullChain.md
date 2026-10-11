# 原 F2-T07 有限整链工程验收

本轮实际完成同一新合成 Case 的新诉求、补件/核对、注册五目标规划、两个资源的组合占用与关联、本人接单、人工本地回执、企业明确 ACK/P1–P5 VERIFY、拒单重派、回执补正/反馈及本地关闭重开。普通生产 API 与独立 CLI worker 实际写入自有 PostgreSQL；新普通 API 子进程实际冷读。人工动作由合成测试驱动，不称自然人试点、真实模型办理或线下履约。

冻结验收源码 `b5ea90ac9b366b015b43c426ad94b72faf7c8b72`；406 文件清单 SHA `fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf`。原405源码零变，本轮新增整链测试与实施前合同，无生产功能补丁。根39模块完整窗口实际 1570 PASS / 0 FAIL / 0 ERROR / 1 SKIP，exit0、1523.631秒、JUnit 1521.392秒；另一个同SHA目标产物完整PG专项窗口 44 PASS / 0 FAIL / 0 ERROR / 0 SKIP，exit0、65.906秒。两窗口ID不重叠，共40模块、1615 unique IDs，1614 PASS与1 SKIP；不称一个40模块单进程窗口。原1561 IDs无缺失，新整链10 IDs另列。唯一旧SKIP是Windows原生文件后端门，本轮Linux不转签Windows。

A场景从零Run/Case、正常新Run走到资料/计划/资源，实际默认访问批准关闭、新Run无执行者assignment，分派403且业务/权限不变；目标不完成。B场景以原fixture owner-only assign_status作为**业务链之外明确合成管理前提**，仅新增指定Run/executor/scope assignment，之后全链只用原API/worker。它不是零授权setup的正式首用：当前普通新Run合法生产批准/分派授权合同缺失仍为BLOCKED，禁止用新Grant/registry/隔离桥掩盖。两次成功新输入为同一fixture-a企业；跨企业/园区/错误角色是拒绝矩阵。

每个五目标产物与PG精确同链：材料UUID/version/text SHA及REVIEW/CONFIRM事件，资源link/combination/member与实际容量，dispatch/offer/ACCEPT actor与receipt step，当前人工receipt UUID/version/text SHA/SUBMIT+ACK事件，当前cycle REVALIDATE snapshot SHA，以及嵌入计划的明确VERIFY来源SHA/事件。缺receipt/ACK、错误hash/陈旧资料版本、跨Case原key拒绝无半写；只GET原key核对丢响应，不自动重发。取消后的旧通知GET/OPEN/MARK_READ重核状态、迟到ACCEPT409，原offer保持OFFERED，组合仍占容量直到独立释放。关闭会使P5失效，需再次明确VERIFY；Case从未写FULFILLED。

独审新模块与额外反例的结果单列在[最终独立报告](evidence/f2-t07-full-chain-20261011/README.md)，不累加为根完整回归数量。原失败窗口及中断窗口全部保留，失败同testID最终对应表、每步HTTP/PG/worker/coldAPI证据与完整原AT01–35映射见[证据索引](evidence/f2-t07-full-chain-20261011/README.md)。导出件明确标脱敏/压缩，清单同时记录原件和导出件hash；失败未改为PASS。

补跑曾误选真实Chromium专项模块，pytest因缺playwright在收集阶段退出2、0PASS/0FAIL/1ERROR/0SKIP，未执行测试或启动浏览器；原argv/log/XML保留。该浏览器模块未重试、未安装依赖、仍NOT_RUN，不声称错误sameID已修。之后只跑独立允许的PG专项。此前39模块首窗因冷API主动SIGTERM退出码oracle需修正而由owned SIGINT停止，17PASS/0FAIL/0ERROR/0SKIP、exit1并附pytest teardown KeyError，均原样保留，不计完整回归通过。

正式F2/AT35/PR0-alpha、真实模型/正式服务发布、三工作台真实浏览器验收、真实园区/线下效果和干净Windows仍NOT_RUN。历史Chromium data:导航ERR_BLOCKED_BY_ADMINISTRATOR保持，浏览器启动与替代重试0；真实模型/付费调用0，无生产部署/迁移、新Grant/信任登记、凭据或网络配置、权限扩大、强推或保护分支写入。历史Case_count0仍UNCONFIRMED，本次CLI worker真实成功建新Case不消除该历史未知原因。

下一步需要在原产品范围明确普通新Run的合法批准/分派授权生产合同，并另验正式模型/发布与工作台；本片不扩大这些前提。源码之后的交付commit只归档文档证据，最终完整SHA与实际正常push/远端/干净工作区记录另核。
