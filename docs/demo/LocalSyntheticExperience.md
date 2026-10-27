# ParkWeave 合成演示：取用与运行

本包包含完整 `src/parkweave` 产品运行源码、`pyproject.toml`、现有启动辅助源码和操作说明。版本见根目录 `BUNDLE.json`，文件哈希见 `SHA256SUMS`；不含第三方依赖、Git历史、测试全集、完整证据库、数据库、会话、凭据或私有 pack/journal。它不是零准备安装器。旧 `33bf2efa125e` 包的产品源码与材料演示交付 `5842312391dce574a25087ed974308ada1798623` 完全相同，但遗漏了后来加入的材料启动器，本包同步这些辅助文件与说明，未改产品算法。

## 已有材料演示：只重启，不再初始化

本次唯一获准建立的 Linux 合成演示库及私有会话仍由原环境持有人保留，服务已停止。材料路径使用普通 `configured_app`，不启用 `LOCAL_SYNTHETIC_DEMO` profile；没有执行者、资源、Run assignment 或批准。**不要再执行 setup、seed、migrate 或扩建权限。**

在原环境的原 Git checkout `/workspace/ParkWeave` 中，使用其既有 `.venv`：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.material_only_demo serve --state-dir /tmp/parkweave-material-demo-fsnwe42i --port 8765
```

这是仅供原环境持有人使用的重启命令，本轮没有再次启动。启动器核对原私有目录、数据库身份/schema32、authority、Git `src` 树及启动器字节；本包只改打包与说明，保留受测产品与启动器字节。**它依赖 Git checkout，不能从没有 `.git` 的解压目录重启原库，也不能把该目录搬到另一机器当作已有环境。** 缺目录、源码绑定不符、端口冲突、未知进程/锁或未确认停止标记均停，不自动修复。细节见 [材料演示边界](MaterialOnlyDemo.md)。

HTTP 仅 `127.0.0.1`，PG仅私有 Unix socket。持有人私下读取原 `sessions.json`，在原页面输入相应企业/专员会话；不要把会话放入聊天、URL、截图或仓库。会话无自动过期，停服务不撤销。前台 Ctrl+C 只停本次持有的子进程，保留数据和会话。平台清理 `/tmp` 仍可能丢失，不能称永久保存。

当前环境启用沙箱的 Chromium 曾因 SUID helper 所有者要求拒绝启动。该拒绝边界保持：不重试、不改权限或所有者、不禁用沙箱、不换路径绕过。本说明不是当前云环境可打开网页的承诺，也没有将回环服务向公网暴露。

## 解压源码：已有合法运行环境才启动

另一安装环境需已有 Python 3.12、`pyproject.toml` 锁定的运行依赖、普通 schema32 应用连接及相应既有会话、Grant、合法目录。材料辅助启动器还依赖 Linux、Git 和已安装的 `pgserver==0.1.4`（自带PG二进制）；本包不自动安装、联网或新建权限。没有合法前置时停在源码阅读与缺项盘点。

普通 API/worker 可直接从解压包根运行，无需安装本项目。先由原环境提供方在私有环境设置已有 `PARKWEAVE_DSN` 和 `PARKWEAVE_MODE=LOCAL`，核对其服务 profile/provider；材料路径不设置严格 demo profile，不混入正式来源或批准配置。两个终端使用同一已有环境：

```bash
PYTHONPATH=src python -m uvicorn parkweave.api:configured_app --factory --host 127.0.0.1 --port 8765
```

```bash
PYTHONPATH=src python -m parkweave.worker
```

这些是 Linux shell 命令，未作为新安装或 Windows 正式 AT 执行。启动不会自动迁移/seed；原 worker 会处理该库可领取的任务，须由持有人确认库的范围。`/health` 的PID应属于本次自有API；健康不证明业务授权。仅在可合法运行沙箱浏览器的环境打开持有人核实的回环地址，不修改本环境的拒绝边界。

严格 `LOCAL_SYNTHETIC_DEMO` 是另一条已有合同路径，需 `PARKWEAVE_DSN`、`PARKWEAVE_MODE=LOCAL`、`PARKWEAVE_SERVICE_PROFILE=LOCAL_SYNTHETIC_DEMO`、`PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG`，及原 pack/journal、身份/资源映射与数据库/目录绑定；材料库没有这些输入。见 [原合同](../F2/LocalSyntheticDemoContract-20261017.md)。只做盘点：

```bash
python scripts/demo_preflight.py --local-synthetic --json
```

缺项返回2即停；0只表示盘点齐备。已有完整输入才可另加 `--check-existing-inputs`，复用原只读绑定校验，仍不检查会话/Grant/Run assignment，`business_ready=false`。不把 profile 缺项说成整个材料演示未启动或整个产品不可运行。

## 原页面材料路线

见 [离线短卡](LocalSyntheticWalk.html)。A设备维护、B员工培训分别建新事项：服务→查看可选服务与专员→开始资料准备；各自追加“诉求摘要”和“材料目录”，标明 SYNTHETIC 来源；专员本人“核对本地资料包”，企业本人“确认本地资料准备”；“生成当前材料文本包”→“重新核对并下载文本”。分别记录 Run/Case/preparation、版本、实际文件SHA，刷新重读。下载是当时快照，后续更新或撤权不追回副本。

仅有材料权限时到此为止。P1–P5另需当前事项合法计划、原执行者、精确 Run assignment、资源/字段权限及相应批准接线；缺项准确拒绝，不复制历史 fixture 或借旧Case授权。IsolatedPlanApproval不能作为普通批准。当前库没有这些输入，本轮不扩建。

## 已验范围与尚缺验收

| 范围 | 已有证据 | 前置与限制 |
|---|---|---|
| 当前独立材料库 | 两件新事项真实HTTP建单、两槽材料、独立REVIEW/CONFIRM；原库/API/worker重启后只读回读一致；原JS纯函数生成文本前后字节一致 | 本次9行合成主体/权限/目录；浏览器在业务前拒绝，未验本次DOM/按钮下载；首HTTP窗末尾重启失败保留，后续只读重启成功，不能拼成全绿窗 |
| 历史普通Chromium P1–P5、六产物、关闭/重开 | 同Case/step、回执v2/v3、P4/P5绑定、cycle1/2、重验及新普通进程GET冷读，1200/320宽度 | 准备及精确Run assignment在普通进程启动前由SYNTHETIC fixture预置；不是新安装零准备闭环 |
| 历史普通Chromium材料复用 | 两新事项从页面建单，来源预览、独立复制、审核确认、原来源变更、实际下载及新进程GET冷读，1200/320宽度 | 已有合成身份/Grant/目录/pack/journal；与当前材料HTTP演示分别留证，不能拼成一次AT35 |

历史报告随包保留：[P1–P5及关闭重开](../F2/OriginalCollaborationDOMValidation-20261018.md)、[材料复用](../F2/MaterialReuseDOMValidation-20261018.md)、[当前HTTP及重启](../F2/MaterialOnlyDemoValidation-20261018.md)。报告中的完整证据链接需在原仓库查看，最小包不复制全部证据。当前沙箱拒绝不抹去历史真实DOM证据；历史通过也不替代本次未执行的浏览器动作。

**尚缺“新安装零准备→同一Case完整P1–P5→再次运行”的无夹具补接线正式AT35**：需要一条经审查、可复现的安装/初始化与身份权限取得路线，能在正常流程中获得本次精确执行访问及所需资源/批准，而非测试中预置；在不降低安全的浏览器环境中从同一干净安装逐步完成并重启/再次运行，保留对象、产物、版本和拒绝证据。当前仅交付已实现源码及上述有限可用范围，完整F2和比赛交付仍未完成。

Windows正式安装/停启/关机AT、真实模型与费用验证、真实园区效果、正式来源专用backend/主体/原ADOPT映射、正式资源批准消费、C0官方模板及正式申报材料各自仍缺。真实外部连接在原设计F4–F6增强范围；其输入/代码缺口只阻对应真实业务主张，不阻合成软件交付。不得把合成确认称资格通过、外部受理或真实履约。
