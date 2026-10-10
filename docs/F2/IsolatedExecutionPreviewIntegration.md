# 隔离P1预览的正常整合记录

获审运行SHA `5c25aa08c7ab499764bc2aa145dd932ee8a2a417`，基线dev `f5f187fb1a390e724a3b471f82243425349b4f85`。独审LIMITED_PASS后，候选安全证据提交 `0a41e5ba694535db8a57f8468b427b85396a4b89` 通过正常push，再以`merge --ff-only`进入dev，正常push成功；[实际远端核验](evidence/isolated-execution-preview/integration-ff-remote.txt)确认candidate/dev均0a41e5b、main保持 `31e7acb7e53bb1ab6465b9daae59de28757f7583`。

5c25后只追加本任务docs/F2文档和安全证据，src/tests/scripts/pyproject无差异，346源码清单hash `3acd646c4a75308478dbacd0dcf5dc798f66bbdfda677ae8efb62ab88f82ca3a`保持。没有新runtime验收；270根PASS及独立六通过窗只归属于获审5c25源码。此整合记录随后仅文档提交，再正常同步候选/dev；最终精确SHA由会话末尾实际ls-remote记录，不将0a41e5b冒称最终文档HEAD。

普通fetch显式核dev，因为既有remote.origin.fetch仅main；没有改该配置、权限、凭据、安全网络、main、强推或部署。known `88403af18b95b361114b303c3fae636f286d91b4`仍为祖先，平台空codex-index-refresh锁inode1310816/0bytes未触碰，无挂起merge/rebase/cherry-pick/revert。本环境root唯一Git/source写入者；独立测试仅独有合成夹具，所有API/PG/Chromium已关闭。非忽略未推送文件须末尾实际Gitclean核验；ignored私有.runtime内故障原件、夹具结果和helper不会推送，也不删改失败原件。

完整AT14、Windows、全仓、现实Case完成及正式服务发布/部署仍NOT_RUN；最后source取样至SQLitecommit的无协作竞态OPEN。旧Windows Job/accounting修复未重做，资料包导出未重做；dot unknown原因未定位。无剩余本P1合成范围阻断，不能将本次LIMITED_PASS外推为一般工程执行。
