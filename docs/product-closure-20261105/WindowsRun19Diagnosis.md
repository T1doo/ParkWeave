# Windows 隔离运行 19：实际结果和共享冲突修复

运行：https://github.com/T1doo/ParkWeave/actions/runs/42025305561

用户明确追加授权一次；已执行一次，无自动重试。main 未改，无发布或部署。

## 实际到达的阶段

1. candidate-build 成功：输出 EXACT_APPROVED_BYTES，云端重建与冻结 r5 的 53,760,516 字节及 SHA-256 一致。
2. 第二个 runner 下载同次原始 artifact 成功，源绑定通过。
3. 私有候选解包通过，输出 EXTRACTED_VERIFIED_NOT_EXECUTED。
4. 严格 CRT 签名及吊销检查通过；该检查不等于产品验收。
5. 新建流程在 CLUSTER / PIN_COMMAND_PATH 失败，NtCreateFile 返回 0xc0000043（共享冲突），没有有效输出句柄。初始化尚未成功，桌面 trial 未启动，业务/回执/重开未验。
6. 最终结果 UNKNOWN / NOT_ACCEPTED，未自动重试或清理后再跑。原日志含租约清理拒绝，不能宣称完全正常退出；runner 隔离资源由平台处置，不在用户电脑留下业务库。

原始去敏结构化结果：windows-run19-native-result.json。汇总：WindowsRun19Result.json。

## 根因

测试标记目录由 OwnedNativeObjects 持有，原目录句柄使用文件同款 0x13019f（包括写入与 DELETE），share=READ。PGDATA 按 DOS 路径逐级再开 read/list 句柄，share=READ|WRITE 且不允许 DELETE；遇到该自有父目录时发生共享冲突。

原始 lease 的父路径读取仅请求元数据，能更早经过该目录；到 PIN_COMMAND_PATH 请求 list/read 后才暴露冲突。不是前端或 WebView2 导致的白屏，也不是通过解除业务禁用就能解决。

## 修复与边界

- 仅将测试标记目录句柄改为 0x120081（读取、枚举、描述符），保留 share=READ、原句柄及身份/ACL/路径核对。
- 标记目录本来就保留为空，不删除，不需要 DELETE；子文件仍使用原写入/DELETE 权限完成既有故障测试与有界清理。
- 没有放宽产品 PGDATA 的共享标志，没有改租约、owner、来源或 production acceptance 门。
- 在真实本机 Windows 的自有空目录上复现旧权限的 ERROR_SHARING_VIOLATION，再验证新权限允许 PGDATA 所需读/list 句柄；并验证竞争的写入/DELETE 打开仍被拒绝。没有启动 PostgreSQL、DPAPI 或服务身份操作。
- 相关测试共 46 passed，包含真实目录共享测试及既有 PGDATA 原生输出、未知状态与清理错误协议测试；后者为合成 FFI 返回，不是完整原生流程通过。

这证明共享冲突的局部修复有效，不证明 runner 中的后续 initdb、业务和重开已通过。第二次授权已经使用；未触发第三次运行。

## 下一份可审阅候选

修复已冻结在本地临时提交 `049d16e34ed12de739fe38683c6aef5dfc6d879b`，工作流禁用、执行记录恢复 null，未推送。

`.cache/ci-freeze-r6/candidate.zip` 已构建成功：53,760,516 字节，SHA-256 `bc5b57348f4dd865c53078837e63c35f3316fd51034f1a5ed8a9a7ce6a5e63e0`。精确 manifest 哈希见 `ci-frozen-candidate-r6.json`。

如果用户再次允许一次限定测试，执行范围仍与 run 19 相同：仅现有临时分支、合成数据和隔离 Windows runner，整次最多 25 分钟，不改 main、不发布或部署、不使用真实数据或模型密钥、失败不自动重试。使用 r6 源码和产物新建该次精确记录，不复用 run 19 的授权。
