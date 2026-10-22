# run15原件与再批准页面账本版本修复

[run15](https://github.com/T1doo/ParkWeave/actions/runs/39760827816)，attempt1，源码 `cceae5be9ba1867443221725801b87cac390f330`，job119764269696，FAIL/exit1。依赖、wheel安装、字体门通过；实际来源预览22个可见文字节点均有合法CDP字体来源且缺字为空，静态684码点全覆盖。真实页面明确来源ADOPT201、资源交付预览200；旧批准fresh-key交付409拒绝正确。接下来显式PROPOSE页面POST409，尚无新APPROVE/交付/冷重启。28POST=24API初态+3DOM（含失败提出）+1旧批准负例；48GET/HEAD=36main+12readiness。

原result的stage仍是上一API负例标记`STALE_APPROVAL_NEGATIVE_API`，保留原值不改写。真实失败命令由responses最后DOM POST和failure原图确定。原件没有保存失败请求正文或后端原错误体；expected_revision0与账本3冲突是受测安装web控制流和红例推导，并非冒称观察到了请求正文。已有ledger3，切换再批准清空planApprovalView，而旧处理器默认`?.revision||0`。原`proposal-red.log`实际执行旧页面处理器失败0!==3；后端保持CAS严格拒绝。

修复只在用户明确PROPOSE点击的首次await前封存quote/body/身份/来源/Case/Run。只读取同Case当前ledger，严校验相同身份、Case、Run、scope、0..64安全整数revision与原quote/body未变后，使用该revision发出一次原key的显式提出。GET失败、403、畸形版本、Case/Run/scope/身份或quote变化均不POST；不调用会覆盖quote的历史Render，不续期、不自动重发或批准。APPROVE/REVOKE仍使用用户已读版本与原最终CAS，409照常保留。

本地22P是原9消费者+13个真实处理器的可控Node oracle；覆盖首次0/已有3、跨身份Case/Run/scope、负/超界revision、GET403、两段await中的quote变化/ABA、POST竞态409与原键恢复。不冒充浏览器/HTTP或再批准成功。中间20P不累加。本轮停止新CI，不准备run16；新产品代码尚待未来安装态真实页面及冷恢复实测。

三张原截图已逐张看：1200px来源影响和采纳内容中文可读、导航没有遮挡；失败页准确显示重新预检提示。未执行390px再批准视图，不能把原图当窄屏或整页视觉验收。仅第一代API/PG/wrapper全exit0、PG marker消失、监听拒绝、cleanup_errors空；没有第二代服务。完整专用API job log、官方ZIP全部6成员、三张原图和元数据保留并校验；原wheel在ZIP内。stdout PENDING_FINALIZATION不是PASS，按validation明确规范化后等于FAIL result；step summary正文未单独读取。

正式source、真实模型、Windows/native、P1–P5/TXT全链仍未验。main/权限/费用/凭据边界不变。

修复冻结源码 `a11c9a24b21570d41d52abcc71908da9e0d58915`，仅产品处理器/定向测试/精确目录变化，样式与批准后端未改。独审限定ACK，未转签浏览器通过。全局/四片精确collection9511cases/404files，四片2413/2323/2435/2340；既有分片不移动，新13案例沿原模块S2。724原字节指纹绑定冻结源码；目录3613 IDs/463883B，4096/524288 cap不变。collection不算执行。发布使用skip ci正常开发分支，未切新run号，也不安排第二次CI。
