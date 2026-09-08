# SWMM-Agentic2 PPT 规划：证据约束型城市内涝诊断工作流

工作目录：`E:\SWMM_Agentic\SWMM-Agentic2`

适用场景：导师组会、论文选题汇报、阶段进展汇报、预答辩前技术说明。

核心表达：

> SWMM-Agentic2 不是“给 SWMM 加一个聊天界面”，而是把 SWMM-CA2D 的复杂模拟输出组织成可追溯、可核查、可解释的城市内涝诊断结果。

## 0. 总体叙事

整套 PPT 建议控制在 **14 页正片 + 3 页备份**。不要把所有技术细节都放上去。PPT 的任务不是替代论文，而是让听众在 8-12 分钟内记住三件事：

1. 城市内涝模拟结果很多，但直接解释很难。
2. SWMM-Agentic2 用工作流 Agent 把结果转成证据、诊断和核查。
3. 这个系统已经在大规模 SWMM-CA2D 案例上跑出可量化结果。

一句话主线：

> 从“模型能跑”，走到“诊断可信”。

## 1. 视觉风格

建议采用“科研极简 + 工程证据感”：

- 背景：白色或极浅灰，不用大面积深色。
- 主色：深灰黑文字。
- 辅色：蓝绿色表示水动力模拟，橙红色表示风险诊断。
- 每页文字：标题 1 行，正文不超过 3 个短句。
- 每页主视觉：只放 1 张主图，最多加 1 个局部放大框。
- 图表尽量用项目已有图，不临时堆图标。

统一术语：

- `SWMM-CA2D`
- `Agentic workflow`
- `Evidence table`
- `Diagnosis claims`
- `Verification`
- `Unsupported rate`

中文汇报时可对应为：

- SWMM-CA2D 耦合模拟
- 多智能体工作流
- 证据表
- 诊断结论
- 证据核查
- 无证据结论率

## 2. 推荐 PPT 标题

首选：

> SWMM-CA2D Agentic：面向城市内涝模拟的证据约束型诊断工作流

更论文感的版本：

> 面向 SWMM-CA2D 耦合模拟的证据约束型城市内涝 Agentic 诊断工作流

更组会感的版本：

> 从模型输出到可信诊断：SWMM-Agentic2 阶段进展汇报

## 3. 图片资产清单

### 必用图片

1. 最大积水深度图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_max_depth.png`
   - 用途：封面、第 8 页、第 10 页。
   - 建议：封面可以做半透明背景；正文页作为主图展示。

2. 最终积水深度图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_final_depth.png`
   - 用途：第 10 页或备份页。
   - 建议：和最大积水深度图做对比时使用。

3. Agent 协同逻辑图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\paper_assets\figures\agent_collaboration_logic_v5.svg`
   - 备用浏览器版：`E:\SWMM_Agentic\SWMM-Agentic2\paper_assets\figures\agent_collaboration_logic_v5.html`
   - 用途：第 6 页。
   - 建议：不要整图塞满一页后再加很多字；图本身就是主体。

4. 前端截图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\outputs\frontend-desktop.png`
   - 用途：第 13 页。
   - 建议：只展示“自然语言交互入口”，不要让它抢走“诊断工作流”的主线。

5. 降雨过程图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\outputs\rainfall_hyetograph.png`
   - 用途：第 7 页或备份页。
   - 建议：用于说明一次任务的输入，不要作为核心贡献页。

### 可选图片

6. CA2D 动画
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_animation.gif`
   - 用途：现场演示，不建议直接放进 PPT。

7. 另一次运行的最大积水图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain4__baseline__20260812_101435\ca2d\ca2d_max_depth.png`
   - 用途：备份页，用于说明系统可复用到不同降雨事件。

8. 站点图或模型原图
   - 路径：`E:\SWMM_Agentic\SWMM-Agentic2\models\suanliguanw_swmm_2d\raw\Site-Post.jpg`
   - 用途：如果老师希望看到“研究区域/模型对象”，可用于备份页。

## 4. 正片逐页规划

### 第 1 页：封面

页面目的：让听众立刻知道你做的不是普通程序，而是一个面向内涝诊断的研究系统。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_max_depth.png`

版式：

- 最大积水深度图铺满全页，透明度 25%-35%。
- 左下放标题。
- 右上放小号项目信息：`SWMM-Agentic2 / 2026`。

页面文字：

> SWMM-CA2D Agentic  
> 证据约束型城市内涝诊断工作流

底部小字：

> 从模型输出到可信诊断

口头讲法：

> 今天汇报的核心不是我做了一个聊天界面，而是我尝试把 SWMM-CA2D 的模拟输出，组织成可以追溯、可以核查、可以解释的内涝诊断结果。

注意：

- 不要在封面写姓名、单位、日期以外的长段背景。
- 标题要大，副标题要短。

---

### 第 2 页：问题从哪里来

页面目的：建立痛点。模型能产生很多结果，但工程诊断仍然困难。

主图：

- 建议用 3 个文件局部截图拼成一张横向视觉：
  - `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\swmm\node_flooding.tsv`
  - `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\swmm\links.tsv`
  - `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\surface_depth.tsv`

版式：

- 左侧 40%：大标题和 3 个短标签。
- 右侧 60%：三个结果文件截图叠放，像“原始输出堆叠”。

页面文字：

> 模型结果很多  
> 但诊断依据很散

三个短标签：

> 节点溢流  
> 管段负荷  
> 地表积水

口头讲法：

> 一次 SWMM-CA2D 运行会产生节点、管段、地表元胞等多类对象的结果。真正困难的地方不是只把模型跑完，而是把这些分散结果变成工程人员能判断风险的诊断依据。

注意：

- 右侧截图不要让人读清每个数字，只要形成“输出复杂”的视觉感。
- 这一页不要讲 Agent。

---

### 第 3 页：一句话定位

页面目的：把项目从“软件开发”提升到“研究问题”。

主图：

- 自制极简三段式流程图，不需要外部图片。
- 三个大块：`Simulation outputs`、`Evidence table`、`Verified diagnosis`。

版式：

- 中间横向流程，占页面中心。
- 上方标题。
- 下方一句解释。

页面文字：

> 从模型输出到可信诊断

流程文字：

> Simulation outputs  
> Evidence table  
> Verified diagnosis

底部小字：

> 让每条诊断都能回到模型证据

口头讲法：

> 我的核心定位是建立一个中间层。它不替代 SWMM 和 CA2D 的计算，而是在计算结果和工程诊断之间增加证据组织、规则诊断和结论核查。

注意：

- 这一页是整套 PPT 的“定海针”。
- 后面每页都要回到这条链路。

---

### 第 4 页：为什么不是简单迁移 EPANET-Agentic

页面目的：回答“这不就是把 EPANET 换成 SWMM 吗”。

主图：

- 左右对比图。
- 左：EPANET-Agentic 的对象简化成“供水管网”。
- 右：SWMM-CA2D 的对象简化成“排水管网 + 地表积水”。

可引用图片：

- 右侧可放：`E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_max_depth.png`

版式：

- 左右两栏。
- 左栏只放 2 行字。
- 右栏放小图 + 3 个对象标签。

页面文字：

> 研究对象更复杂

左栏：

> EPANET  
> 供水管网仿真

右栏：

> SWMM-CA2D  
> 管网溢流 + 地表积水

右侧标签：

> node  
> link  
> cell

口头讲法：

> EPANET-Agentic 面向供水管网，输出对象相对集中。我的对象是 SWMM-CA2D 城市内涝耦合模型，需要同时处理节点、管段和二维地表元胞，诊断链条更长。

注意：

- 不要贬低 EPANET-Agentic。
- 重点讲“对象和诊断任务更复杂”。

---

### 第 5 页：核心贡献

页面目的：在早期明确创新点，避免听众迷失在流程细节里。

主图：

- 三角形结构或三列结构。
- 三个关键词：`Tool-first`、`Evidence-grounded`、`Verifiable`。

版式：

- 中间一个大标题。
- 下方三块，每块只放一个关键词和一句中文。

页面文字：

> 证据约束型工作流

三块内容：

> Tool-first  
> 模拟交给固定工具

> Evidence-grounded  
> 诊断读取证据表

> Verifiable  
> 结论计算 unsupported rate

口头讲法：

> 这个系统最重要的设计原则是：模型运行不靠 LLM 自己写，诊断不靠 LLM 自由发挥，结论不能只停留在自然语言里。

注意：

- 这一页文字越短越好。
- 可以把 `unsupported rate` 用橙红色强调。

---

### 第 6 页：系统架构

页面目的：展示 SWMM-Agentic2 的 Agent 分工。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\paper_assets\figures\agent_collaboration_logic_v5.svg`

版式：

- 图片占 75%-80% 页面。
- 左上角或顶部放标题。
- 底部只放一句总结。

页面文字：

> 工作流 Agent 架构

底部小字：

> 每个 Agent 只处理一个明确阶段

口头讲法：

> SWMM-Agentic2 把任务拆成 Scenario、Simulation、Evidence、Diagnosis、Verification、Report 等阶段。每个阶段有清楚的输入和输出，减少任务路由漂移。

注意：

- 不要在这页逐个解释所有 Agent。
- 讲清“分阶段”和“边界明确”即可。

---

### 第 7 页：一次任务如何流转

页面目的：把架构变成可理解的执行过程。

主图：

- 自制极简流程线，使用项目 README 中的阶段：
  - `User request`
  - `ScenarioAgent`
  - `SimulationAgent`
  - `EvidenceBuilderAgent`
  - `DiagnosisAgent`
  - `VerificationAgent`
  - `ReportAgent`

可选配图：

- 降雨输入图：`E:\SWMM_Agentic\SWMM-Agentic2\outputs\rainfall_hyetograph.png`

版式：

- 上方放流程线。
- 下方放一个“输入到输出”的例子。

页面文字：

> 一次自然语言任务的路径

流程文字：

> 请求  
> 情景  
> 模拟  
> 证据  
> 诊断  
> 核查  
> 报告

示例小字：

> rain1 + baseline

口头讲法：

> 用户给出降雨和情景后，系统先准备 scenario_request，再运行 SWMM-CA2D，然后生成证据表、诊断结论和核查报告。

注意：

- 流程线不要做复杂箭头网。
- 这页只讲“顺序”，不讲内部算法。

---

### 第 8 页：真实案例规模

页面目的：证明项目不是小 demo，而是接近论文实验对象的真实/准真实大规模案例。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\ca2d\ca2d_max_depth.png`

数据来源：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\summary.json`

版式：

- 左侧放三个大数字。
- 右侧放最大积水深度图。

页面文字：

> 大规模 SWMM-CA2D 案例

三个大数字：

> 10040  
> SWMM 节点

> 9877  
> 管段链接

> 598535  
> CA2D 结果记录

口头讲法：

> 当前案例已经超过 1 万个 SWMM 节点、接近 1 万条链接，并产生近 60 万条 CA2D 结果记录。这个规模已经能支撑“复杂输出如何被诊断”的论文问题。

注意：

- 只放 3 个数字，不要塞完整 summary。
- 图上可以圈出高水深区域，但不要加太多标注。

---

### 第 9 页：标准化模拟输出

页面目的：说明系统不是只生成自然语言，而是沉淀可复现文件。

主图：

- 建议用运行目录截图：
  - `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600`

关键文件：

- `summary.json`
- `swmm\node_flooding.tsv`
- `swmm\nodes.tsv`
- `swmm\links.tsv`
- `ca2d\surface_depth.tsv`

版式：

- 左侧标题。
- 右侧目录树截图或手绘目录树。
- 目录树只保留关键文件。

页面文字：

> 每次运行都有固定目录

目录树文字：

> summary.json  
> swmm / nodes, links, flooding  
> ca2d / surface_depth  
> evidence / evidence_table  
> diagnosis / claims  
> verification / report

口头讲法：

> 我把一次模拟固定成标准运行目录，后续 Agent 不再到处找文件，而是从明确的输出位置读取结果。

注意：

- 这页强调“可复现”和“可交接”。
- 不要展示完整文件路径，太长。

---

### 第 10 页：证据表

页面目的：讲清楚系统创新的核心中间产物：evidence table。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\evidence\evidence_table.csv`

数据来源：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\evidence\evidence_summary.json`

版式：

- 上方：标题。
- 中间：evidence_table.csv 局部截图，突出 `evidence_id`、`object_type`、`object_id`、`metric_name`、`value`。
- 右侧：一个大数字。

页面文字：

> 证据表把输出变成诊断材料

大数字：

> 318411  
> evidence records

表格旁标签：

> 对象  
> 指标  
> 数值  
> 来源

口头讲法：

> Evidence table 是整个系统的核心中间层。它把 SWMM 和 CA2D 的结果统一成一条条可引用证据，每条证据都有对象、指标、数值、单位、来源文件和 evidence_id。

注意：

- 不要让表格太密。只截 6-8 行。
- `evidence_id` 要高亮，因为后面 claim 要引用它。

---

### 第 11 页：诊断结论

页面目的：展示系统如何从证据生成诊断，而不是停在数据表。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\diagnosis\risk_ranking.csv`

辅助文件：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\diagnosis\diagnosis_claims.json`

版式：

- 左侧放最大积水深度图局部。
- 右侧放 Top 5 风险排序。

页面文字：

> 从证据表生成风险排序

右侧 Top 5：

> Cell 115176 / 0.698 m  
> Cell 38021 / 0.638 m  
> Cell 9684 / 0.523 m  
> Cell 37765 / 0.476 m  
> Cell 38278 / 0.458 m

底部小字：

> claim = object + metric + value + evidence_id

口头讲法：

> DiagnosisAgent 不直接读原始大文件，而是从证据表里按规则识别热点、持续积水和高风险对象。这样每条诊断都能回到对应 evidence_id。

注意：

- Top 5 足够，不要把 Top 10 全放上去。
- 数字保留 3 位小数即可。

---

### 第 12 页：证据核查

页面目的：展示可靠性评价机制，这是论文亮点。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\verification\verification_report.json`

辅助文件：

- `E:\SWMM_Agentic\SWMM-Agentic2\models\songhua_swmm_2d\runs\rain1__baseline__20260721_165600\verification\unsupported_rate.txt`

版式：

- 中间放一个极简“核查仪表盘”。
- 三个数字横排。

页面文字：

> 结论先过证据关

三个数字：

> 50  
> claims

> 50  
> supported

> 0.0  
> unsupported rate

底部小字：

> 每条 claim 检查 evidence_ids

口头讲法：

> VerificationAgent 会检查每条诊断引用的 evidence_ids 是否真的支持对应结论。最后用 unsupported rate 衡量无证据结论比例。

注意：

- 这一页非常重要，要让老师记住 `unsupported rate`。
- 不要把 JSON 原文放太多。

---

### 第 13 页：前端与交互

页面目的：说明系统可以通过自然语言使用，但不要把重点带偏成“聊天机器人”。

主图：

- `E:\SWMM_Agentic\SWMM-Agentic2\outputs\frontend-desktop.png`

版式：

- 左侧放前端截图。
- 右侧放三条“它能做什么”。

页面文字：

> 自然语言只是入口

三条能力：

> 准备情景  
> 推进工作流  
> 查看诊断结果

口头讲法：

> 前端的意义是降低使用门槛。用户可以用自然语言触发工作流阶段，但真正保证可靠性的仍然是后端的固定工具、证据表和核查机制。

注意：

- 标题一定不要写“智能问答系统”。
- 强调“入口”，不是核心创新。

---

### 第 14 页：总结与下一步

页面目的：收束贡献，并自然引出后续工作。

主图：

- 建议使用一条纵向链路或桥梁式图：
  - 左：`SWMM-CA2D simulation`
  - 中：`Evidence-grounded workflow`
  - 右：`Flood diagnosis`

版式：

- 上方一句总结。
- 中间三段链路。
- 底部三条下一步。

页面文字：

> SWMM-Agentic2 补上了模拟与诊断之间的中间层

链路文字：

> 模型计算  
> 证据组织  
> 可信诊断

下一步：

> 多降雨事件  
> benchmark 任务  
> 对比实验

口头讲法：

> 当前系统已经完成从模拟输出到证据、诊断、核查的基本闭环。下一步要把它扩展到更多降雨和情景，并建立 benchmark，对比直接 LLM、普通工具调用和完整 Agentic workflow 的差异。

注意：

- 最后一页不要新增复杂概念。
- 让听众带走“中间层”和“可信诊断”两个词。

## 5. 备份页规划

### 备份页 B1：SWMM-Agentic 与 SWMM-Agentic2 区别

页面目的：回答“新版到底新在哪里”。

主图：

- 左右对比。

页面文字：

> 从能跑到能证

左侧：

> SWMM-Agentic  
> 工具调用  
> 模拟执行  
> 结果解释

右侧：

> SWMM-Agentic2  
> 阶段 Agent  
> 证据表  
> 结论核查

口头讲法：

> 第一版重点解决自然语言驱动模型运行，第二版重点解决诊断结论的证据边界。

---

### 备份页 B2：诊断规则

页面目的：如果老师问诊断是不是 LLM 编的，用这页解释规则来源。

引用文件：

- `E:\SWMM_Agentic\SWMM-Agentic2\workflow_agents\rules\diagnosis_rules.json`

页面文字：

> 诊断由规则触发

规则示例：

> moderate depth：0.27 m  
> high depth：0.40 m  
> critical depth：0.60 m

口头讲法：

> 当前诊断先采用确定性阈值规则，LLM 不直接决定风险等级。后续可以把阈值校准作为实验内容。

---

### 备份页 B3：核查规则

页面目的：解释 VerificationAgent 怎么判断 supported / unsupported。

引用文件：

- `E:\SWMM_Agentic\SWMM-Agentic2\workflow_agents\rules\verification_rules.json`

页面文字：

> 不同 claim 需要不同证据

示例：

> surface_hotspot：max_depth  
> long_duration_ponding：ponding_duration  
> high_load_link：max_fullness

口头讲法：

> 核查不是简单看有没有 evidence_id，而是看 claim 类型需要的指标是否存在、是否对应同一个对象、是否满足规则要求。

## 6. 每页文字总表

| 页码 | 标题 | 页面主文字 |
|---:|---|---|
| 1 | SWMM-CA2D Agentic | 证据约束型城市内涝诊断工作流 |
| 2 | 模型结果很多 | 但诊断依据很散 |
| 3 | 从模型输出到可信诊断 | Simulation outputs / Evidence table / Verified diagnosis |
| 4 | 研究对象更复杂 | EPANET：供水管网；SWMM-CA2D：管网 + 地表积水 |
| 5 | 证据约束型工作流 | Tool-first / Evidence-grounded / Verifiable |
| 6 | 工作流 Agent 架构 | 每个 Agent 只处理一个明确阶段 |
| 7 | 一次自然语言任务的路径 | 请求 / 情景 / 模拟 / 证据 / 诊断 / 核查 / 报告 |
| 8 | 大规模 SWMM-CA2D 案例 | 10040 节点 / 9877 管段 / 598535 条 CA2D 结果 |
| 9 | 每次运行都有固定目录 | summary / swmm / ca2d / evidence / diagnosis / verification |
| 10 | 证据表把输出变成诊断材料 | 318411 evidence records |
| 11 | 从证据表生成风险排序 | Cell 115176 / 0.698 m |
| 12 | 结论先过证据关 | 50 claims / 50 supported / unsupported rate = 0.0 |
| 13 | 自然语言只是入口 | 准备情景 / 推进工作流 / 查看诊断结果 |
| 14 | 模拟与诊断之间的中间层 | 模型计算 / 证据组织 / 可信诊断 |

## 7. 汇报节奏建议

### 8 分钟版本

- 第 1-3 页：1 分钟，讲研究定位。
- 第 4-6 页：2 分钟，讲对象复杂性和架构。
- 第 7-12 页：4 分钟，讲案例、证据表、诊断、核查。
- 第 13-14 页：1 分钟，讲入口和下一步。

### 12 分钟版本

- 第 1-3 页：2 分钟。
- 第 4-6 页：3 分钟。
- 第 7-12 页：5 分钟。
- 第 13-14 页：2 分钟。

## 8. 不建议放进正片的内容

这些内容不是没价值，而是不适合正片：

1. 大段代码截图。
2. 完整 JSON 文件。
3. 完整 evidence_table。
4. 过多失败历史。
5. 太细的前端交互。
6. “未来要做 embedding/RAG”的大篇幅说明。

如果老师问，可以放到备份页或口头补充。

## 9. 最推荐的开场白

> 我这个项目目前想解决的不是“怎样用自然语言把模型跑起来”，而是更靠后的问题：SWMM-CA2D 跑完以后，怎么把大量节点、管段和地表元胞结果，变成有证据支撑、可以核查的内涝诊断。

## 10. 最推荐的结尾

> 所以 SWMM-Agentic2 的价值，不是替代 SWMM 或 CA2D，而是在模型软件和工程决策之间补上一个证据约束的诊断工作流。

