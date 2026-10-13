# 冷建单的原 Run 读回恢复

接续 `fa15fee91796d642f8caef7f3f8b4e84e072e9b6`。父级确认上一三类修复方向，但严格verified门使正常intake/candidate-intake创建Run成功后仍持有登记，而原refresh未列入恢复入口。上一片不因此视为冷建单签收。

冻结源码 **311ca5438c22ae1474eed9811ed7cb12b0a45829**。原refresh现在仅允许当前登记全部属于Run域时进行非破坏GET，原身份/上下文校验仍适用。释放要求GET路径Run ID、GET响应ID及原成功POST响应Run ID精确一致；未知POST没有observed成功事实，普通GET不能代替原key核对，也不自动重发。原总览打开入口仍须先核对未决写。

真实冷链又发现资料建单的同类遗漏：prep-create已有prepCall GET轮询Run，但共享核验仅覆盖apiCall。两条原读取现共用runEntryReadProof；没有放宽其他GET、业务域或未知结果的释放标准。

新增owned PG/进程内ASGI桥测试从空页面执行完整原HTML handlers：intake POST→原refresh GET→真实总览打开Run→原目录读取→prep-create（另一个Run POST、prepCall GET、资料POST与完整资料加载）→原ADD_EVIDENCE表单及精确事件读回→真实总览按唯一标题回到正确资料项。只有DOM/存储/定时器为离线double；HTTP响应来自现有真实PG fixture及ASGI API，原函数不替换、不手工设置pending。合成worker按现有claim/finish执行，4次POST均明确用户步骤，无自动重发。该有界冷链覆盖两次Run建单和一份资料的首次追加，未扩展到分派、回执、取消或完整AT08/35。

根原件保留：精确fa15 Git blob的intake反例FAIL；仅加refresh后真实ASGI资料建单登记不释放的cold-red反例FAIL。首个桥脚手架在断言后未关闭readline，已识别并终止本测试自建Node子进程，原FAIL/rc-15保留；该窗口不作正常产品完成结果。第一次修复窗口52PASS/1FAIL为测试误选UUID排序第一项而打开另一Run，按真实唯一标题选择修正后53PASS。上述窗口不累加为最终统计，见证据中的failure-qualifications.json。

最终计数和独审结果见本报告下方及 [results.json](evidence/run-refresh-recovery-20261013/results.json)。既有安全approval仍false/null/null，main/F1/原F2及其他既有分支不改。浏览器、安全探针、Windows、完整冷链、生产/部署及真实模型/付费均NOT RUN；历史浏览器拒绝不重试。本片仅补原读回恢复路径，不宣称完整生命周期或冷全链签收。

最终冻结相关 **420 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，107.74秒**；52个完整原HTML模式及1个真实PG/ASGI有界冷链包含其中，不另加总。新增4个Node模式核intake/candidate成功恢复、unknown及错Run不能释放。旧手工pending25模式、上一独审及各中间窗口不作为本片新增冷链证据。

源码diff检查PASS；归档初次暂存diff检查实际FAIL/rc2，16处pytest原失败输出尾空白保留。归档该检查输出后，最终暂存检查仍FAIL/rc2，共32处（16原失败输出加16原检查回显）；最终检查记录仅留runtime，避免递归归档。6份含已识别fixture会话repr的失败日志/XML按显式SANITIZED_EXPORT导出，原件、字节与hash留私有runtime；失败结果及JUnit统计不改。

同一冻结源码独审 **10模式/92断言 PASS，0 FAIL/ERROR/SKIP**：9原HTML+HTTP/DOM模式72断言，1独立原HTML/owned PG/ASGI有界冷链20断言（pytest1PASS/2WARN），34次HTTP请求中4次POST。独立冷链也走通原建单、原GET核验、资料建单、材料追加与总览回到同一事项，无入口函数mock或手工pending；不与根420及旧窗口加总。两fa15实际红例原件保留。归档助手一次读取错误字段KeyError已留证并按实际清单格式纠正，属于metadata操作失败，未改产品测试结果。

父级有限接收996后已由 [FullOwnedLifecycle-20261013.md](FullOwnedLifecycle-20261013.md) 延伸两份新输入的同一Case最小业务链；本报告原420与独审10/92不作为后续源码验证、不加总。
