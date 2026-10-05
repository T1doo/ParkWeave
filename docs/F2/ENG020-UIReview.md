# ENG020 独立确认审查与可审阅界面

基线50f7c4bd7fe6704e61bd2dc3c9a96d26f3e31f90，工作树起始干净。用户授权同工作区独立只读review及小范围前端美化，继续本地测试/commit，不push/CI/Library备份/上传/外部预约/真实provider。仓库及.agents未发现适用AGENTS.md/SKILL.md；沿用已读取agent-browser技能与缓存工具，不安装框架。依据原V1产品§3三个工作区、事项/材料/记录优先、角色范围和基本窄屏；原设计文件不修改。

## 独立审查

/root/confirm_review，6.1sol medium，固定da69..50f7增量；只读源码/tests/公开合成证据，没有写入、外网、API/模型、私有runtime或独立测试运行。发现一项P2：确认已成功而响应丢失，同身份另一页取消后原key重试，历史CONFIRM回执+当前RELEASED依法返回；卡片已释放，提示却根据action固定显示已确认。实际Chromium合成响应复现：22/23检查true，cancelled_confirm_replay_uses_current_state false，报告.runtime/eng020-review-repro.json。最小修复依据返回hold.state显示当前状态，原回执observed_state不同则标注历史回执，不将回放当重新确认；后端无修改。

审查未发现有证据的后端锁序/容量/期限/当前授权/tenant漏洞，不代表全时序证明。补实际PG不同key同占位双确认只提交一次、等待principal锁时撤权提交后拒绝确认；旧同key、确认取消竞争、版本、TTL、指纹及跨企业测试仍保留。park迁移及真实并发管理员协议、原生日期picker/Windows未验证。

## 界面范围与验收

保持现有纯HTML/CSS/JS、三工作区、主要ID和后端契约。绿色/暖白基调，字号/间距/边框/圆角与按钮统一，44px以上操作入口、键盘focus、reduced motion；导航明确当前位置。服务主张/目标/材料准备分层，资源三步提示、两列表单、主确认与次取消区分、本人记录卡片以状态/用途/区间/份数/历史期限/版本分层，UTC可读时间；不修改原始输入或API。合成环境、真实预约未确认/外部未受理/无线下履约仍可见。事实澄清可展开；工程JSON默认收起，错误/当前成功反馈可见且保留原防迟到响应守卫。

桌面1200与320/390实际Chromium截图保存在.runtime/eng020-ui-final/，不是DOM测试替代视觉检查。记录图像hash和实际检查结果见本片evidence；初轮图片.runtime/eng020-ui/保留。可审阅版本而非用户视觉签收，Linux视口不代表真实手机/Win11。资源过期/已取消用当前状态色，历史确认不冒充当前确认；规则/容量冲突和无权状态不可视觉隐藏。

实际测试范围：资源预检/占位/确认/取消/TTL5、双企业匿名容量/隔离、禁用按钮重复click、返回工作区清空旧草稿、本人刷新/reload、script纯文本；资料双角色补件/补正/核对/确认/重开与迟到请求；事实区块真实展开/补充仍UNKNOWN/取消保留历史；桌面及窄屏视觉、空态/错误/容量警告/成功反馈。最终成绩在Log/evidence，初始失败保留不计PASS。

F1未签收、F2 NOT_PASSED、R4 DISABLED、Win11/原生日期picker/完整36AT6EX NOT_RUN；Windows37324704568失败明细仍待用户，收到先F1。不增加组合确认、真实资源或来源许可判断。
