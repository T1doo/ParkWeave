# P2 原资源链隔离执行预览：有限验收

运行候选 `b05362117e19da18c343a401b3b3d8660c2825df`，基线 `24c6a9d2bfc2842fcbe2323b69f76f8117170f69`，合同先于实现（1c857e931e8c7054624918812d423334d22329ad/64c38a0f74d4d81f70e642e2fe662cc7436310d5，SQL闭包b81b8ecd9e8a58af0e0c8e094899ba675e3227bb）。352路径manifest SHA256 `2a0c2776ddd24e3632d6efc8376614dfe50594122baba9c8218b6c83048c0dfb`，1553实际AST函数诊断ID。

实际运行原P1四动作，原资料缺槽时保存FAILED并将P2列NOT_EXECUTED/未预演；P1成功后实际原resource_holds.preview/create、resource_combinations.confirm、case_resources.bind。固定两个现有授权合成规则、原READ/HOLD/PREPARE/EXECUTE权限闭包，17影子表及35精确SQL模板；未知模板不执行。每次生成新资源/占位/组合/Case/Run/角色UUID并rollback/close真实PG连接，仅独立SQLite产物持久。所有public表和逐行值（脱敏authorization_audit单列）及原P1库整文件不变，正式容量/占位/Approval/通知/原成果不变。

独立scope和attach属性兼容原P1存储；原P1根/历史不迁移、不清空。完整artifact/state和绑定/目标/覆盖写入独立不可变proof，改正文重hash不能省目标或修改资源结果。原Case/Run/资料revision/请求revision/双槽ID/version/hash/规则版本全部绑定。同key幂等，409拒CAS与换body；503前后只GET核对原key，明确新预演才POST。当前授权先于历史，source_atomicity=false、SNAPSHOT_MATCH/STALE不宣称全来源原子一致。

原bounded-planning页面提供P2明确预演/历史/GET恢复。原key句柄仅五字段，独立P2 storage key，8条/24小时；无正文/token，Case/身份/草稿变化和403清私有视图，迟到回复不复活。实际cold页面、不同API PID、320/390/1200宽度已在冻结测试中验证。保留全部原必需目标/unsupported目标及P3–P5未预演；正式Case未完成。

| 窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根冻结14完整模块 | 355 PASS，0FAIL/ERROR/SKIP，自然0 | 212.370 / 214.127898 |
| 独立 independent-api-corrected | 9 PASS、1 FAIL、0 ERROR、0 SKIP，自然1 | 13.931 / 15.278014 |
| 独立 independent-api | 0 PASS、10 FAIL、0 ERROR、0 SKIP，自然1 | 15.067 / 16.786610 |
| 独立 independent-browser | 2 PASS、0 FAIL、0 ERROR、0 SKIP，自然0 | 8.413 / 9.844744 |
| 独立 related-fourteen | 355 PASS、0 FAIL、0 ERROR、0 SKIP，自然0 | 211.753 / 213.627584 |
| 独立 relational-and-nonempty | 1 PASS、1 FAIL、0 ERROR、0 SKIP，自然1 | 5.358 / 6.600308 |
| 独立 relational-closed-observer | 1 PASS、0 FAIL、0 ERROR、0 SKIP，自然0 | 3.325 / 4.513938 |
| 独立 relational-consumption-corrected | 0 PASS、1 FAIL、0 ERROR、0 SKIP，自然1 | 2.742 / 3.832168 |

四个独立失败窗共13个观察器FAIL：安全note目录/原raw hold字段失配、未选P3–P5预期写错、对POST-only入口误用GET、私有Store观察器未在原正式入口前恢复。报告记录这些实际失败及新窗纠正，原件/hash保持私有，未改名为PASS，也不转移root计数。本SHA无产品FAIL，独审决策LIMITED_PASS。非空原资源探针实际先生成2个原hold与组合/receipts，正式occupied_peak为1，隔离为0；正式public逐值及旧P1 SQLite整文件不变。

[独审安全报告](evidence/p2-resource-execution-preview/independent/report.json) SHA256 `5de97650aedb2b4716aef1bf5e3504f0e33e00af704209558e306b6549dcb4f5`；[逐窗验证索引](evidence/p2-resource-execution-preview/verification.json)、[文件hash](evidence/p2-resource-execution-preview/artifact-hashes.json)、[失败原件hash](evidence/p2-resource-execution-preview/independent/private-failed-window-hashes.json)。

开发窗dev01 16PASS；dev02 16PASS/1缺失fixture导入ERROR（非产品结果），原日志/哈希保全；dev03 22PASS。后两新增故障/源换版测试及边界固定字段校验只计最终冻结窗口，不把开发结果转为冻结验收。diff --check的文件末尾空行已修正，原exit2元数据保留。不得把分窗口合计冒充一次全部通过。

本次仅签P1/P2原合成隔离预演。预览资源初始占用为0，不复制正式占位，容量不代表正式可用量；固定两资源、数量1、一小时窗口，不外推一般资源、组合、图或正式履约。P3–P5、完整AT14/全仓/Windows、WAL读者排斥、全来源/时间/非合作写入原子性、正式权限/发布/部署均不签。模型调用0，旧Windows Job/accounting修复不重做，资料包导出不重做。Dot unknown原因仍未定位。

root为唯一源码/Git写入者；所有独审窗口自然结束且自有资源关闭，获审源码之后仅追加安全docs/F2证据。候选普通push后以merge --ff-only整合dev；最终完整SHA及实际远端/未推送文件见整合末尾核验，不改main、强推、部署或凭据/权限/安全网络配置。
