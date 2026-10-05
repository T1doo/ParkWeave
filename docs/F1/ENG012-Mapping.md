# ENG012 Windows Server CI本地准备冻结

基线5185cf4b0a3973f1b7b486bc6adf43f478742db2。仅标准windows-2025待审查CI/PowerShell脚本、独立Server候选工程harness与本地Linux/静态验证。Actions访问拒绝未解除，本轮不访问Actions/重试gh、不换身份或路线、不推送workflow/不启动runner、不修改权限/凭据。无larger runner/cache action/artifact上传/部署/真实模型请求；Sim2Act成功不作为Park权限或验收证据。

预期runner原生Python3.12x64、PGBIN/PostgreSQL17 fresh loopback cluster，专用临时owner和parkweave_app角色，不使用预装service/data/密码、Linuxpgserver/容器/WSL。OS/版本/admin/UAC只读记录，不改策略。PowerShell生命周期、正常API/worker/本地浏览器和既有工程测试；来源仅合成，LIVE关闭。新建fixture可设置其自身私有ACL；已有对象/系统ACL不修。

独立Server harness复用当前已发布未启用文件候选的只读测试oracle，不绕过/修改Win11 probe main release11守卫、不spoof、不接入产品R4。实际Server执行NOT_RUN；Linux静态/guard通过不能算Windows通过。失败/缺权限/可选native能力缺失准确记FAIL/NOT_RUN，不把全拒绝当PASS。完成本地验证/Log/权限阻塞留档，保存本地提交供复核，不push。
