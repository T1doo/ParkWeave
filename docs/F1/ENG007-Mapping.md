# ENG-007 冻结范围

基线384028bc00a3f7d38c54fa71ecf80eee0de768b7。只处理Checklist T05独立工程缺口，不扩F2、不实施Windows文件backend。

1. 固定官方HTTPS端点HTTP传输代码；所有本轮测试走明确MockTransport，无真实socket。LIVE须共享库owner批准的LIVE窗口及预留，运行CLI只提供合成链。
2. 独立共享PostgreSQL配额schema，provider account窗口总额+产品上限；产品角色绑定账号，受控数据库函数原子预留/发送标记/结算。usage未知保留额度，已发送无自动重试；只有确认未发出的预留可释放。无prompt/token/业务原文存入共享库。
3. 正常worker可显式选择合成模型规划，严格case.create proposal与持久输入相同，再经当前授权/fence可信动作，真实本地回执反馈。模型链最多两次请求，反馈失败不覆盖已知Case效果；独立心跳覆盖请求等待。两阶段结果持久化，失联发送不重发。
4. 实际临时PG、API/CLIworker、离线HTTP路径及并发/隔离/恢复工程测试。完整AT/EX NOT_RUN；真实模型预算/调用0，注入/共享部署/真实计费BLOCKED；Linux证据不等于Windows。

新规格来自V1全文+本轮委派，不声称收到原验收包。账号引用是owner配置的不透明标识，不能从密钥猜测；两个产品必须连接同一协调库/同一账号引用，实际跨产品部署尚无证据。
