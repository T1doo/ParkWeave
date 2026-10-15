# WIP 联合预审 v1

尚未冻结，不签实现 PASS。共享 UI v3（7b7c1299…）与不可变候选相同；preview显示正文/source/分区匹配check/proofhash，异步hash完成后重核context，reset清勾选，当前403清私有预览，generation隔离迟到响应。新字段只经NoteCarryApply/独立patch；原Apply默认dump和fingerprint未加字段；原replay在新carry gate前且在当前auth后。

真实发现：成功carry的实际PG/API证明中，current_epochs/captured_epochs引用version改True/1.0并重算相关hash，完整_recovery_proofs仍接受；4纯内存反例均未被拒。backend正在新helper收紧类型/canonical比较，未修改旧note parser。原RED日志/JSON/XML保留。

旧v2 MANUAL阳性：真实材料MERGE_NOTE→原sourceADOPT→review/confirm/relink/reoffer/newreceipt/localREVALIDATE+P1–P5VERIFY→首次carry保正文→合法EDIT→原机会REFRESH→KEEP_AND_CONTINUE→next-hop→原第一keyGET，隔离snapshot实跑1PASS19.55秒。此为旧5目标/P1–P5 fixture兼容检查，不代六目标独测。旧卡UNKNOWN先失败，原REFRESH后可达；没有绕adoption_guard。新scope纠正receipt解释v3末尾快照字段把合法EDIT/CONT的ledger变化混进carry对比，原件不改；正式将两次carry分别即时比较。

首两探针窗口/harness错误和失败均保全并在JSON分列：v1 pytest ini覆盖sourcepath且capture名字撞builtin；v2显式bootstrap复制包后隔离成立。首v1日志中完整43字符session候选0；新窗口fixture私值专用0600登记。source-wip-v1整包仅为私有隔离运行，主归档必须排除此整树，保manifest、探针、结果和差分。

等待delta2+freeze后，新目录note-template-carry-review-formal准备16完整模块，实际fulltracked before/after与raw collection/JUnit核对；新carry预算/128和v2历史/epoch篡改分列，不迁旧分数。不扩一般迁移、发布授权或Windows/真实浏览器/正式AT/真实模型/生产验证。
