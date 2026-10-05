# ENG-006 F1收尾冻结范围

基线3387aa2f5a2315440cf8d169f4391863bb4601ab；新建工程规格，不是收到的原验收包。

| 任务 | 本轮交付 | 实测边界 |
| --- | --- | --- |
| F1-T01 | Doctor/Setup/Start/Status/Stop/Test.ps1；只localhost，保护既有配置/数据，明确owner/app角色；新用户体验说明 | Linux静态/共享Python助手模拟；Windows执行NOT_RUN |
| F1-T05 | 官方Chat Completions格式离线适配边界：非流式、已知型号大小写、工具结构、限额、超时/429/截断/usage；LIVE fail closed | 合成HTTP传输/载荷，无真实账号/探测/API调用，无共享真实配额 |
| F1-T06 | 固定AT绑定/工程执行器/状态汇总及逐条F1清单 | 完整36AT/6EX维持NOT_RUN，工程pytest结果单列，禁止把mock/模拟作LIVE/Windows通过 |

生命周期脚本不安装数据库/创建持久凭据、不关闭安全策略、不覆盖env/config/数据库、不终止其他项目进程，不公开绑定。既有PostgreSQL服务及parkweave专用数据库/app角色由授权安装者准备；精确Windows依赖未实测，仅候选锁定。

本轮结束于回归、日志、commitpush、远端核实；停止新增工作，F1门不通过则不进入F2。
