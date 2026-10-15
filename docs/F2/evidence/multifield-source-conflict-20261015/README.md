# 双槽材料包确认：工程证据归档

最终验证源码 `30e8a60f8bffeb5f0b41bd3abb222526127c5433`；基线交付 `40092be0334a9891afcd478a9c0b1a1cfa54fe10`。本目录包含开发窗口、失败窗口、第一次冻结窗口及最终冻结窗口。索引的 source_sha 是最终源码参照，不能用来声称每份历史原件都在该 SHA 执行。

## 怎样复核

`index.json` 逐项列出私有原件和导出文件的相对路径、原件/导出 SHA256、大小及去敏次数。导出过程读取实际原件，原件保留不改。`audit.json` 是生产者 checkpoint；独立结论在相邻 `multifield-source-conflict-audit-20261015/final-gate.json`，不能把生产者自己核 hash 当独立审查。

`multifield-source-root/final-regression-verification.json` 核对最终选择：完整模块、完整 collection/JUnit 身份、无重复节点及同一冻结 SHA。若存在安全重跑，只能以整个失败模块排除/替换，并保留旧原始结果、原因和替代模块的新完整结果。正式选择不包含旧 WIP 分数、第一冻结的结果、partial 或无名中断占位。

`multifield-source-root/freeze.json` 是最终冻结；`freeze-6187ed2-historical.json` 保存第一次冻结字节。第一次 root-1-v1 的899PASS/1FAIL是29个新增测试函数没有登记原CI白名单，修正后97模块从头执行。旧backend/review窗口各一次精确自有SIGINT收口，原log/XML/collection及来源清单保留；未完成和中断占位不计有效PASS。CI元数据消费者补充、独审4pytest、37纯变异、29VM和6预算stub均单列。

完整 HTML 是 Node VM DOM→真实 HTTP/ASGI→自有 PostgreSQL。原 `.venv/bin/python` 与原命令/解锁规则保持；未安装缺失的 Playwright、未换解释器运行浏览器。所有 synthetic session 仅服务本地隔离夹具，不是产品凭据。

## 去敏和排除

精确已知合成 session 使用固定替换占位；仅 pytest fixture repr 文本行允许整行遮蔽。XML 先解析再处理文本和属性；JSON/JSONL 递归处理字符串值，遇到无效结构或残留私值即停止。含去敏的 JSON 用 ASCII 转义保留畸形 Unicode 测试数据；未发生替换时导出字节与原件完全相同。私值清单支持严格 list[str] 或已知 synthetic_private_values:list[str]、可选 provenance:str 的封闭字典，不把任意来源字符串当私值。

排除私值清单、PostgreSQL 数据文件、缓存、临时私有源码副本和无关 runtime。失败 smoke1 的数据库目录不发布，顶层失败日志/XML/结果仍保留。去敏只影响公开副本；原件 hash/大小受索引约束。独立审查须单独枚举来源和重建允许的转换，不直接调用导出器的转换函数。

Windows/Win11、真实浏览器、正式业务AT、真实产品模型/B0–B2、正式治理/批准主体、现实履约、生产和没有既有触发的本分支CI均未执行。真实产品模型调用0。main和旧开发分支只读；仅正常新开发分支推送，无强推、部署、新费用/凭据/安全权限或拒绝绕过。
