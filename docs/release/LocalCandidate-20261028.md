# 本地源码候选交付 · 2026-10-28

项目版本仍为 `0.1.0rc1`，Python 合同为 `>=3.12,<3.13`。本次文件名额外带完整源码提交的前 12 位，区别于旧预发布资产；不是新的已签收 Windows Release。交付目录中的 `delivery-manifest.json` 记录完整提交、Git tree、源码文件 SHA256、锁定 Windows 资产及实际构建结果，`SHA256SUMS.txt` 校验交付文件。内部哈希不构成发布者签名。

## 文件与源码一致性

- `source-candidate-<commit>.bundle`：本次开发分支及其完整可达 Git 历史，无外部 prerequisite。Linux 本地产品依赖 Git checkout，请从此 bundle 克隆并核对完整 HEAD；不承诺携带无关分支或未引用悬空对象。
- `source-candidate-<commit>.zip`：该提交全部 tracked 文件的源码快照，不含 `.git`、本地安装、数据库、凭据或虚拟环境。它用于源码审阅；不要把直接解压或补做 git init 当成已满足原源码绑定的 Linux 安装。
- `delivery-manifest.json`、`source-files.json`、`SHA256SUMS.txt`：交付元数据、逐文件哈希与外部校验值；构建和验证日志同目录保存。

便携 builder 使用显式 40 位 `--source` 从 Git archive 读取应用、Windows 脚本及 launcher，并校验 builder、payload parser、资产锁与该提交一致，不打包未提交工作区文件。`RUNTIME_SOURCES` 包括当前 protected staging、登录、静态检查和启动接线；完整 `src/parkweave` 包括当前工作台 HTML/JS 与 SQL。

本轮环境没有为 Windows bundle 配齐锁定的 24 份运行时资产。实际便携构建在读取缺失资产时拒绝，没有生成 Windows runtime ZIP 或新 EXE。旧 BLOCKED 二进制没有被改名、复用或描述为本次字节。源码包中的 `.cmd`、`.py` 是入口源码，不是已经完成原生验收的可执行安装包。

## Linux 安装、启动与退出

仅由安装者在已授权、非 root 的 Linux 环境操作。先从自包含 bundle 克隆到新的独立目录，并核对 manifest 中的完整源码 SHA；按 [本地资料工作台](../demo/LocalMaterialProduct.md) 准备 Python 3.12、候选依赖和 `local-product` extra。源码包没有附带离线依赖仓库，因此依赖安装是否需要网络应由安装者明确安排。

安装执行 `python -m scripts.local_product install`，分别安全输入企业和专员密码；只有新建才生成独立私有目录及合成数据库。记录输出的 `state_dir`。启动执行 `python -m scripts.local_product start --state-dir '<原 state_dir>'`，打开输出的回环 URL；不会自动发现凭据或采用旧数据库。当前业务支持提交、补材料、补正、审核、确认、重开及进程重启回读。

在运行服务的终端按 Ctrl+C，等本次 API、worker、PG 正常停止后再退出；关闭浏览器标签不会停止服务。重开使用原 `state_dir`，不再次 install、不 seed、不修改授权。源码/数据库身份变化会拒绝重开；此版没有自动升级或迁移已封存安装的功能。

## Windows 入口与实际验收门

只有未来取得对应平台验收及明确安全操作授权后，才可验证新 Windows runtime 包。双击 `ParkWeave.cmd` 的源码流程为重开／首次新建／只读状态／退出；显式参数会转发给私有解释器。指定 `--instance` 默认只重开；首次新建要求独立不存在目录和两个明确不同端口。重开失败不转新建。

当前首次新建仍因 `OWNER_MUTATION_PAUSED` 拒绝；重开不再误用新建暂停，但仍经过 fixed journal 与 native loader 独立拒绝门。需要逐项完成：

1. Windows `cmd.exe` 真实参数传递、私有解释器与全部依赖来源/加载检查。只读检查不需要新增安全 setter 授权；也不得改用用户电脑。
2. 私有目录/文件创建、固定 slots 的写入与停止/重开、DPAPI 分账号解封、异常清理及只读文件核对。凡涉及实际创建凭据、目录保护或安全属性的新窗口，须先确认具体 Windows 环境与操作范围。
3. 新建 initdb 的派生 token `TokenOwner`/`TokenDefaultDacl` setter、原始管道客户端身份、Job 进程与认证前 endpoint witness。这些实际 setter 当前没有授权，不能消耗历史许可，也不能只删门运行。
4. 原生 PG/API/worker 完整办理、独占启动、失败 UNKNOWN 保留和持久重开；须在上述条件获验收后执行，不能用云端协议 double 代替。
5. 1366×768 与 1440×900 真实主工作台像素和键盘操作验收。当前云端浏览器曾在 SUID sandbox 启动阶段拒绝，未重试、未绕过、未出截图。

## 卸载与清理范围

本版不安装系统服务、计划任务或全局卸载器，也不提供自动清理按钮。卸载由安装者明确选择：先正常停止本次所有自有进程，再决定是否删除本次独立 checkout/虚拟环境和已确认不再需要的原 `state_dir`。保留 `state_dir` 会同时保留合成业务、加密身份与日志；删除它会丢失这些内容。密码遗失、备份迁移及跨机器 DPAPI 恢复没有自动补救承诺。

Windows 源码/候选解压目录只有在没有运行进程、没有需保留实例数据时才可删除；运行时源文件可能仍被本次实例持有。不要递归清空共享 `.runtime`、未知目录、其他集群或进程，不修改服务、防火墙、账户、系统 Python 或系统 PostgreSQL。UNKNOWN/停止未确认时保留目录与日志，先核清原拥有关系，不能把删除视作恢复。

本轮产物仅保存在指定云环境，未上传、未更新 PR 说明、未部署。
