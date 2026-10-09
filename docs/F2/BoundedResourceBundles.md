# 已有授权资源的多会话组合候选

原产品§5.4、F2-T03要求一组必需资源同事务全部确认或全不提交。基线 `5a168116e52afbc360ba7178207f0d3f61318866` 只有两个不同资源的组合原语。先于实现冻结的[合同](BoundedResourceBundleContract.md)提交为 `67d59ceab8abfda673f98fff82a5931522382c39`；本候选解决3–8个本人已有占位的有界子条件，直接改变原实际PG容量记录。多会话可以使用同一已有资源的不同时段；不增添资源或Grant，不重做材料交付功能，不声称任意组合/完整F2已验收。

企业在资源区的本人占位列表选择3–8条，点击“明确确认这组占位”，查看所有成员实际状态并可显式整组取消。原单资源和两不同资源操作保留；新的组合需要每成员当前READ/HOLD、本人scope及核心READ/EXECUTE。全部资源稳定序锁后核对DB时点、期限、版本、启用、来源、窗口/缓冲及峰值容量；全部检查先于写入。任一不满足则原占位不被部分确认或自动取消。组/全部成员状态/不可变CONFIRM回执同事务，取消亦为全组事务；单成员不能退出已确认组。

初始CONFIRM回执保存scope、原排序后的成员manifest及hash（hold ID、resource ID/revision、区间、数量），不保存私有用途正文。旧两资源记录不回填为新manifest。新组合的读、恢复及Case关联必须核对初始证明与实际成员；缺少、篡改或不一致即拒绝。无新表、迁移、权限或安装；原roles.sql、权限注册表、Store迁移和Linux启动器字节未变。真实Linux TCP schema25库及正常schema26夹具都验证成功，非原生Windows证据。

显式Case关联可选验证后的整组，原资料版本、P1、当前资源权和P2重验均保留。取消或来源变化保留旧关联历史、显示需重验；不自动替代、取消别的组或完成Case。组确认是本地合成容量记录，真实预约仍NOT_CONFIRMED、外部未受理、线下无证据，方案级Approval与正式SLA仍未实现。

页面保存最多8个原actor/key/operation/对象ID句柄，没有token、用途、资源方案或请求body。未知结果锁住新的资源写入，冷刷新或实际API进程重启后仅GET核对原键/回执/当前整组。NOT_OBSERVED不是未提交证明，句柄不自动到期删除；损坏存储不降级发送。提交已成功而恢复409/网络失败仍保留句柄。身份、草稿、generation变化的迟到响应不填回当前视图；403清私有显示而保留原句柄。已确认后TTL为历史，取消后重放确认返回旧回执和当前CANCELLED，不重新占用容量。

同次冻结定向回归 **461PASS/0FAIL/0ERROR/0SKIP，247.683秒，2WARN**；304源码/测试/脚本hash零漂移。含34新API/PG、14真实HTTP/Chromium、原单/双资源、Case关联、资源影响/替代/目录竞争、受控计划/服务Case步骤/Case路径、执行回执与本地关闭兼容。新API覆盖3/8成员、同资源多会话、原键倒序等价、同/异键并发、与单释放竞争、双取消、当前撤权/角色/跨企业园区、等待到期、故障回滚、不可变成员/回执、损坏manifest、schema25原表复用和Case取消失效。真实页面覆盖3/8确认与取消、320/390/1200宽度、丢回显冷恢复、独立API进程重启、迟到身份/草稿响应、恢复失败保留句柄、损坏/未观察/8句柄、撤权隐私、实际HTTP重复写入及换版拒绝。

首轮原兼容测试遗留maxversion25断言（基线实际已26），必要相关三个测试断言补齐26。首轮新API有5个驱动错误（UUID/string与fixture CHECK），首轮页面暴露身份查询前busy未同步设置，已修正并复跑；原始失败日志均在私有`.runtime/resource-bundles`保留，公开[故障分类与hash](evidence/resource-bundles/failure-history.json)。先前90/14PASS不与最终461相加。两WARN为既有Starlette/httpx弃用与XDG运行目录回落。

候选 `20c9a387e821dac4481a46c40cc2b7fc1400cf5b` 已普通推送并[独立限定通过](evidence/resource-bundles/independent-review.json)，无阻断：独立111PASS（69.401秒）和额外5PASS（7.283秒），均零失败/错误/跳过，304hash无漂移。额外首轮驱动在已满窗口创建pair后误取不存在id，产品正确409；私有驱动改到可用窗口后5PASS，原失败保全。这些计数不与461相加。最新用户授权正常开发分支推送；集成及远端结果另记，不在实际操作前预填成功。全仓NOT_PASSED_NOT_COMPLETED；Windows/native、42AT/EX未签收，既有Windows失败未动。owner和现有principal/resource协作锁仍为信任边界，不保证无协作的管理员写入或外部事务；异议合同的库内xmin限制亦保持。无真实模型、通知、权限扩展、政策审批、Case完成、main/强推/部署或凭据安全配置改变。原资料包和异议证据保留原字节。

[机器记录](evidence/resource-bundles/verification.json)、[冻结日志](evidence/resource-bundles/compat-frozen.log)、[JUnit](evidence/resource-bundles/compat-frozen.xml)、[304源码hash](evidence/resource-bundles/frozen-source.json)、[3成员截图索引](evidence/resource-bundles/browser-3.json)、[8成员截图索引](evidence/resource-bundles/browser-8.json)、[真实API重启](evidence/resource-bundles/api-restart.json)。
