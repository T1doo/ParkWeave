# 无效恢复句柄清理

在已交付清单版本 0a185d81fa906dd38251ba19cbd4783efc4fd2a8 之后，修复原浏览器恢复句柄解析失败被忽略却未删除、可能占用八条容量的非阻断缺口。只修改原 readPrepRecovery：不存在的 key（getItem 返回 null）不处理；已存空字符串或无法解析 JSON 删除；JSON null/false/0/数组同样删除。存储访问或删除失败仍返回无可用恢复信息，不伪造授权或降级发送。字段/UUID/版本/24h/400字节和八条有效容量合同不变；有效句柄按字节保留，无关存储保留。

最终真实 Chromium localStorage 探针覆盖空字符串、坏JSON、null/false/0/[]删除，八条坏JSON释放容量，有效句柄字节保持、无关条目保持，八条有效保留且第九条被阻止；检查本身无POST。随后重走现有材料清单、提交丢回读/硬刷新只读恢复、新身份隔离、原专员REVIEW/企业CONFIRM，独立API核对实际材料正文和版本。探针只创建并删除自己的合成条目，原环境/备份保留。

最终API相关34PASS/14.21秒；本小补丁不重新声明完整Linux回归，2463PASS/9nativeSKIP明确只绑定前一冻结0a185d8源。当前源码与前一冻结差异仅web.html、浏览器driver两个文件，后端、测试、规则和权限源不变；最新collection仍2472项/89文件，旧精确keys全部保留。当前浏览器、定向API、源码前后指纹、独审及交付见[微补丁机器证据](../integration/RecoveryStorageCleanupEvidence.json)。独审先发现遗漏空字符串，修复并补入后重新跑最终浏览器，先前不含空字符串的PASS不作为最终证据。

本补丁不涉及schema/Grant/角色/发布/安装/模型/外部办理。F1未签收/F2并行、完整PR0/Win11未验收、R4关闭/预算0。普通dev推送及精确Server CI另记私有.runtime/recovery-storage-delivery.json；Server仅隔离工程测量。

最终浏览器PASS 47.221秒/45图，294冻结源前后0差异；独审无阻断，精确资料版本与原事件已独立API回读。此流程沿主driver窄图滚动局限，窄屏清单可见像素仍属于前一清单补充范围；本补丁storage边界依据实际localStorage断言。
