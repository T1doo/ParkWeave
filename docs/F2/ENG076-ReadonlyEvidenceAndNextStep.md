# ENG076 现有只读证据与最小下一步

当前起点9430ae5，工作树起初干净。只核对已有安全证据、源码及本地注入合同；不访问网络、不迁移/导出备份、不运行原生Windows/CI。owner入口和setter仍暂停，未修改任何owner/ACL或放宽权限保持条件。

## SESSION/CONFIG：只读还能定位什么

ENG071唯一原生记录均为owner_same=true、acl_equal=false、control_equal=false、owner_defaulted_changed=false，事务在PERMISSIONS_COMPARE拒绝。安全记录没有保存before/after control整数或具体delta位，也没有原始ACL副本。现有本地记录无法还原实际差异位；不能把ENG072 mock出现的DACL_AUTO_INHERITED当作那次实测位。

目前生产inspect返回GetSecurityInfo(OWNER|DACL)副本的完整AclSize字节与GetSecurityDescriptorControl整数。已有只读比较器能按control XOR输出固定名称，分别区分有序完整ACE、revision、容量、保留/slack、NULL/empty；严格合同仍只有原完整字节和control保持才UNCHANGED，semantic_permission_change始终UNKNOWN，SACL内容NOT_QUERIED。

**无需owner/ACL写入的可行定位**：若在原生Windows有合法现有对象且已持有精确只读句柄，可对同一对象做两次独立OWNER/DACL读取，验证对象身份/读取稳定性，记录当前控制位及A/B差异固定名称，复制有效数据后分别释放SD。不请求WRITE_OWNER/WRITE_DAC/ACCESS_SYSTEM_SECURITY，不创建或修复目标，不改继承/特权；无效对象、重解析/竞态或读取拒绝则UNKNOWN/UNAVAILABLE。当前Linux环境未执行此原生读取。

该A/B是**无修改基线**，只能说明当前描述符是否稳定，不能替代owner修改前后证据。即使A/B相同，历史那次控制位变化和DACL访问语义仍未知；即使当前读到某位，也不能推断它是历史新增位。没有原始前后值时，追加解析代码不能凭空恢复历史信息。

因此当前仍不能证明DACL保持：实际完整字节和control均变，但未测有效ACE/具体delta。容量/slack或副本表示差异是可能来源，不是实际已证根因；OWNER-only调用最小也不保证结果满足原保留合同。不会屏蔽control位、裁剪字节来使原事务通过。

## Job：本地已证明与原生缺口

ENG074实际生产run/stop_tree注入测试证明：唯一时钟在终止前起算，身份读取、Terminate、原Accounting循环、三阶段观测及finish共享+5秒；查询前后与最终返回都有deadline gate。显式借用目标同handle核对PID/创建时间与innerJob membership，拒绝本次thread/parent/job句柄及同parent PID替代，未知/非成员/身份错/超期均FAIL，主退出17和timeout保留，finish先于自有句柄关闭。默认CLI/CI没有提供HeldDescendant，不自动开启候选。

本轮重新跑owned_job及synthetic_session_file模块：134PASS/5原生SKIP，确认当前代码与暂停边界；原ENG074的97PASS/4SKIP及相关76PASS保留原范围。源码指纹匹配当前提交。它们使用注入kernel/只读API，不能证明Windows API实际行为。

原生还缺同次受控执行中的以下证据：

1. 清理前已合法持有并核对目标descendant句柄，属于仍打开的本次innerJob；不能等run返回、Job关闭后才按PID打开。parent不能替代descendant。
2. BEFORE_TERMINATE、AFTER_TERMINATE、Accounting=0与目标Wait0=SIGNALED在同一原截止内的实际顺序；Accounting=0与目标LIVE必须保持FAIL，不拿TreeStopped盖过去。
3. primary17/timeout各自保留、无关精确进程仍LIVE、close前验收及借用句柄由caller在run完成后关闭。
4. Win32调用自身若阻塞，Python gate不能抢占。只能超期后拒绝成功，真实执行耗时仍须测。单个目标signal只证明该目标，不泛化为整树。

既有ENG071 normal descendantLIVE尚未复证；timeout历史PASS仍为那一轮范围。原S4 timeout/countNULL/coverageFalse单独OPEN，与Job精确目标观测不是同一个缺口；1403 collect和本地PASS都不能补成原S4已完成。

## 已选择的最小下一步

优先整理一个**完全不调用SESSION/CONFIG创建或owner helper的受控Job原生recipe候选**，把合法创建时保留的目标句柄及expected identity送入现有opt-in接线；先以注入API验收固定安全输出、共享预算、未知拒绝和关闭顺序。其后独立原生运行仅测上述normal/timeout/无关目标三gold，不依赖owner恢复，不启动整套生命周期或CI。本轮只确定方案，未运行原生或新CI；实际原生执行仍待单独安排，不需要把实现技术选项交给用户。

描述符方向不继续堆mock或猜修复：已有比较器足够解码将来合法只读A/B数据；有实际原生现存对象与只读访问时再测当前稳定性。没有原始前后数据就明确保留历史UNKNOWN。

**本轮没有必须申请的新权限操作。** 如果以后确须重建owner修改前后差异，需单独确认恢复一次固定SESSION/CONFIG首次新建对象的受控owner-only事务；仍保留原完整DACL/control断言，任何变化继续拒绝，不写业务数据，不修复既有文件、不提权或扩大对象。当前不执行也不提出夜间确认。日志/初始STATE/原子临时STATE/未启用FILES的集中清单继续待晨间决定；批准这些对象不等于批准忽略SESSION/CONFIG的DACL保持失败。

产品方面，ENG075失效校验摘要已由真实同Case浏览器及实际看图复核。此次源码检查未发现需要立即新增修复的同类缺陷，没有虚构新功能或重跑整套UI；同Case纠错/新版重核/显式重验仍是当前可体验价值。完整资格/真实履约/设备验收仍未交付。

固定证据：[ENG076 JSON](evidence/eng076-readonly-evidence-next-step.json)。F1未签收/F2并行、R4关闭、模型/预算0；Server非Win11，无阶段签收。
