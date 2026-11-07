# 一次 Windows 隔离运行的具体方案（待授权，未执行）

目的：推进真实 Windows 初始化、办理和冷重开，不能以删除 OWNER/FIXED/LOADER 拒绝门、mock 或截图替代。

## 已核实的阻断

- 实际新建请求返回 OWNER_MUTATION_PAUSED；setup_readiness 无条件 BLOCKED。
- 后续还有独立 fixed journal 与 loader 门，不是只改这一处就能运行。
- native_trial_authority 的源授权只接受已冻结的隔离执行记录；现有 native_business_window.json 为 null。
- 原生验证包含 LocalService DPAPI 对照，代码明确可能产生该服务身份的密钥缓存；原设计依赖隔离 runner 销毁清理，不在用户日常电脑上擅自执行。
- 原试验 composition 只覆盖 MATERIAL 六身份，不自动授权四角色 SAMPLE；这两个范围必须分别补证，不把前者的通过改名为后者通过。

## 请求授权的范围

1. 为本次工作创建单独临时分支，不改 main，不发布版本或部署。
2. 将明确选定的源码、测试和一次执行记录提交到该临时分支；排除 .cache、数据目录、身份文件、密码和密钥。
3. 准备并触发一次 GitHub Actions Windows 隔离测试，整次上限25分钟，产生 Actions 用量；失败保留日志，不自动无限重跑。
4. 仅在该次 runner 的新私有临时目录使用已锁定的运行依赖、合成数据和临时应用身份；测试原初始化/退出/重开边界，不接真实园区、不调用付费模型。
5. 仅保存去敏结果、源码/产物哈希和必要截图，不上传密文凭据、明文密码、完整数据库或私有身份目录。

现有入口参考 .github/workflows/native-business-trial-once.yml；执行记录、源绑定、Windows目标差异和四角色范围须在触发前核对。此方案不是已经签发的源授权，也不把Windows Server runner结果当作用户Windows11全部通过。

## 顺序与验收

先在隔离环境完成原初始化与持久恢复诊断，修实际失败；再验证四角色已支持业务路径。最终仍回到普通Windows用户的完整EXE验证新建、办理、退出重开，原前端固定使用已有设计。

授权前继续本地源码工作，不自动提交/推送/运行工作流。授权后也不跳过原契约，不改全局安全设置，不创建用户电脑账户。
