# 既有本地合成服务选择接普通 CaseStep 与冷恢复

基线 `f16d9cf7895e31ad7aab7594494c90bb1e8fa7fb`。原分阶段计划 F2-T02 要求有限注册服务图与明确输入/产物，F2-T07 要求三个工作区和持久化办理；本片把既有两个入口精确组合，不重写规划、选择、ADOPT、P1–P5 或恢复算法。

新增默认关闭的显式 `PARKWEAVE_CASE_STEP_MODE=LOCAL_DEMO_CURRENT_PREPARATION`。必须同时提供原 `LOCAL_SYNTHETIC_DEMO` profile 与严格 config/1；加载已有 hash-pinned pack/1、私有 journal/1、实际 DB 绑定与原目录 hash/xmin，只允许原 schema32。输入文件仍只读，不初始化、重绑、修复、签发或发布。原 `CURRENT_PREPARATION` 继续拒绝所有 demo/V4/provider 配置；通用互斥不删除。

只允许精确 `OrdinaryCaseStepAssignments` 与精确独立 `LocalSyntheticDemo/LocalDemoCatalog/LocalDemoSelector`，同一个 Store、同一个 catalog 对象显式配对。Isolated、Native、formal source、Approval、V4 模型及其他 provider 仍互斥；管理配置入口与 Isolated CaseStep 不取得该例外。API 与 worker 从同一显式配置各自只读构造，不传入 fixture permit，不创建 Run assignment。

普通事务进入和全部原检查之后均核对 pack/journal/DB/目录/有效期，实际 parent 必须与包内已有 owner/reviewer/park/org 相同，执行者只能是包中已有 service_executor。原当前 READ/PREPARE/REVIEW_ASSIGNED/EXECUTE、主体 generation、资源 READ/HOLD、Run/Case/create 证明、原绝对300秒期限和3秒锁超时仍须通过。配对仅选择路由，不增加任何权限。配置与资料身份不足精确拒绝，不能由 pack 导出批准或创建发布权。

用户从原目录选择产生原唯一有限解，producer 保持 `NO_MODEL`、provider=false、model=null、real_model_calls=0；显式原 ADOPT 后直接进入既有办理工作区，依次明确核验 P1、原资源组合/关联与 P2、专员 OFFER/执行者本人 ACCEPT 与 P3、人工 SUBMIT/owner ACK 与 P4、本地 REVALIDATE/CLOSE_LOCAL_RECORD 与 P5。LOCAL_OUTPUTS_VERIFIED 和本地关闭不表示 Case/线下履约完成。

Linux 演示启动器可显式读取一个既有 config 文件传给普通 API/worker；默认启动不变，setup 不生成 demo pack/journal。验证只能在新拥有的离线 SYNTHETIC 空业务初态写入测试包和 journal；与产品启动只读输入、真实业务缺口分别记账。原三主体/目录/资源及34条合成初态不扩展，不采用旧 Run assignment 链。

已有合法输入时，保留原现场的启动命令是 `python -m scripts.ordinary_synthetic_demo serve --state-dir /tmp/parkweave-ordinary-demo-<existing> --local-demo-config /absolute/existing-config.json`。不传该选项仍为原 CURRENT_PREPARATION。直接使用 configured_app 与 worker 时，二者均须显式同一 DSN、LOCAL、新 CaseStep mode、原 profile 与 config JSON；不从环境寻找其他凭据或自动推断模式。

在原页面读取此 Case 的服务方案与服务能力，明确生成合成候选，勾选确认并填写采用理由后点击原采用入口；采用后五个原步骤的“进入此Case…”按钮就是后续办理入口。原专员/执行者工作区与现有会话不变。选择候选不自动接单、核验或关闭；重启后只读取原记录与原 key。

验收为实际普通 API/worker 新建 Run/Case→新诉求/双材料/REVIEW/CONFIRM→目录选择→明确 ADOPT→原完整 P1–P5→停止 API/worker/PostgreSQL→同库冷启动，读回原候选/key、计划/结果、原 TXT 和原期限，不能重发命令、重算模型、续期或改变权限/目录文件。原 HTML 必须显示候选来源并在 ADOPT 后可继续办理；不是新预览按钮或矩阵。

有限固定 oracle 覆盖完整链与冷恢复、精确配对/旧互斥、包或目录变化/缺权限拒绝、无 Run assignment 和无 authority 变化。独审本轮仅静态，旧平台标记动态窗口不重试；历史 HTTP 超时 UNKNOWN 保持未关闭。真实模型/业务、浏览器正式场景、Windows 正式 AT 与项目完整性不在本次结论内。
