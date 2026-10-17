# F2 文件材料导入：原资料链的可操作用户切片

从本地合成 TXT、MD、CSV、JSON 选择文件，查看候选全文，明确填入原材料表单，沿原“追加材料版本→获派专员核对→企业确认→生成并下载文本包”办理；普通 API 进程重启后可读回原资料。此切片对应 V1 产品设计 §4.2/§5.1 与阶段计划 F2-T01 的文件导入，不代表完整项目或真实验收完成。

新增 `POST /api/preparations/{preparation_id}/material-file-candidate` 只读解析接口，不存储文件、不抽取事实。读取当前企业本人已有的 SYNTHETIC preparation，复用原 READ/PREPARE、获派 REVIEW_ASSIGNED、精确 preparation_catalog 和 Case/Run/revision 检查；明确保存仍由原 ADD_EVIDENCE 实现。专员和企业确认逻辑、材料文本包下载、来源修订/采纳算法均复用。

仅支持 UTF-8（可 BOM），原文件 1–8192 字节；候选正文 1–4000 UTF-16 单位，超限拒绝而不截断。JSON 校验重复字段/结构深度/节点数并保留数字词法；CSV 统一带引号，保留单元格值；TXT/MD 按纯文本处理。原文件 SHA256 与候选正文 SHA256 分开显示。真实性始终 UNVERIFIED，文件指纹仅作来源线索，人工修改后的保存正文由原材料算法独立计算指纹。

## 源码与验证范围

- 开发分支：`dev/f2-material-file-import-20261017`。
- 基础交付：`9d362018320770e339ebe6609e24897700494ec4`；原指定 `db1084100a2477bbff3da8b49287c755dbc83c1b` 仍是祖先。
- 冻结源码：`650a2af1c495b8d9efe5daeb876138ac9cab41b8`；726 个源/测试/脚本/配置文件哈希。
- 9 个完整相关模块收集到197个唯一用例，其中新增68个解析/API、6个浏览器项包含在197内。最终实际 **197PASS / 0FAIL / 0ERROR / 0SKIP**，JUnit 400.314秒（pytest400.32秒）；未额外累加先前窗口。
- 只读独立审查关闭5项P2：请求大小、JSON数值、CSV空白、Unicode错误回显及极端指数异常；独立内存探针不累加197。

测试环境为 Linux、Python 3.12、隔离 PostgreSQL、普通 configured_app 子进程与 Chromium；使用合成身份和样例。实际选文件、原表单写入、专员核对、企业确认、真实下载字节比对、普通进程重启和新浏览器 GET 读回均纳入测试。浏览器故障注入覆盖原 ADD 成功响应丢失后的同 key 重试，以及旧文件200/403迟到、身份/事项 ABA 和撤权。

## 运行输入与未完成工作

普通启动使用已有 `PARKWEAVE_DSN` 和本机 `PARKWEAVE_MODE=LOCAL` 配置。实际使用需迁移后的现有数据库、当前合法会话、已有 SYNTHETIC preparation_id 及其 Case/Run、企业本人有效 READ/PREPARE、原获派 reviewer_id 有效 READ/REVIEW_ASSIGNED、与 preparation.service_id/service_version 精确匹配的有效 SYNTHETIC preparation_catalog；保存另需原 EXECUTE。本次这些前提由隔离合成夹具提供，真实业务环境的对应输入未提供/未验证。缺任一项沿原拒绝处理，本切片不创建业务身份、Grant、分派或目录。

正式资料接入尚缺已授权来源的记录结构及编号/修订、来源域和对象类型、当前主体授权证明、真实信任根及撤销/当前 head 协议、获准的只读宿主组合，以及正式已采纳方案与资源批准的来源映射。逐项字段和未实现接线见[正式来源报告](FormalPreparationEntry-20261017.md)。现有 formal preparation 入口仍关闭，IsolatedPlanApproval 测试 fixture 不能用于普通批准。NativeRunAccess 默认拒绝 permit/writer 继续保留。

Windows 原生正式 AT（含材料导入相关 AT05/AT06）、真实业务来源/批准、真实模型、部署和完整竞赛验收未执行。原项目还有未完成范围；本切片成功只证明现有本地合成资料链的工程可用性，不推定资格、外部受理、线下履约或 Case 目标完成。

## 保留的失败与复核

开发窗口分别为 dev-v1：52PASS/1FAIL（原恢复路由测试写错）；dev-v2：55PASS/4FAIL（新只读POST误记写入、原5秒浏览器断言和原命令完成时序）；dev-v3：70PASS/1FAIL（框架非法UTF8固定400与测试422预期不同，全部6浏览器通过）。每个失败窗口、对应源码和原始日志均保留；修复后再开新窗口，未重启或覆盖失败窗口，多个窗口不相加。归档dev-v2的pytest失败trace自带尾空白，整包`git diff --check`因此返回2；精确排除该原日志/XML后其余交付文件检查0，冻结产品源码检查0，原件与公开副本按映射保全。归档台账更新脚本曾误用list为dict，源码快照已完成，错误与后续修正也保留。

独审原先复现的JSON小数舍入和CSV字段尾空格丢失已修复；Decimal极端指数发现后改为数字语法验证，不做数值运算。实际HTTP覆盖8192/8193字节、原全局16385字节拒绝、孤立surrogate稳定422及非法原始UTF8稳定400。浏览器200/403迟到为客户端故障注入，不冒充真实撤权或真实来源变化。

完整[证据门](evidence/material-file-import-20261017/gate.json)、[最终JUnit](evidence/material-file-import-20261017/final-v1.xml)、[冻结清单](evidence/material-file-import-20261017/freeze.json)、[独立审查](evidence/material-file-import-20261017/independent-review.json)、[全部窗口失败记录](evidence/material-file-import-20261017/failure-ledger.json)与[导出原件映射](evidence/material-file-import-20261017/public-pairs.json)。公开副本仅脱敏随机合成会话，JSON键、JUnit节点与实际Git分支引用保持原样；原始件仍在`.runtime/material-file-import`及本窗口`/tmp`目录。

本片无新增模型调用、实际身份/Grant/分派/目录/批准/凭据、安全网络权限或费用，无部署或Actions查询；main及原开发分支保持原SHA。未知锁与无关进程未清理。

## 从页面使用

1. 在普通启动的 `/` 输入当前已有会话和本人原 preparation 编号，点击“只读打开已有记录”。
2. 在“从文件整理材料候选”选择合成样例并明确用途，点击“读取文件并查看候选全文”。
3. 核对全文与两个指纹后点击“填入下方原材料表单”；已有手工候选不会被覆盖，需本人先处理。正文可编辑，填入本身不保存。
4. 明确选择诉求摘要或材料目录，再点击原“追加材料版本”。两项材料仍由原获派专员核对、企业确认；随后使用原“生成当前材料文本包”和下载按钮。进程重启后重新只读打开原编号可读回。

推送后实际交付SHA、远端0/0及工作区结果记录于本次最终回复与`.runtime/material-file-import/delivery-verification.json`。
