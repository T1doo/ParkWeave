from pathlib import Path
import base64,html
root=Path('submission/04-视频制作')
out=root/'审阅修订图'
out.mkdir(exist_ok=True)
def text(x,y,s,size=24,bold=False,color='#172d55'):
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(s)}</text>'
def box(x,y,w,h,fill='#f8faff'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#a5b6d6" stroke-width="1.5"/>'
def begin(ref=None,title=''):
    s='<svg xmlns="http://www.w3.org/2000/svg" width="1672" height="941" viewBox="0 0 1672 941"><defs><linearGradient id="bg"><stop stop-color="#edf5ff"/><stop offset="1" stop-color="#eeeaff"/></linearGradient><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0L9 4L0 8" fill="#637fe5"/></marker></defs><rect width="1672" height="941" fill="url(#bg)"/>'
    if ref:
        data=base64.b64encode((root/ref).read_bytes()).decode()
        s+=f'<image width="1672" height="941" href="data:image/png;base64,{data}"/>'
    if title:s+=box(232,0,1430,127)+text(270,58,title,38,True)
    if ref and title:s+=text(270,102,'企业技术交流活动 · PW-20261108-001',24)
    return s
def save(name,s):
    (out/(name+'.svg')).write_text(s+'</svg>',encoding='utf-8')
def rows(s,x,y,w,items,gap=77):
    for i,(label,value) in enumerate(items):
        yy=y+i*gap
        s+=box(x,yy,w,gap-12,'#edf2ff')+text(x+20,yy+37,label,23,True)+text(x+240,yy+37,value,22)
    return s
def edge(x1,y1,x2,y2,dash=''):
    return f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="#637fe5" stroke-width="2" stroke-dasharray="{dash}" marker-end="url(#arrow)"/>'
s=begin('AI参考图/C02-企业机会/C02-v1.png')
s+=box(267,512,350,370)
for i,t in enumerate(['入驻准备','研发协作','团队成长','业务拓展']):
    y=555+i*77
    s+=f'<circle cx="312" cy="{y}" r="12" fill="{"#3975ea" if i==2 else "white"}" stroke="#8499bc"/>'+text(343,y+8,t,24,i==2)
s+=box(649,535,1008,380)+text(680,579,'机会依据与下一步',29,True)
s=rows(s,672,598,958,[('需求触发','企业声明扩充研发团队'),('依据来源','企业资料与服务目录，版本待核'),('待核条件','资格、资料完整性与服务时效'),('下一步','专员复核后创建服务事项')],74)
save('C02-v2',s)
s=begin('AI参考图/C03-方案推演/C03-v2.png','候选方案条件核对')
for x,label,value in [(250,'资源参考小计','¥1,500'),(720,'资源参考小计','¥900'),(1193,'仅场地小计','¥1,200')]:
    s+=box(x,632,430,55,'#e8edff')+text(x+16,668,label,22,True)+text(x+295,668,value,25,True)
s+=box(250,722,1075,190)+text(275,763,'费用口径与状态',27,True)+text(275,809,'场地与设备小计；接待等未计费用待核。')+text(275,857,'A 满足容量与设备条件，时段可用性须核对。',23)
save('C03-v3',s)
s=begin('AI参考图/C04-变化影响/C04-v2.png')
s+=box(253,230,890,405)+text(280,276,'影响分析',30,True)
s+=box(280,409,185,80,'#edf2ff')+text(300,455,'需求变化',27,True)
for y,title,detail in [(312,'场地候选','容量仍满足 · 费用偏好比较'),(422,'设备复验','类型保留 · 新时段复验'),(532,'接待安排','分工保留 · 执行时段待核')]:
 s+=edge(465,449,520,y+40)+box(520,y,550,80,'#edf2ff')+text(540,y+31,title,25,True)+text(540,y+62,detail,22)
s+=box(1165,232,485,77)+text(1192,280,'待核候选 B',30,True)
s+=box(263,661,1380,79)+text(285,692,'企业偏好  满足条件后优先减少资源费用',25,True)+text(285,726,'A 资源小计 ¥1,500，B 小计 ¥900；两者新时段均需复验。',23)
s+=box(1312,764,330,95,'#e4edff')+text(1341,821,'复验后确认候选',27,True)
save('C04-v3',s)
s=begin(title='满足条件后的资源费用比较')
s+=box(70,150,1530,140)+text(100,198,'PW-20261108-003 · 20 人 · 15:00–17:00 · 预算上限 ¥2,000',28)+text(100,251,'企业明示偏好  满足条件后优先减少资源费用',27,True)
for x,title,cap,price in [(70,'原组合 A','48 人','¥1,500'),(855,'候选组合 B','24 人','¥900')]:
    s+=box(x,335,745,405)+text(x+30,395,title,36,True)
    for i,t in enumerate([f'目录容量 {cap}，满足 20 人需求',f'场地＋设备资源参考小计 {price}','新时段可用性 待复验','接待等未计费用 待核对']):
        s+=text(x+30,465+i*68,t,25)
s+=text(75,822,'资源小计相差 ¥600，属于案例候选比较。',28,True)+text(75,876,'时段复验与企业确认分别完成，保留原方案和选择依据。',25)
save('C04b-候选比较',s)
s=begin('AI参考图/C05-服务网络/C05-v1.png')
s+=box(248,150,936,510)
for x,y,t,w in [(275,340,'企业目标',210),(520,215,'资料条件',210),(520,340,'场地资源',210),(520,465,'设备资源',210),(785,465,'接待任务',180),(945,300,'候选方案',215)]:
    s+=box(x,y,w,78,'#edf2ff')+text(x+18,y+47,t,25,True)
s+=edge(485,379,520,254)+edge(730,254,945,339)+edge(730,379,945,339,'8 5')+edge(730,504,945,339,'8 5')+edge(875,465,1050,378)
s+=text(280,612,'实线 前置依赖    虚线 资源引用    点线 责任关联',21)
s+=edge(875,581,875,548,'2 5')+text(785,586,'执行人员',19)
save('C05-v2',s)
s=begin('AI参考图/C06-研发设备/C06-v1.png')
s+=box(1195,259,459,514)+text(1222,308,'服务条件核对',31,True)
for i,(label,val) in enumerate([('样件信息','材料与尺寸待提供'),('方法与精度','适用性待核对'),('操作资格','人员资质待核对'),('使用时段','协调后确认'),('报告要求','内容与交接方式待核')]):
    y=338+i*80;s+=box(1214,y,420,66,'#edf2ff')+text(1228,y+26,label,21,True)+text(1228,y+54,val,20)
save('C06-v2',s)
s=begin('AI参考图/C07-企业入驻/C07-v1.png')+box(650,102,1007,219)
for i,t in enumerate(['空间匹配','资料核对','合同衔接','物业准备','入驻确认']):
    x=676+i*192;s+=box(x,128,177,162,'#e6edff' if i==1 else '#f8faff')+text(x+58,184,f'{i+1:02}',36,True)+text(x+19,232,t,24,True)+text(x+29,273,'当前阶段' if i==1 else '待确认',20)
s+=box(670,527,960,69,'#edf2ff')+text(690,552,'网络与物业条件',23,True)+text(690,581,'协调 资源管理员    执行 物业团队    状态 待协调',21)
save('C07-v2',s)
s=begin('AI参考图/C08-跨园区/C08-v1.png')+box(252,478,1406,440)+text(280,526,'本地映射与验收准备',30,True)
s=rows(s,278,553,1350,[('资源标识','本地场地与设备 ID 待选择'),('角色授权','人员、权限与责任范围待映射'),('规则来源','政策适用范围及有效期待核验'),('业务时区','当地时区与日历条件待核对'),('系统接口','连接器、返回状态与异常处理待验证')],65)
save('C08-v2',s)
s=begin(title='从模型候选到可核对交付')
steps=[('模型候选',['目标与条件表','服务版本引用','候选任务图']),('规则核验',['满足 / 不满足','依据不足 UNKNOWN','逐项硬条件检查']),('人工确认',['比较费用偏好','核对来源与版本','授权人员决定']),('受控执行',['请求与事件账本','连接器与权限','外部状态核对']),('实际回执',['结果与依据','企业核对','纠正与历史归档'])]
for i,(title,lines) in enumerate(steps):
    x=50+i*326;s+=box(x,235,290,370)+text(x+20,289,title,29,True)
    for j,t in enumerate(lines):s+=text(x+20,369+j*70,t,23)
    if i<4:s+=edge(x+293,420,x+322,420)
s+=text(70,687,'候选输入 → 校验结果 → 授权动作 → 实际回执',31,True)
s+=box(50,743,1570,150,'#edf2ff')+text(75,791,'依据不足 / 结果未知 → 待核对与责任人处理',29,True)+text(75,850,'变化事件 → 影响集 → 保留 / 复验 / 候选替换 / 影响未明 → 修订确认',25)
save('T01-v2',s)
s=begin(title='部署边界与执行责任')
for x,w,title in [(50,340,'客户端'),(440,620,'园区受控服务'),(1110,510,'外部依赖')]:
    s+=box(x,220,w,560)+text(x+22,270,title,31,True)
for i,t in enumerate(['Windows 工作台','目标与岗位操作','会话与身份校验']):s+=text(75,365+i*90,t,25)
for i,t in enumerate(['API 与任务处理','目录版本、规则与授权','数据库、文件与事件账本','连接器、幂等标识与查询','UNKNOWN → 待核对 → 责任人']):s+=text(465,350+i*85,t,25)
s+=text(1135,350,'模型服务',30,True)+text(1135,405,'必要输入 → 候选建议',24)+text(1135,565,'预约 / 物业 / 工单系统',28,True)+text(1135,620,'业务状态权威来源与回执',23)
s+=edge(395,420,435,420)+edge(1065,380,1105,380)+edge(1105,435,1065,435)+edge(1065,595,1105,595)+edge(1105,650,1065,650)
s+=text(75,863,'资料与权限按职责限定；无法确定的外部结果交责任人核对。',28)
save('T02-v2',s)
print('10 SVG files generated.')


s=begin('AI参考图/C01-园区总览/C01-v1.png')
s+=box(1245,185,385,94,'#e9f0ff')+text(1263,222,'企业技术交流 · 当前事项',24,True)+text(1263,256,'40人 · 资源待确认',22)
s+=box(253,553,1404,104)+text(278,590,'当前事项',25,True)+text(278,627,'PW-20261108-001',19)
for i,t in enumerate(['目标表达','方案确认','资源核对','协同执行','结果归档']):
 x=650+i*215
 s+=text(x-48,627,t,20,i==2)+f'<circle cx="{x}" cy="580" r="10" fill="{"#3975ea" if i==2 else "white"}" stroke="#8fa3ca"/>'
save('C01-v2',s)
for name in ['C05-clean-plate','C04-clean-start','C04-clean-end']:
    s=begin()
    s+=box(55,55,1562,830)
    for i in range(3):s+=box(130,220+i*170,1412,130,'#f5f8ff')
    if name.endswith('end'):s+='<rect x="55" y="55" width="1562" height="830" rx="14" fill="none" stroke="#bdcafa" stroke-width="4"/>'
    save(name,s)
