# 园合 ParkWeave

面向园区服务办理的工作台：服务事项、协同派单与回执、资源关联、模板版本检查，以及保留来源与人工核验状态的目标结果和 TXT 核对包。

## 当前交付状态

这是 **0.1.0rc1 候选源码 / 预发布**，不是已经通过全部验收的端用户成品。

- 暖橙色服务、协同、资源、导览与模板页面已有分区、状态和响应式改进；历史图像验收有明确场景范围。
- 本地合成办理和权限检查已有工程证据。模拟数据、技术 Run 成功和 TXT 导出不等于正式业务目标完成。
- 新增可运行的 [Linux 本地资料工作台](docs/demo/LocalMaterialProduct.md)：企业/专员分别密码登录，真实提交、补正、审核、确认、重开及进程重启回读。身份加密保存；支持非临时私有目录安装、待核对请求跨刷新保留及旧事项翻页。依赖源码 checkout，主机重启和 Windows 实跑尚未验证。
- 已确认使用已有官方系统 CRT 的先决条件方案：只读核源，缺失退出并提供官方说明，不自动安装或搜索 PATH。详见 [CRT witness 合同](docs/release/ExistingSystemCRT-20261028.md)。
- Windows 私有实例入口仍拒绝初始化，`usable_product=false`。候选 ZIP 内有锁定运行时与依赖，用户无需为检查包而安装 Python，但该 ZIP **目前不能办理业务**。
- 真实浏览器连接当前模板 HTTP 链路尚未完成；Chrome 官方包准备仍 FAIL。Windows 原生安全/初始化/持久恢复、外部正式来源合同、LIVE 模型与正式 AT35 仍有独立缺口。

本次云端本地交付以 [源码候选说明](docs/release/LocalCandidate-20261028.md)、[独立桌面入口](docs/release/DesktopCandidate-20261028.md)和包外完整 SHA/哈希清单为准。下面旧文件名与 [旧预发布验收边界](docs/release/CANDIDATE.md) 保留历史含义；现已按锁取得公开依赖并生成真实 Windows runtime ZIP 与 AMD64 GUI EXE 候选，仍未通过原生验收。不要把 Windows ZIP 的完整性检查或拒绝启动信息当成安装成功，也不要通过关闭安全门强行运行。

## 文件如何使用

| 文件 | 用途 |
| --- | --- |
| `source-candidate-<commit>.bundle` | 本次提交及其完整可达历史；离线克隆为 Linux 所需 Git checkout |
| `source-candidate-<commit>.zip` | 本次完整 HEAD 的 tracked 源码、测试、文档与已跟踪证据；不含 .git、未跟踪安装数据或虚拟环境 |
| `ParkWeave-source-*.zip` | 旧预发布源码范围，见其配套历史清单；不能替代本次完整 SHA |
| `parkweave-0.1.0rc1-py3-none-any.whl` | 开发/集成安装包，声明 Python 3.12；需要已配置的依赖与隔离数据库，不是自包含桌面程序 |
| `Windows-runtime-candidate-<commit>.zip` | 当前完整源码及锁定软件依赖的真实静态封装；保留拒绝门，不能称已可办理业务 |
| `ParkWeave-Windows-BLOCKED-*.zip` | Windows x64 静态封装候选；入口明确拒绝初始化，留待集中原生验收 |
| `SHA256SUMS.txt` | 下载完整性核对；不是代码签名或发布者身份证明 |

## 开发与验证

源码声明 Python `>=3.12,<3.13`。核心 API/worker 需要明确配置的 PostgreSQL，不会自动搜索数据库凭据。普通开发安装依赖后可使用 `uvicorn parkweave.api:configured_app --factory --host 127.0.0.1`；必须先按既有合同准备 `PARKWEAVE_DSN` 和角色/资料配置，不能连接未知或共享业务库。源码内测试脚本不应被当作生产安装器。

正式模型未启用；请勿为试运行填入生产凭据。当前 Windows 资产锁指定内嵌 Python 3.12.10，原生兼容性仍须独立验收，不能由 Python 3.12 的云端测试代签。
