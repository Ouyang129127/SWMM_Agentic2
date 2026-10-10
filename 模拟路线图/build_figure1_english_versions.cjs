// Build two English derivatives of the existing, unchanged Figure 1.
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('C:/Users/ouyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = __dirname;
const source = path.join(root,'agent_collaboration_logic_morandi_vertical_v2_20261008.html');
const translations = new Map([
 ['SWMM–CA2D 事件中心型诊断工作流','SWMM–CA2D Event-Centred Diagnosis Workflow'],
 ['关系证据构建 · 机制解释 · 引用核验 · 受约束报告','Relational evidence · Mechanism assessment · Reference checks · Reporting'],
 ['前置计算 / INPUTS &amp; SIMULATION','INPUTS &amp; SIMULATION'],
 ['用户任务与模型条件','User task and model inputs'],
 ['SWMM 管网 / CA2D 地表 / 降雨情景','SWMM network / CA2D surface / Rainfall'],
 ['情景准备与耦合模拟','Scenario setup and simulation'],
 ['模型结构与保存结果','Model structure and saved results'],
 ['节点 · 管段 · 地表过程','Nodes · Links · Surface time series'],
 ['工作流管理：阶段调度 · 状态与任务记录','Workflow management: Stage coordination and task records'],
 ['反馈与用户参与','FEEDBACK &amp; USER INPUT'],
 ['可追溯产物 / 来源与版本绑定','TRACEABLE ARTIFACTS'],
 ['事件检测 · 局部拓扑 · 同期水力过程','Event detection · Local topology · Hydraulic time series'],
 ['确定性提取与关系组织','Deterministic extraction and evidence organisation'],
 ['事件证据包','Event evidence package'],
 ['证据索引 · 对象与时窗','Evidence IDs · Objects · Time windows'],
 ['来源绑定 · 任务证据快照','Source binding · Evidence snapshot'],
 ['四问驱动 · 机制比较 · 联合解释','Four questions · Mechanism comparison · Joint explanation'],
 ['LLM 解释 / 竞争机制 / 缺口与补证请求','LLM reasoning · Alternatives · Gaps and evidence requests'],
 ['结构化诊断','Structured diagnosis'],
 ['过程解释 · 机制状态','Process explanation · Mechanism status'],
 ['引用 · 竞争解释 · 证据缺口','References · Alternatives · Evidence gaps'],
 ['引用核验 + 配套结构与对象绑定检查','Reference checks + Structural and object-binding checks'],
 ['确定性检查，不替代因果有效性评价','Deterministic checks; causal validity assessed separately'],
 ['核验记录','Verification record'],
 ['通过项 · 缺失引用','Verified items · Missing references'],
 ['错误反馈 · 诊断版本绑定','Error feedback · Diagnosis version'],
 ['检查通过','Checks passed'],
 ['结构化诊断 + 确定性数值与图表','Structured diagnosis + Computed facts and plots'],
 ['LLM 叙述 / 事实绑定 / 地表表现关联','LLM narrative · Fact binding · Surface associations'],
 ['报告材料与生成记录','Report materials and records'],
 ['事实文本 · 图表 · 叙述','Facts · Plots · Narrative'],
 ['数值绑定 · 来源与版本检查','Numeric binding · Source/version checks'],
 ['初步 / 修订诊断报告','Initial / Revised diagnosis report'],
 ['事件解释 · 图文结果 · 未解决问题','Event explanations · Plots · Unresolved questions'],
 ['检查失败修正','Check failure recovery'],
 ['反馈错误 → 修订诊断','Error feedback → Revise diagnosis'],
 ['持续失败：保留错误并暂停','Repeated failure: Save errors and pause'],
 ['按需补证工具','Evidence retrieval tools'],
 ['读取已保存模拟结果','Read saved simulation results'],
 ['按对象 / 指标 / 时窗提取','Extract by object / Metric / Time window'],
 ['新增证据绑定至原任务','Bind new evidence to the existing task'],
 ['补充证据','New evidence'],
 ['用户确认继续补证','User approval'],
 ['有可执行的证据请求','Executable evidence requests available'],
 ['不默认自主扩展调查','User decides whether to continue'],
 ['确认后执行','Execute after approval'],
 ['无可执行请求或用户不继续：保留本轮报告与未解决的证据缺口','No executable request or user stops: Retain report and unresolved evidence gaps'],
 ['管网—地表联系：节点注入网格及积水过程关联；不表示已实现地表水源贡献追踪。','Network–surface association uses injection cells and surface time series; source attribution is not performed.'],
 ['主流程','Main flow'],['产物记录','Artifacts'],['检查修正','Check repair'],['补证调查','Evidence retrieval']
]);
function translate(html){
 html=html.replace(/<!--[\s\S]*?-->/g,'').replace('lang="zh-CN"','lang="en"');
 html=html.replace(/(<text\b[^>]*>)([\s\S]*?)(<\/text>)/g,(all,a,b,c)=>a+(translations.get(b)??b)+c);
 html=html.replace(/<title>[^<]*<\/title>/,'<title>SWMM–CA2D Figure 1 — English versions</title>');
 html=html.replace(/(<title id="fig-title">)[^<]*(<\/title>)/,'$1SWMM–CA2D Event-Centred Diagnosis Workflow$2');
 html=html.replace(/(<desc id="fig-desc">)[\s\S]*?(<\/desc>)/,'$1Four core modules build evidence, assess mechanisms, check references, and generate reports. Failed checks return to diagnosis. After an initial report, approved evidence requests retrieve saved results for a revised diagnosis. Unresolved gaps are retained.$2');
 html=html.replaceAll('"Microsoft YaHei","Segoe UI",Arial,sans-serif','Arial,"Segoe UI",sans-serif');
 html=html.replace('font-size:28px','font-size:26px').replace('font-size:21px','font-size:19px').replace('font-size:17px','font-size:15px').replace('font-size:15px;fill','font-size:13px;fill').replace('font-size:13px;font-weight:600','font-size:12px;font-weight:600');
 html=html.replace(/<p class="note">[\s\S]*?<\/p>/,'<p class="note">Morandi palette retained from the existing figure. Verification and supporting structural checks are grouped by function. Reference traceability and causal validity are assessed separately. This offline figure uses no external scripts or fonts.</p>');
 return html;
}
function documentShape(x,y,w,h,cls='data'){
 return `<path d="M${x} ${y}H${x+w}V${y+h-9}Q${x+w*.75} ${y+h-22} ${x+w*.5} ${y+h-9}T${x} ${y+h-9}Z" class="${cls}"/>`;
}
function cylinder(x,y,w,h,fill,stroke){
 const ry=9;
 return `<path d="M${x} ${y+ry}C${x} ${y-ry/3} ${x+w} ${y-ry/3} ${x+w} ${y+ry}V${y+h-ry}C${x+w} ${y+h+ry/3} ${x} ${y+h+ry/3} ${x} ${y+h-ry}Z" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/><ellipse cx="${x+w/2}" cy="${y+ry}" rx="${w/2}" ry="${ry}" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/>`;
}
function symbols(html){
 // Shift the lower workflow to make room for an explicit check decision.
 html=html.replace(/<(?:rect|text|path)\b[^>]*>/g,tag=>{
  if(/\sy="/.test(tag)) return tag.replace(/\sy="([\d.]+)"/,(_,n)=>` y="${+n>=890?+n+80:n}"`);
  if(/\sd="/.test(tag)) return tag.replace(/\sd="([^"]*)"/,(_,d)=>` d="${d.replace(/([MLQCT])([\d.]+) ([\d.]+)/g,(_m,c,x,y)=>c+x+' '+(+y>=890?+y+80:y)).replace(/V([\d.]+)/g,(_m,y)=>'V'+(+y>=890?+y+80:y))}"`);
  return tag;
 });
 html=html.replace('viewBox="0 0 1280 1350"','viewBox="0 0 1280 1660"');
 html=html.replace('<text x="352" y="651" class="small">New evidence</text>','<text x="237" y="673" class="small" text-anchor="middle">New evidence</text>');
 html=html.replace('<rect x="62" y="153" width="326" height="82" rx="7" fill="#f8f5ef" stroke="#cbbdac"/>','<path d="M78 153H388L372 235H62Z" fill="#f8f5ef" stroke="#cbbdac"/>');
 html=html.replace('<rect x="850" y="153" width="366" height="82" rx="7" fill="#f8f5ef" stroke="#cbbdac"/>',cylinder(850,153,366,82,'#f8f5ef','#cbbdac'));
 html=html.replace('<rect x="955" y="395" width="260" height="88" rx="7" class="data"/>',cylinder(955,395,260,88,'#e7e0eb','#a798b2'));
 for(const [y,h] of [[558,90],[735,88],[987,88]])html=html.replace(`<rect x="955" y="${y}" width="260" height="${h}" rx="7" class="data"/>`,documentShape(955,y,260,h+14));
 html=html.replace('<rect x="930" y="345" width="310" height="688"','<rect x="930" y="345" width="310" height="780"');
 // Agent modules use the predefined-process symbol (double side rules).
 html=html.replace(/(<rect x="420" y="(380|540|720|970)" width="460" height="(\d+)" rx="9" class="agent"\/>)/g,(_all,rect,y,h)=>rect+`<path d="M432 ${+y+1}V${+y + +h-1}M868 ${+y+1}V${+y + +h-1}" fill="none" stroke="#7c8e8b" stroke-width="1.2"/>`);
 html=html.replace('<path d="M650 835V970" class="main"/>','<path d="M650 835V850" class="main"/><path d="M650 910V970" class="main"/><polygon points="650,850 750,880 650,910 550,880" fill="#ded6bd" stroke="#aa9b72"/><text x="650" y="885" class="body" text-anchor="middle">Checks pass?</text>');
 html=html.replace('<text x="667" y="865" class="small">Checks passed</text>','<text x="667" y="944" class="small">Yes</text>');
 html=html.replace('<path d="M420 777H380V567H420" class="repair"/>','<path d="M550 880H380V567H420" class="repair"/><text x="405" y="869" class="small">No: Repair</text>');
 html=html.replace('<path d="M345 777H371" fill="none" stroke="#9b7861" stroke-width="1.3"/>','<path d="M345 777H380" fill="none" stroke="#9b7861" stroke-width="1.3"/>');
 html=html.replace('<rect x="420" y="1150" width="460" height="100" rx="24" fill="#d8cfc4" stroke="#9d8f7f" stroke-width="1.4"/>',documentShape(420,1150,460,114,'reportDocument'));
 html=html.replace('</style>','svg .reportDocument{fill:#d8cfc4;stroke:#9d8f7f;stroke-width:1.4}</style>');
 html=html.replace('<rect x="130" y="1150" width="215" height="100" rx="8" fill="#ded6bd" stroke="#aa9b72"/>','<polygon points="237,1145 362,1210 237,1275 112,1210" fill="#ded6bd" stroke="#aa9b72"/>');
 html=html.replace('<text x="237" y="1186" class="head" text-anchor="middle">User approval</text>','<text x="237" y="1204" class="body" text-anchor="middle">Retrieve evidence?</text>');
 html=html.replace('<text x="237" y="1215" class="body" text-anchor="middle">Executable evidence requests available</text>','<text x="237" y="1226" class="small" text-anchor="middle">Available and approved</text>');
 html=html.replace('<text x="237" y="1238" class="small" text-anchor="middle">User decides whether to continue</text>','');
 html=html.replace('<path d="M420 1200H345" class="query"/>','<path d="M420 1200H386V1210H362" class="query"/>');
 html=html.replace('<path d="M237 1150V1109H82V580H130" class="query"/>','<path d="M237 1145V1109H82V580H130" class="query"/><text x="249" y="1090" class="small">Yes</text>');
 html=html.replace('<rect x="420" y="1275" width="795" height="46" rx="6" fill="#f0ece5" stroke="#d8d1c7"/>','<rect x="420" y="1295" width="795" height="70" rx="35" fill="#f0ece5" stroke="#d8d1c7"/><path d="M237 1275V1330H420" class="query"/><text x="274" y="1318" class="small">No / Stop</text>');
 html=html.replace('<text x="817" y="1304" class="body" text-anchor="middle">No executable request or user stops: Retain report and unresolved evidence gaps</text>','<text x="817" y="1324" class="body" text-anchor="middle">Retain the current report and unresolved evidence gaps</text><text x="817" y="1347" class="small" text-anchor="middle">End of the current investigation round</text>');
 html=html.replace('x="640" y="1359"','x="640" y="1410"');
 // A dedicated shape legend supplements the existing line legend.
 html=html.replace(/(<path d="M270 1392H321"[\s\S]*?)(<\/svg>)/,(_all,legend,end)=>
 `<text x="62" y="1450" class="tag">FLOWCHART SYMBOLS</text>
 <path d="M78 1475H213L199 1519H64Z" fill="#f8f5ef" stroke="#a99a88"/><text x="139" y="1503" class="small" text-anchor="middle">Input / Data</text>
 <rect x="244" y="1475" width="177" height="44" class="agent"/><path d="M256 1475V1519M409 1475V1519" stroke="#7c8e8b"/><text x="332" y="1503" class="small" text-anchor="middle">Subprocess</text>
 <polygon points="503,1473 565,1497 503,1521 441,1497" fill="#ded6bd" stroke="#aa9b72"/><text x="503" y="1502" class="small" text-anchor="middle">Decision</text>
 ${cylinder(603,1475,153,44,'#e7e0eb','#a798b2')}<text x="679" y="1506" class="small" text-anchor="middle">Stored data</text>
 ${documentShape(797,1475,160,44)}<text x="877" y="1501" class="small" text-anchor="middle">Document</text>
 <rect x="1003" y="1475" width="182" height="44" rx="22" fill="#f0ece5" stroke="#a99a88"/><text x="1094" y="1503" class="small" text-anchor="middle">Start / End</text>
 <text x="62" y="1560" class="tag">CONNECTORS</text>
 ${legend.replaceAll('1392','1596').replaceAll('1398','1602')}${end}`);
 return html;
}
async function exportVersion(browser,html,stem,label){
 html=html.replace(/<div class="toolbar">[\s\S]*?<\/div>/,`<div class="toolbar"><span>Figure 1 · ${label} · 2026-10-08</span><a href="${stem}.svg" download>Download vector SVG</a></div>`);
 const htmlPath=path.join(root,stem+'.html');fs.writeFileSync(htmlPath,html,'utf8');
 const page=await browser.newPage({viewport:{width:1440,height:1850},deviceScaleFactor:2});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(htmlPath).href);await page.evaluate(()=>document.fonts.ready);
 // Fit translated labels inside their unchanged nodes; no layout changes in version 1.
 await page.evaluate(()=>{
  const texts=[...document.querySelectorAll('#architecture text')];
  for(const t of texts){
   const x=+t.getAttribute('x');const y=+t.getAttribute('y');let max=0;
   if(t.getAttribute('text-anchor')==='middle'){
    if(x===650)max=420;
    if(x===1085)max=234;
    if(x===237)max=191;
    if(x===225)max=292;
    if(x===618)max=320;
    if(x===1033)max=336;
    if(x===817)max=747;
    if(x===640)max=1160;
   } else if(x===352)max=65;
   if(!max)continue;
   let size=parseFloat(getComputedStyle(t).fontSize);
   while(t.getBBox().width>max&&size>10){size-=.25;t.style.fontSize=size+'px';}
  }
 });
 const result=await page.evaluate(()=>{
  const el=document.querySelector('#architecture');const clone=el.cloneNode(true);
  const style=document.createElementNS('http://www.w3.org/2000/svg','style');style.textContent=document.querySelector('style').textContent;
  clone.insertBefore(style,clone.firstChild);const vb=el.viewBox.baseVal;
  clone.setAttribute('width',vb.width);clone.setAttribute('height',vb.height);
  const outside=[...el.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x<0||b.y<0||b.x+b.width>vb.width||b.y+b.height>vb.height;}).map(t=>t.textContent);
  const visibleChinese=[...el.querySelectorAll('text,title,desc')].filter(t=>/[\u3400-\u9fff]/.test(t.textContent)).map(t=>t.textContent);
  return {svg:'<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(clone),html:document.documentElement.outerHTML,outside,visibleChinese};
 });
 fs.writeFileSync(path.join(root,stem+'.svg'),result.svg,'utf8');
 fs.writeFileSync(htmlPath,'<!doctype html>\n'+result.html,'utf8');
 await page.locator('#architecture').screenshot({path:path.join(root,stem+'.png')});
 await page.close();
 if(errors.length||result.outside.length||result.visibleChinese.length)throw new Error(JSON.stringify({errors,...result,svg:undefined,html:undefined}));
 console.log(JSON.stringify({version:stem,errors,outside:result.outside,visibleChinese:result.visibleChinese}));
}
(async()=>{
 const english=translate(fs.readFileSync(source,'utf8'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  await exportVersion(browser,english,'figure1_english_original_layout_20261008','English · Original layout');
  await exportVersion(browser,symbols(english),'figure1_english_flowchart_symbols_20261008','English · Flowchart symbols');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
