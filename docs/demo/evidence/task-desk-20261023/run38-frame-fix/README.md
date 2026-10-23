# Run38 screenshot06 取景修复候选（未原生重验）

基线 `382ab03c622ef7927ac3935598c3e8b7da7aaf79`。本轮仅driver工具修复、必要离线检查及普通开发分支封存，不启动浏览器或CI，不改产品、字体、workflow、原生权限或预算。旧run38仍FAIL，不重跑。

## 已证失败与边界

父级通过正常授权消费者独立读取run38新原ZIP，399869B／官方SHA256 `2c3dbd75a28a0f40ec4e8b59e8a4b37215f9305bb3ec675852ddcbfcdeb9cbbf`，报告确定失败为 `COLLABORATION_1200` screenshot06前原完整可见断言：`dispatch-items` top458.344、bottom1021.406，原viewport高1000，底部超出21.406px。scrollIntoView受scroll-padding影响是原证据支持的取景原因，没有据此改产品。

父级限定核实：实际仅01服务入口、05协同空态两张PNG；1200两链接mouse／Enter／目标focus／随后Tab／Back四项通过；双方GET各4、POST0，无pageerrors／violations；cleanup5.483s，CLOSED／REFUSED／完整自有进程树退出。390、UNKNOWN／在途guard、899／900／1060断点未执行。前述为父级原件核验来源，本执行器未重取ZIP／log，也不冒称自己已看新图或清理失败。

## 最小工具补丁

新增 `dispatch_frame_delta` 与 `frame_dispatch_records`，只在06图compose之后调用一次，原 `visible_in_viewport(dispatch-items)`、协同几何、字体和capture断言仍保留。新增标准库math，无第三方依赖。

实际测量required组：夹具标识、两lane原标题和完整警告、分派按钮／状态／items及两张原卡。对每组元素取真实矩形，合法整体滚动整数区间为 `ceil(maxBottom-(1000-16)) <= delta <= floor(minTop-16)`；选择离0最近的合法整数，一次整体scrollBy，不改内容或viewport。无法完整容纳时拒绝，不缩字／截断／删警告／放宽断言。已知bottom1021.406得到38px，避免小数滚动被取整到37而再露底。

滚后重新测量：全部组的可见性、四边、原1200×1000 viewport、16px上下边距及请求增量0。记录请求scroll delta和实际scrollY delta；若浏览器限位，必须以滚后实测断言决定结果，不以请求量宣称成功。此滚动只为06截图取景，不回填先前原生回访落点。

未加入可选failure-visual截图接线，保留原错误与清理路径，不把本候选写成已有失败图。

## 实际离线检查

当前driver SHA256 `a073ffbe6a630c5a109d70bdc43cc8fd5a51a355e2db5edd8bdd44112648279e`。`offline-checks.json`保存12个定向纯检查：已知超出量求38px／滚后满足16px、已完整可见不再滚、内容过高／viewport变化／缺组／非有限矩形拒绝、顶部裁剪整体下移、实际helper在机械page上只滚一次并重测、滚动限位／横向溢出／请求增量仍拒绝，以及实际内嵌JS仅编译不调用。它们不是12个pytest、真实浏览器或像素通过；除父级报告的dispatch两数字，其他矩形是明示机械夹具，不是假称原图几何。

反向移除两helper、math及一处call后，整个driver与基线逐字一致。其他所有原函数完整保留，仅collaboration_observation多一call；产品两页、字体helper、workflow、supervisor及发布最终化源码均未变，未添加collection ID、未全回归。90s工作清理／85sworker／360s发布、GET每侧≤39／POST0、10文件8MiB全部保持。

本候选仍保留原run38门，尚未准备／授权下一运行绑定；不得直接拿新SHA重跑38或自动投39。后续须父级复审，再依据实时下一编号及新精确来源另行绑定。无真实模型／业务、Windows或用户电脑动作，未改main。
