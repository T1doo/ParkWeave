# 普通用户本地合成体验包

普通用户用浏览器打开 [AcceptanceWalk.html](AcceptanceWalk.html)，根据安装者提供的本机地址和现有合成会话操作。无需写代码、编辑JSON或提供模型密钥。操作卡离线使用，无外部资源、无网络请求、无输入凭据字段；勾选不持久保存，刷新清空，打印可留空白核对表。

基线：`9ab3c06567ec4d3ff2bcd8152008ba46c39089a5`。依据原V1 §5.2、§5.5、§7.2–7.5、F2计划及ENG098/099/100。仓库及本环境 `.agents` 未发现 AGENTS.md 或相关 SKILL.md。原独立支线本包仅新增 `scripts/demo_preflight.py`、`tests/test_demo_preflight.py`、本目录及独立证据，不修改核心、Windows脚本/workflow、迁移或身份权限。

## 安装者离线盘点

在已批准Python3.12环境执行（任意工作目录均可，路径指向本仓库）：

```bash
python scripts/demo_preflight.py
python scripts/demo_preflight.py --json
```

返回0表示资产与依赖元数据齐备，2表示Python版本或资产/依赖缺失。工具不导入应用、不读取 `.runtime` / 会话 / DSN、不连接数据库/网络、不启动进程、不写报告、不安装软件。依赖版本仅列出，不验证版本兼容性；服务、数据库、业务访问始终 `NOT_PROBED`。不能将返回0作为业务可用或验收通过。

缺依赖时交由安装者按既有授权准备；本工具不会自动修复。Linux已有harness与启动说明见[原首次体验](../首次体验.md)，本包不重复启动器。已有环境由安装者按原授权准备。原harness会seed身份/Grant，因此原体验包支线未运行该harness。主线实际浏览器回归仅使用原隔离UUID fixture测试setup（浏览器开始前），不创建生产授权，开始后七项权限表须保持hash不变。也不新增Run assignment。没有已准备的合法环境时，只能验证本包离线盘点和操作卡结构。

## 两条路径和真正的停点

- **普通新Case路径：** 同一事项从资料准备新建、显式目标、补正、人工核对到确认；核对该Run已有合法访问。没有assignment则停在接单前，不能称完整冷启动。即使资料已齐，不能借旧Case执行者授权继续。
- **已具备合法前置的同Case路径：** 五个持久步骤、原执行者本人接单、新回执企业核对、本地关闭重开、材料新版本、新OFFER/ACCEPT、新回执世代和逐步重核。若使用预置恢复Case，它只能算预置案例恢复，不算上节新Case闭环。

ENG098 `/template` 是显式独立组合工厂的隔离候选，普通harness不挂载，不应在原产品地址输入路径期待正式模板。候选作者/审核者/发布者和正式权限合同尚未签收；本包不启动候选工厂、不准备候选主体。ENG099恢复保持同一Case和原执行者，新回执不复制旧正文/核对。

已有 `template_cold_start_browser_smoke.py` 与 `dispatch_recovery_browser_smoke.py` 需要各自测试owner准备的私有stdin上下文、合法授权以及已获准缓存浏览器；不是普通用户直接命令，不拼接它们宣称一个冷启动闭环。本包不复制它们或生成含凭据的上下文。它们已有历史PASS不是本包当前环境的实测。

## 维护者验证

```bash
python tests/test_demo_preflight.py
```

使用标准库 `unittest`，位于既有 `tests/` 路径，也可被已准备的pytest收集。测试只创建临时合成文件，不调用应用/PG、模型或权限setup。本线不修改冻结分片清单：整合方需按既有流程刷新collection/manifest再宣称全量工程覆盖。

新增测试文件属于现有CI路径过滤，但现有workflow只监听 `dev/f1-foundation`；本线独立分支不会匹配该触发条件。没有更改workflow。独立支线未触发主线CI；主线整合后的准确HEAD另行核查现有Server隔离Job，不代表完整Windows/Win11。不部署、不合并main。

独立支线原证据保留在 [evidence.json](evidence.json)：当时解释器缺少产品数据库依赖和pytest，离线Chromium两次未生成图片；产品UI/PG/Windows均NOT_RUN。这些是独立支线的历史结果，不能描述主线本次环境，也不能用其6项标准库PASS替代主线浏览器验收。主线整合从上述已完整测试的ENG100基线开始，新增同owner同服务材料目录复用说明；实际离线卡/产品UI验收及当前解释器盘点另存 integration-evidence.json，未形成终态前不申领通过。

同用途材料复用使用原产品专用入口，须在新Case尚无任何材料时明确选择来源、用途和理由；只复制material_outline为新UUID/v1/UNVERIFIED。该Case的新need_summary、独立人工REVIEW/CONFIRM及当前Run合法访问仍需重新准备。详见[ENG100验收映射](../F2/ENG100-V1AcceptanceAndMaterialReuse.md)。

本任务的受管Chromium明确阻止 file:// 导航，不能据此申领文件直接打开通过。安装者可在既有本机只读服务上以固定URL展示公开操作卡；实际测试仅该卡预读字节响应，其余路径404、不开放仓库目录或私有会话文件，不修改浏览器策略。此模式仍不请求外部网络。直接文件打开结果与本机HTTP结果分别记录。


## 当前冷入口接线

Linux启动命令须显式使用 `--fresh-fixture`（见首次体验文档）。它在系统临时目录初始化全新自有集群，在CREATE DB前读取实际集群证据，CREATE后取得同进程receipt，原Store同事务迁移001–025。就绪输出runtime_directory及已核实的本次API进程/端口；会话只存本次私有临时目录，正常结束只清理本次服务与目录。已有仓库.runtime和旧库保持；仅既有schema25允许原持久模式，低版本不补造票据、不自动迁移。

普通使用者从服务目录的新资料事项入口经原Run API/LOCAL worker创建Case，再填写事实/材料、人工核对和企业确认。身份、角色、合成服务/资源目录依然由原fixture初始化，新Run的executor assignment仍未提供；无合法访问时停在分派/回执前，不能称无需准备的全业务闭环。本轮从零指0业务Case/Run/资料/事实/回执，不是无身份/目录初始化。实际验收记录在本轮证据中，不沿用旧预建Case截图结论。
