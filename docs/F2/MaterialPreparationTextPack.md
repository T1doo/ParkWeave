# 当前材料准备与补正文本包：最小合同

基线：604f722095574198e574c4742f2424339e0196c4。独立候选分支，不接入缺失的 a823a28 Windows Job accounting 修复，不合入 dev/main。

依据原 V1 产品 §5.3、F2-T01、F3-T01/AT23，企业或原获派专员在原资料准备页显式生成可复制/下载的 UTF-8 纯文本包。内容限定当前已分享的双槽材料、实际正文/版本/来源指纹、缺口、原补正说明与下一步；保留 Case/资料 revision/来源 hash 和合成范围声明。缺材料保留缺口，不提取未分享事实，不生成政策条件，不改变业务状态或保存新的评估。

生成和每次复制/下载均重新调用原 GET readiness，复用现有身份、READ/PREPARE 或获派 REVIEW 检查。首次生成必须匹配已展示的 Case/revision/source hash，输出前再次读取相同来源；复制/下载同样重新核验，不导出页面缓存。来源不同、请求失败、撤权、页面/身份切换、未知写入锁定、并发生成或迟到响应均拒绝并清除文本候选。只有最新请求可发布结果；纯文本以 textContent/textarea.value 展示，下载仅 text/plain。

检查是有限读取快照，不声称最后服务端读取至客户端复制之间能排除外部管理员变更；已复制或下载的历史副本无法收回。包明确只对应所列 revision/hash，不能用于声称当前政策资格、外部受理或 Case 完成。正式政策与真实履约 PENDING。无新 endpoint/schema/Grant/角色、业务 POST 或 native/LIVE 操作。

验证要求：实际原 API/数据库权限和无写入、双槽新版本/补正/缺口/事实私有来源隔离；真实 HTTP 与 Chromium DOM 的生成、复制、下载、撤权、来源变动、迟到响应/身份切换和窄屏。所有证据仅覆盖独立候选精确源码，不能继承历史回归或原生修复成绩。

## 独立候选验证结果

同次最终相关 **91 PASS / 0 FAIL / 0 SKIP / 2 WARN，87.23 秒**：13 项真实 HTTP/Chromium/PG 用例及 78 项原 API/PG 相关用例。企业和原获派专员均覆盖；并非两个不同数据库后端。下载 UTF-8 与所显示文本字节一致，六次输出相关请求均为原 readiness GET；准备事项/材料/事件/指派/原能力与资料权限行不变。当前流程不生成新的业务 POST；原接口拒绝时的既有审计不变。

覆盖实际 READ/PREPARE 撤权 HTTP403、同 revision 服务来源变化、两读取间材料变化、旧身份/旧 Case 迟到响应、并发生成、未知客户端操作锁定、未分享事实/竞争摘录隔离。1200/390/320 截图与无横向溢出通过，无 browser pageerror。源 web/test 指纹在最终运行前后相同。

证据见 [机器记录](evidence/material-text-pack/verification.json)、[同次 JUnit](evidence/material-text-pack/final-targeted.xml)、[日志](evidence/material-text-pack/final-targeted.log) 与 [输出/截图索引](evidence/material-text-pack/browser-output.json)。前三轮失败均为验证脚本问题，原因与准确 0/1、0/1、12/1 记录保留；不改 CSP 或应用授权。独立 HTTP 线程和浏览器关闭，无活动 Git/测试/PG 被观察到；PID1 下五个 PG Z 条目保留，不声称 /proc 条目全消失，不终止未知进程。

只核对上述范围，不继承旧全量/原生成绩。没有新业务后端/schema/权限，因此后端必要验证沿原 PG 应用角色合同；未执行 Windows 或另一个数据库后端。候选普通 push 后待独立交审，未审不合入 dev。旧 a823a28 修复和其证据仍缺失，附件403后未重试；正式政策/真实履约 PENDING，Case不自动完成。
