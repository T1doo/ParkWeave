# ENG014独立工程规格

依据V1全文中的F2协同语义新建；并非原附件包，整项AT-12/13/15/35与F2门仍NOT_RUN。测试仅SYNTHETIC。

PG初态：独立UUID fixture数据库，迁移9，parkweave_app无DDL与identity/Grant历史修改权，三企业两园区、显式合成服务及每企业专员。API和独立worker用最小环境；无provider请求。

Oracle独立读数据库：统计Preparation/evidence/events与canonical snapshot hash，检查Run SUCCEEDED而Case NEEDS_INPUT、external NOT_SUBMITTED/offline NO_EVIDENCE，槽位最新版本以及不可变旧行；按当前身份/Grant/assignment测试授权交集。补正/核对/确认/重开只经API，后端直接改表仅故障注入或可信fixture setup。

每次写需request key+当前revision。锁序为principal授权锁→请求key锁→单Preparation行；同key重放必须先重验当前角色/Grant/获派范围且返回当时回执，不再次应用。每次改变资料/reopen清除当前review hash，旧确认保留。专员核对必须两个当前材料槽齐全，人工说明不能为空；确认只接受当前核对快照。

API输入16KiB、两个固定槽、纯文本每项最大4000字符、单事项最多64条事件、来源摘要最大200字符、版本由数据库逐槽增长；未知字段/HTML不执行、不抓取来源URL。历史为SELECT/INSERT-only。一次提交事件记录包含actor、命令、revision、当前快照hash，不等同站外消息送达或履约。

重置由pytest独立PG fixture创建/销毁自己的UUID库；浏览器使用既有本机合成smoke库和新request key/新Run，不重置旧Case。浏览器会话仅当前页内存，公开证据无token/临时DSN。原来源hash/Windows guard/workflow保护检查后冻结全量回归。失败先留痕再修复，不删oracle或把NOT_RUN计PASS。
