# 72c 静态独审与暂停窗口核对

源码：`72c1e2a8a3a28774d801b93735cca26f24f9597c`；五文件比较基线：`441674c5bfd06ffb64343a148ff85fc4a5cdd1c7`。

本次实际读取并重哈希740项输入，0漂移，详见 `hash-verification.json`。五文件及继承25c时序代码未发现新增静态阻断；本审查不授予完整验收。

R2原四XML共30条testcase记录：27个真实预期节点，17 PASS / 10 FAIL / 0E/S；另3条仅含time、无classname/name的中断残留不计PASS或unique。其余269个预期节点没有完成记录。日志进度点与XML suite计数交叉一致。

10项失败中，8项在ordinary API15秒健康就绪轮询阶段失败，尚未进入页面业务断言；2项分别在5秒断言内停SUBMITTING、LOADING。具体import/DB/HTTP/调度耗时环节和UI等待中的请求阶段仍Unknown，不称环境flake或已证明死锁。原/tmp子进程日志现已缺失；不得据此放松权限、ready、UNKNOWN门或生产锁/超时。

根线程R3串行10项95.091秒全通过结果已只读核对，只属于该窗口，不能抹去R2失败。

原独立31项的/tmp镜像及raw当前不存在。此前实际回执为6个PASS进度点、pytest退出-2（SIGINT）、513.677秒、余25项未完成；本轮未重新核验这些raw，也不计为本轮验收或31项通过。

NOT_RUN：本轮未运行pytest/Node/PG/API/browser/network；新31项镜像独测未启动；Windows、正式来源、真实业务和模型未验。只写本证据目录，未修改源、测试、脚本、合同或Git。

完整节点、失败分类、五文件SHA与因果限界见 `static-review.json`。
