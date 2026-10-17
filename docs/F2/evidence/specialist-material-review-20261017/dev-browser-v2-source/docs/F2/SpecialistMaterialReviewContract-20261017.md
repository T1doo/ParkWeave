# 原获派专员：相对最近一次审核的材料差异核对合同

基线`5a1771aa337b00c4366c46a40752d1442e8ebf22`，分支`dev/f2-specialist-material-review-20261017`。父独审有限准入215唯一/23新增、五个变更文件及合成本地原链；不声称父审重哈全部221归档对。

排除等价入口：企业materialVersion只比较未提交表单与当前同槽材料，且owner可见；专员当前/历史全文平铺及补正请求时基线、当时resolution均不是完整最近REVIEW资料包对当前资料包。双槽部分提交会保留CHANGES_REQUESTED，原待办/原复核门已支持，不重做。

本片仅为当前原获派专员提供只读差异入口。复用原READ、REVIEW_ASSIGNED、preparation/Case/Run/park/org、精确合成目录入口；不扩权限、身份、分派、目录、批准或事实采纳。原REVIEW/CONFIRM、全包审核、CAS/key与UNKNOWN流程不改；企业比较不能代替专员审核，专员比较也不自动判断补正充分、真实性、资格或当前审核通过。

最近REVIEW只存整包snapshot，包含材料UUID，但通用material_history不含旧UUID。专用读取在原scoped SHARE父锁内取有界历史，只取原latest的八字段，核每正文SHA、顺序和原snapshot算法，最多64条历史/1024双槽组合；必须唯一匹配最近REVIEW的整包指纹才展示旧包。没有REVIEW明确首次审核；有记录但不可唯一恢复明确不可比较，不按创建时间、文件名、上一版、请求基线或更早审核猜选，不改写旧事件或回填绑定。服务版本变化无法核对旧hash时同样不可比较。

新增一个可选GET投影，不改变原通用读取字段或审核写入。输出当前原专员ID、原prep/Case/Run/service版本、当前revision/整包hash、最近审核事件ID/revision/actor/hash、两槽匹配旧/当前全文及来源和确定投影指纹；无私有事实/权限明细。GET只SELECT/原作用域锁，不发布、持久化、执行或创建任何记录。

前端每次明确读取用原entry→该GET→原material-corrections→entry；固定当前会话代际、身份/角色、Case/Run/prep/revision/专员/service、两槽原材料ID/version/hash、最近审核事件和补正引用。每个await后重检当前上下文和所有原在途/UNKNOWN门；刷新、换身份/Case/工作区、再读及原写入使对照失效。当前403清私有，迟到旧200/403不覆盖新上下文；不新增持久化或恢复句柄，不强制增加原REVIEW审批条件。有限GET不承诺跨系统永久原子或未来有效。

复用已有逐行字面差异函数和纯文本渲染；两槽逐一显示旧/当前完整正文、来源类型/标签、材料版本/指纹、正文与来源分别变化；CR按明确转义。预算超出仍保留全文，未提供旧/当前材料明确缺失。不把差异hash或历史actor当授权。

仅以现有隔离合成授权实测普通configured_app/API/Chromium及原ADD→审核失效→本次专员只读对照→原REVIEW→企业CONFIRM→进程重启读回；覆盖当前撤权、改派、跨主体、迟到/ABA和UNKNOWN。正式来源协议、合法真实主体/目录/批准、专用reader/verifier与可信宿主接线、真实材料/履约及Windows正式AT仍缺，不以fixture或本片补齐。
