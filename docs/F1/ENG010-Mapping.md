# ENG-010 R2账号发送速率门冻结

基线cc3458bd18704bcde1d96868d7346b8fe323f7fd，仅修R2已复现31即时发送问题。不做R3/R4，不改Windows/网络/真实凭据，不实际LIVE请求，预算0。

账号行锁统一预算/速率变迁。先预约rate slot（HELD，仍未发送），再原子转发送授权（DISPATCHED/IN_FLIGHT）；所有HELD及未决IN_FLIGHT持续占位，不按老timestamp自行过期。返回/timeout的COOLDOWN从DB完成时刻保守保留60秒，因此延迟发送/长请求不能靠旧预约时间释放slot；真实send syscall与PG不是分布式原子，计数针对平台发送授权/最迟本地完成时刻，不承诺远端收包时刻。已发/unknown不可退款重发；确定未发可release预算及slot。同work已证实未发的rate拒绝允许安全重试，sent work不重发。事件台账保留变迁。

数据库生产时间源clock_timestamp；SYNTHETIC-only owner测试时钟，低权限app不可写，LIVE忽略该clock。回拨停止发送，固定60秒右开窗口明确边界；rate_limit默认30可下调/0禁发，不能放宽到>30。LIVE owner须核实rate evidence，纯安全开关/预算/变量名存在性用Fake Mapping验证，不读取value/实际env/秘密，不创建真实LIVE worker。

确定性测试31st/60s边界、两产品/worker竞争、pending延迟发送、clock回拨、重启/同work重试、usage与已发unknown/未发release计数。旧31 gap变回归拒绝，历史gap evidence不改写。两真实产品须显式同协调库/账号；独立数据库无自动共享，实际部署未验。回归+Log/Convergence+commitpush即停。
