# Linux 本地资料工作台

这是使用原 PostgreSQL、普通 worker 与原资料 API 的合成资料产品入口。企业提交诉求并补充材料，获派专员要求补正或核对，企业确认；可以重开、再次核对与确认，并停止/重启进程回读原记录。它不调用模型，不连接真实园区，不表示资格通过、外部受理或履约完成。

需要本机非 root Linux、完整 Git checkout、Python 3.12 和已安装依赖。它不是 Windows 安装器，也不是可搬迁 wheel；不要在用户电脑上代为操作。安装者在已授权的 Linux 环境自行使用：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[local-product]'
.venv/bin/python -m scripts.local_product install
```

安装时分别输入企业、专员密码并确认，至少 12 字符且两者不同。输入不回显，不通过参数、环境变量或文件提供密码。默认在 checkout 的 `.runtime/local-product` 新建独立私有目录和合成库，输出 `state_dir`；可用 `install --parent '<已存在的私有目录>'` 指定长期保存位置。父目录须由当前用户拥有且其他用户无权访问。不会采用旧库、覆盖会话或修复授权。

```bash
.venv/bin/python -m scripts.local_product start --state-dir '<本次输出的state_dir>'
```

打开 `http://127.0.0.1:8765`。默认只绑定 IPv4 回环；端口已占用时拒绝，不终止占用者。正常停止在前台按 Ctrl+C，再用同一 start 命令重开。密码遗失不自动重置；不要重新 seed 或修改既有会话。

工作台左侧固定导航，中间新建入口/事项列表，右侧材料与操作。企业先提交诉求，待本地 worker 建立记录后明确点击“开始准备材料”；补齐“诉求摘要”和“材料目录”，注明合成来源类型/版本。退出并由专员本人登录，选择同一事项，要求补正或填写说明后核对；企业本人再登录并确认。材料和办理记录分别在右侧区域滚动，操作区保留当前角色的审核、确认、重开按钮。刷新后需重新登录；未开始准备的已提交诉求可从“接续已提交的本地诉求”只读选择。

每个角色用独立 scrypt 密钥与 AES-GCM 密文保存随机 bearer；密码和 bearer 不以明文写文件。密文认证本次物理目录与数据库身份，登录仍核对当前数据库身份状态。角色切换清空当前页面私有内容；不是同一操作系统用户之间的隔离沙箱。下载是当前有权读取的资料快照，后续撤权不能追回副本。

事项按每页 20 条显示，列表底部“上一页／下一页”可访问旧记录；接续诉求直接按原 Run 查询对应事项，不再只搜索最近 100 条。

发送变更前，浏览器先持久保存无秘密的原请求句柄；刷新、退出重登后仍显示待核对状态。它包含安装标识、完整角色身份、请求键、操作及正文指纹，不包含密码、bearer 或材料正文。使用 Web Locks 保证同一安装和角色的多标签页互斥；存储或互斥能力不可用时暂停写入。待核对句柄属于同一浏览器与同一地址端口，不能作为跨设备恢复或备份。

提交结果不明时停止写操作，不自动重试；只有 ADD_EVIDENCE 提供原请求键的只读恢复，且要求原正文指纹、完整身份、当前凭据摘要、当前版本、快照和精确回执都一致。其余 UNKNOWN 不自动消除。不要清理站点存储来绕过待核对状态。

**持久范围：** 新安装使用独立 `LocalDatabaseCreationEvidence`，绑定新建私有目录、真实 initdb、自有 postmaster、Unix socket 内核对端与实际 CREATE DATABASE。原 `/tmp` fixture 凭据合同保持原样。已经在 `/workspace` 下实际创建并验证 API、worker、PostgreSQL 正常停止/独立进程重开后的原记录精确回读；无需搬迁临时库。重开只读校验实际运行源码字节、库物理身份、schema32 和原权限快照，不再 initdb、迁移、seed 或自动复权。此证据不代表主机重启、平台卷保留、灾难恢复或备份已验证。UNKNOWN 安装不自动重试。

**Windows 源码进度：** 具体 Security/ClusterPrerequisites、DPAPI reviewer provider、数据库认证前 endpoint witness、原始 initdb 管道写入和工厂/入口已接线。`NativeRuntimeInstallation` 在原 fresh lease 下持有源文件与父链，按冻结清单排除别名/保留目录，以显式私有描述符和 FILE_CREATE 写入完整运行时；同句柄回读 SHA256 后关闭 writer，再保留同 ID 的只读 pin。重开核验已有完整树，缺失不复制、不修 ACL。源 payload 全树也必须已有合规私有 ACL，普通 ZIP 解压不提供这一保证。

`NativePreparationSessionProvider` 将原六身份分别用独立安装密码派生的 scrypt/DPAPI entropy 密封，再写入原受保护目录的 WEB_LOGIN 文件。新建才询问密码，重开只读；本轮没有实际生成 Windows 凭据或执行安全设置。API 子进程只接收有界密文配置，worker 不接收。网页登录解封后仍通过原数据库核对当前主体、组织、园区、角色和撤销状态；原 token 不因角色选择自动发放。身份只保留在页面内存，UNKNOWN 句柄保留原隔离约束。未知 DPAPI 清理会锁住本次登录 provider，保留原 native 状态，不继续尝试。

**未验与缺口：** 云端 Chromium 在打开业务页面前因原生 SUID 沙箱拒绝，未生成主应用截图；1366×768/1440×900 的布局尚无真实像素验收。没有关闭沙箱、修权限或改用用户电脑。原 `OWNER_MUTATION_PAUSED`、`WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED`、`NATIVE_PAYLOAD_ENUMERATION_NOT_ACCEPTED` / `NATIVE_RUNTIME_LOADING_NOT_ACCEPTED` 仍关闭；完整 installer 已有独立 native 枚举实现，原 PG 静态检查调用合同尚未取得 native acceptance。Windows 仍不能宣称可交付启动与办理链，源码/协议检查不是 Windows 实跑验收。完整 AT35、正式来源和真实试点分别待验。

新增云端补证使用真实持久 HTTP/worker/PostgreSQL：有界代理在原 ADD_EVIDENCE 已提交后截断响应，两个 Node 页面上下文执行实际页面 api/logout/recover，合计一次 POST；A 退出后 B 的恢复 GET 为零；A 重建页面后使用原 key 和当前版本两次只读 GET，且服务重启后内容一致。Node 页面上下文不是浏览器双标签验收。分页以 105 条精确 ID 集合核对无漏重，同时间戳按 UUID 稳定分页，并拒绝跨组织及同组织未获派/非 owner 的游标。
