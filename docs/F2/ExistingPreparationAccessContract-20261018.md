# 既有主体的资料准备权限配置

基线 `a9c725babd36561a6a25733953cc374ee1b77bd5`；原 P5 的42有效节点由父级有限接收，不为本片整包重跑。普通开发分支，唯一源码/Git写入者。

原文：产品设计 §3（资源工作区及角色菜单）、§10（317行初始化不得覆盖配置）、§11（339行当前授权/Case范围交集）；开发计划 F1-T03、§14（325行来源台账）、§15（366行初始化/启动）。当前 `cli.py` 仅迁移、固定三企业 seed、撤权；Windows Setup 也只调用该 seed。资料专员、PREPARE/REVIEW_ASSIGNED 与目录靠测试/演示setup补建，没有供合法既有主体使用的配置入口。

本片最小功能：本机 CLI 读取一份有界JSON配置，仅引用**已存在**的同园区企业owner、reviewer和精确服务目录。默认 `prepare-access --config FILE` 只做数据库只读 dry-run，列当前阻碍及两项准备权限变更；独立 `--apply --expected-plan-sha256 SHA` 才能执行。没有HTTP管理入口、自动启动修复或默认seed调用。

配置不含会话、token/hash、DSN、路径/SQL或任意权限列表，未知键和重复JSON键拒绝。身份和目录均不由配置创建/导入实体；材料仍由原用户入口明确补交、核对、确认。源服务仍只接受原明确 SYNTHETIC 目录，不把它标为真实或正式发布。

只可 INSERT 两类缺失的原 `preparation_grants`：owner/PREPARE，reviewer/REVIEW_ASSIGNED。权限实际范围是原principal+park/org+capability，不是目录或某Case专属权限；owner仍限本人事项，reviewer仍限原指定事项，原业务路由继续动态检查。目录引用用于核对配置来源，不缩小或代替该原权限范围。

既有主体必须active、角色/园区/企业精确匹配；owner已具有READ/EXECUTE，reviewer已具有READ。能力Grant只校验，不新建或恢复。现存inactive或错scope准备Grant阻断，不UPDATE、不覆盖、不复活；active同scope保留。仅允许原支持的服务ID及精确既有version、SYNTHETIC来源与原目录证明。缺主体、能力、目录或证明就准确阻断。不能据此补建真实身份、目录发布、执行者或资源授权。

dry-run 使用只读事务，不写审计、不发凭据。它只是配置差异，不是Approval/Run访问权。计划SHA绑定配置、数据库实例/数据库、当前主体及能力/准备Grant代际、原目录内容/代际；不包含凭据或材料原文。SHA是状态复核fence，不是签名或管理员授权。

apply必须实际直连数据库owner/session owner，并拥有原相关public表；普通应用角色即使意外有INSERT也不能冒充管理员。现有principal锁按稳定ID顺序独占，随后锁定/复核原行与目录。取得所有等待后的当前快照须匹配明确expected SHA，已变更则拒绝；新insert与原authorization_audit同一事务，全成功或全回滚。异常不得宣称没有提交，先重新dry-run核对，不自动重放。

原审计仅保存操作类别/具体权限及计划SHA，outcome=ALLOWED；reason作为受审配置被SHA绑定，不向日志复述自由文本。无变更返回NO_CHANGE而非声称新授予。一次成功后旧SHA因代际变化不再适用；没有原键持久回执，不冒称幂等原请求恢复。管理员删除原撤销记录等可信数据库改写不在历史证明保证内；原CaseStep仍核对新代际，重新插入权限不能使旧marker复活。

普通启动与管理入口分开；不调用Native/隔离provider作为管理授权，不恢复Native拒绝，不改原业务算法、roles、schema或测试权限。现存应用/provider Store不得充当管理员上下文；单独的直连owner Store才可应用。此片只提供可审的代码和新拥有Linux PG上的合成测试，**本会话不执行任何真实身份/Grant新增、分派、目录发布、批准、凭据、生产安装或权限调整**。

验证需覆盖默认只读、显式两Grant原子应用/审计、原资料用户流程与冷启、不改能力/身份/目录/Run授权、普通应用角色拒绝、inactive不复活、角色/租户/目录/数据库/代际/陈旧SHA拒绝、并发变更/等待后检查与失败回滚；CLI错误不回显凭据/原始配置。保护上片P1–P5及原目录/权限算法，独审先固定原文oracle，再按最终SHA有限验证；失败与探针归因保留。

真实身份接入/合法来源取得、正式目录发布、执行者/资源管理初始化、生产schema安装及Windows正式AT35仍缺或未验；当前代码的SYNTHETIC支持不能凭填配置变为真实业务准入。不改main、不强推、不部署、不调用真实模型或新增费用/安全网络权限，不删未知锁/进程。
