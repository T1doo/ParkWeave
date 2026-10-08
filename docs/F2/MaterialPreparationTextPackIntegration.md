# 已审材料文本包正常整合

独立候选 `b20a929d2a95d4978ce9fcef582f43b7c2aa7bb7` 已由父任务转述独审限定通过，无实质阻断。本实例获得 dev/f1-foundation 唯一写者授权；直接远端检查仍为 `604f722095574198e574c4742f2424339e0196c4`，未观察到活动 Git/测试进程。普通 no-ff 合并 `cf648b8217ffd2efa0d0723798183998d1adb1d5` 的两父分别为基线和已审候选，源码/测试/脚本/config 与候选没有字节差异。

**缺失的旧本地 a823a28 Windows Job accounting 修复仍在旧实例且未迁移。** 本次没有恢复、reset 或覆盖它，也不声称 dev 已包含该修复。未来只能在另外授权的传递核验后，从604分叉祖先正常合并并逐项核冲突。旧两个实例仍不push、旧对象与备份保留；新附件403后不重试、不换路。

父任务提供的独审范围：40个不同用例，首轮34PASS/2驱动计数FAIL；修正原页面后台GET计数后另次6PASS（包含4新增）。不合称同次40PASS。转述证据为真实Chromium剪贴板全文=UTF8下载，API/PG正文/版本/hash一致，成功输出前后46表不变；撤权、并发换版、身份/Case迟到响应、未知锁和读取失败拒绝输出。2WARN为TestClient弃用和cwd回退。此处归档父任务转述，不冒称本实例重新读过独审原件。

本实例必要整合检查：**同次21PASS/0FAIL/0SKIP/3WARN，38.63秒**，13项原页面真实HTTP/Chromium/PG及8项相关API/PG清单用例。候选web/test指纹前后相同；输出/截图放入新目录，原候选91项结果与截图不覆盖。额外WARN来自预载未修改测试模块以重定向证据目录导致anyio assertion rewrite提示；另两项是TestClient弃用及XDG_RUNTIME_DIR回退。所有本次HTTP线程和浏览器由原fixture退出关闭。

[整合机器记录](evidence/material-text-pack-integration/verification.json)、[JUnit](evidence/material-text-pack-integration/targeted.xml)、[日志](evidence/material-text-pack-integration/targeted.log)、[输出/三宽度截图索引](evidence/material-text-pack-integration/browser-output.json)。没有个别材料撤回接口，已导出副本不能撤回，最终读取后仅保证所列版本快照；正式政策、真实履约、Windows及完整全仓验收保持PENDING/未覆盖。无main/强推/部署/凭据权限/LIVE变更，不另行dispatch/rerun CI。

按授权普通push dev；实际最终源码/直接远端SHA另由私有 `.runtime/material-text-pack-integration-delivery.json` 核定，授权与本地提交不替代成功。
