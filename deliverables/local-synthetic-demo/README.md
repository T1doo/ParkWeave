# 当前合成演示代码包

下载 [ParkWeave-SYNTHETIC-0ff5b76417bc.zip](ParkWeave-SYNTHETIC-0ff5b76417bc.zip)（970,100 bytes），[SHA256文件](ParkWeave-SYNTHETIC-0ff5b76417bc.zip.sha256)：

```text
45c6b640ed64957688bbcdd990f71867a86511c6191aa7b83b76f423ba334288
```

固定源码提交 `0ff5b76417bc0ad9c5c8a7b456f154fe33e61db6`，基于材料交付 `5842312391dce574a25087ed974308ada1798623`。全部178个产品源码文件及原材料启动器字节保持；只同步打包及说明。包内194项，包括190件源码/说明、BUNDLE、入口、核对表和校验和；不含Git历史、完整测试/证据库、第三方依赖、数据库、会话、凭据或私有配置。旧包保留。

## 精简运行步骤

1. 核对ZIP哈希，解压后先读 `START_HERE.txt` 和 [运行说明](../../docs/demo/LocalSyntheticExperience.md)；包内同路径可用。
2. **原保留材料演示库**：由原环境持有人在原Git checkout使用既有`.venv`，按说明只运行 `.venv/bin/python -m scripts.material_only_demo serve --state-dir <原私有目录> --port 8765`，不再setup。仅回环地址，当前服务停止；原私有会话私下取用。启动器依赖Git绑定，不能从无`.git`的解压目录重启原库。
3. **解压源码接入已有合法环境**：先具备Python3.12、锁定依赖、schema32应用DSN、会话和必要既有权限。按说明分别启动普通 `parkweave.api:configured_app` 与 `parkweave.worker`。材料路径与另需pack/journal的严格 `LOCAL_SYNTHETIC_DEMO` profile分开；缺项准确停止。本包未提供新安装零准备的初始化路线。
4. 可合法运行沙箱浏览器的环境按 [A/B离线短卡](../../docs/demo/LocalSyntheticWalk.html)操作材料审核确认/文本下载。当前云环境SUID helper拒绝保持，不重试、改权限、禁用沙箱或换路径绕过；本轮没有再次启动服务。

## 已验与缺口

- 本次原独立库：两事项真实HTTP材料链、独立审核确认、完整重启回读、原客户端纯函数文本前后相同；本次DOM/浏览器下载未验。可取用[两份合成材料文本](../material-only-demo-20261018/README.md)。
- 历史真实Chromium：普通P1–P5/六产物/关闭重开/冷读（准备与精确Run assignment预置SYNTHETIC fixture）；另有两新事项材料复用、审核确认、实际下载与冷读。各自在原报告冻结版本已验，不能拼成一次AT35；当前沙箱拒绝不否定历史DOM证据。包内保留三份范围报告，完整原证据仍在仓库。
- **新安装零准备→同Case完整P1–P5→再次运行的无夹具补接线正式AT35尚缺**。须有正常安装/初始化、取得当前执行访问及资源/批准的合法路线，并在可用沙箱环境从同一安装逐步留证。完整F2/比赛交付未完成；Windows正式AT、真实模型/园区效果、正式来源映射/批准消费和C0官方模板/申报仍有各自缺口。正式外部来源只阻对应真实业务主张。

本轮冻结13项原离线预检测试全通过；190件源码及193条校验和、解压离线入口、辅助导入均核验；独立复建ZIP字节完全相同、源码/解压载荷零漂移，无P1/P2阻断；独立业务测试0，不累加测试数。无业务/数据库/浏览器运行。核对结果见 [delivery-validation.json](delivery-validation.json)。旧33bf包184件源码与584原白名单逐字节一致，但缺后来材料启动器及说明，故仅做必要同步。

复建（已有仓库与Python，无安装/联网/运行配置读取）：

```bash
python scripts/package_local_synthetic_demo.py --commit 0ff5b76417bc0ad9c5c8a7b456f154fe33e61db6 --output <不存在的新ZIP路径>
```

旧版本：[33bf源码包](ParkWeave-LOCAL-SYNTHETIC-33bf2efa125e.zip)，940,079 bytes，SHA256 `a6bdbe2846415d585653d92668faca2784328667f06f652c275b8c3b20736b9b`；其[原验证记录](../../docs/F2/LocalSyntheticExperiencePackage-20261018.md)保留，旧入口中的环境结论属于该历史冻结。
