后端和测试已停写，根负责最终 Git 冻结、正式回归和整合。本 agent 仅修改 `src/parkweave/service_release_preflight.py` 与 `tests/test_service_release_preflight.py`，当前 23 项；精确文件 hash 及日志见 `backend-handoff.json`。

开发完整窗 21 PASS /43.93s，随后最后当前性修复的 3 项目标窗 PASS /7.32s（两项 expiry 窗口及原持久日志幂等/冷重启）。窗口有重叠、源码阶段不同，不能求和当完整冻结通过。首窗 4 PASS/16 setup ERROR 和 focus 3 setup ERROR 均保全；原因分别为未先确认资料、未引入原 ready helper 必需的标准 receipt fixture。均只修新测试夹具，不改原拒绝门或直接改 Grant。所有后续窗带根 shared_capture，合成会话值仅保留在本目录 0600 私有 registry，未打印/导出值。

当前目标从原 ACTIVE catalog/instance、同服务/owner_org/template family、当前权限和受审最新 head 取得；mapping 锁等待后及 Case 实际来源检查末尾各有界重核。模板 source 撤回/失效为 UNKNOWN 不可记录，owner/mapping 撤权为 403。原版本用 V4 frozen 历史和 immutable source 验证，当前 flag 再核实际撤回/配置状态；不倒造历史。合同语义与 Case 现状分列，title-only 新版本仍因原绑定实变需要重验；历史锁/六目标/业务事实保持。证据只写独立既有 ConsumerRepository schema，业务 PG 零写，原拒绝 authorization audit 例外单列。无新表、发布、迁移、回滚、真实模型、费用或权限扩展；Windows/真实浏览器/正式 AT/生产仍未执行。
