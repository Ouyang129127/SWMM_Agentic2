# Tool-first 执行策略与固定模拟管线

## 1. 记录背景

本次错误历史位于：

```text
E:\SWMM_Agentic\SWMM-Agentic\试错与创新点记录\错误历史记录4-模拟失败+tool-first execution
```

相关材料包括：

- `SWMM-2D-Agentic ChatHistory3.html`：前端对话历史；
- `4795eec83d354694d368171e9682e716.png`：后台控制台截图。

本次用户希望执行一次基于 `songhua_swmm_2d` 的 SWMM-2D 模拟：

```text
使用 events/rain1.txt 作为降雨事件，
结合 baseline SWMM 输入文件，
运行 SWMM，
导出节点溢流，
再驱动 CA2D 二维地表模型，
最后保存结果。
```

前端对话中，Agent 能够完成模型检查和流程规划，但在真正执行模拟时没有稳定进入固定模拟工具，而是绕到了 LLM/CodeRunner 的临时执行链路，最终表现为模拟未成功执行、API 超时或执行流程不清。

## 2. 关键复现结论

后续通过固定工具直接复现，发现问题并不在模型本身。

固定工具调用：

```text
run_swmm_2d_project_from_rainfall(
  model_name="songhua_swmm_2d",
  rainfall_file="events/rain1.txt",
  event_name="rain1",
  scenario_name="baseline",
  run_id="codex_diag_rain1_20260720"
)
```

运行结果显示完整 SWMM-2D 流程可以跑通：

```text
SWMM total_steps: 14360
SWMM saved_steps: 5
node_count: 10040
link_count: 9877
flooding_records: 49450
max_flooding_Ls: 531.91
max_node_depth_m: 10.5

CA2D matched_nodes: 9890
report_times: 5
max_depth_m: 0.759
result_records: 598535
```

输出目录：

```text
models/songhua_swmm_2d/runs/codex_diag_rain1_20260720/
```

因此，本次失败不是：

```text
rain1.txt 读取失败
SWMM 输入文件无法启动
CA2D 静态模型无法运行
```

而是：

```text
用户的“执行模拟”请求没有被确定性路由到固定模拟工具，
而是进入了 LLM/CodeRunner 临时规划或临时代码链路。
```

## 3. 发现的核心问题

本次问题和之前“完整性检查结果不一致”的问题具有同构性。

之前的问题是：

```text
正式模型完整性检查没有固定走 check_swmm_2d_project，
导致 CodeRunner 临时脚本发明 data/model.inp、outputs/ 等错误检查标准。
```

本次的问题是：

```text
正式模拟执行没有固定走 run_swmm_2d_project_from_rainfall，
导致 CodeRunner 或 LLM 临时尝试读取降雨、写入 SWMM、运行模型，
从而出现路径、格式、API 超时或流程不完整的问题。
```

这说明系统需要的不只是：

```text
固定验证器
```

还需要：

```text
固定模拟执行管线
```

## 4. Tool-first execution policy

本次可以提炼出一个重要设计原则：

```text
Tool-first execution policy
```

中文可称：

```text
工具优先的确定性执行策略
```

其核心思想是：

> 对于已经被工程验证过的固定任务链，Agent 不应让 LLM 每次临时编写代码或自由规划执行步骤，而应优先调用经过验证的领域工具。LLM 的职责是识别任务、选择工具、组织流程和解释结果，而不是重复实现底层工程计算。

一句话表达：

> **Agentic 不是让 LLM 每次临时写工程代码，而是让 LLM 正确选择和组织已经验证过的工程工具。**

## 5. 固定工程动作与开放分析任务的边界

系统应明确区分两类任务。

### 5.1 固定工程动作

这类任务必须走固定 tools，不应交给 CodeRunner 临时写脚本。

包括：

```text
列出模型项目
检查模型完整性
检查 CA2D 静态模型
列出降雨事件
读取降雨事件
写入 SWMM 输入文件
运行 SWMM
导出节点溢流
运行 CA2D
保存 run.yaml 和 summary.json
```

对应工具包括：

```text
list_swmm_2d_models()
check_swmm_2d_project()
check_all_swmm_2d_projects()
check_ca2d_model()
list_rainfall_events()
run_swmm_2d_project_from_rainfall()
run_swmm_2d_project_from_flooding()
```

### 5.2 开放分析任务

这类任务可以交给 LLM、CodeRunner 或 DataAnalyzer。

包括：

```text
解释结果
生成图表
提取自定义指标
编写诊断报告
比较多个情景
生成论文图表
形成管理部门简报
```

这类任务的输入应该来自固定工具已经生成的结果文件，而不是让 CodeRunner 重新发明模拟过程。

## 6. 推荐系统路由策略

后续系统应采用如下路由规则：

```text
模型完整性检查 -> fixed validators
降雨事件列表/读取 -> fixed tools
SWMM-2D 模拟执行 -> fixed pipeline tool
结果解释/图表补充/报告生成 -> LLM / CodeRunner / DataAnalyzer
```

更具体地说：

```text
如果用户明确要求“执行模拟”“运行模型”“使用 rain1.txt”“baseline 场景”“生成 run 结果”
则必须优先调用：

run_swmm_2d_project_from_rainfall()
```

只有当用户提出固定工具不覆盖的开放需求时，才允许使用 CodeRunner。

例如：

```text
请把 run_xxx 的最大积水深度图重新配色
请比较 run_A 和 run_B 的峰值积水差异
请生成一份管理部门简报
```

这些才适合进入开放分析层。

## 7. SWMM-2D 固定模拟管线

对当前项目而言，完整模拟管线已经存在：

```text
run_swmm_2d_project_from_rainfall()
```

它应负责：

1. 读取 `models/<model_name>/events/<rainfall_file>`；
2. 解析时间戳和降雨强度；
3. 将降雨事件写入 run 专属 SWMM 输入文件；
4. 更新 SWMM 模拟起止时间；
5. 调用 PySWMM 运行一维管网模型；
6. 导出节点水深、节点溢流、管段流量等结果；
7. 生成 CA2D 所需的 `node_flooding.tsv`；
8. 调用 CA2D 二维地表漫流模型；
9. 保存 `surface_depth.tsv`、深度图、动画等输出；
10. 保存 `summary.json` 和 `run.yaml`。

这条管线一旦经过验证，就应该成为 Agent 的默认模拟执行入口。

## 8. 为什么不能让 CodeRunner 临时重写模拟链

如果每次让 CodeRunner 临时写模拟代码，容易出现以下问题：

- 忘记 `rain1.txt` 第一行是中文单位说明；
- 误判降雨文件格式；
- 用错 `model.inp` 路径；
- 忽略 `swmm/scenarios/baseline/model.inp` 规范；
- 忘记更新 SWMM 起止时间；
- 只运行 SWMM，不导出 CA2D 所需节点溢流；
- 保存目录不符合 `runs/<run_id>/` 规范；
- 不生成 `summary.json` 和 `run.yaml`；
- API 超时后没有实际执行；
- 临时代码引入新的依赖或路径错误；
- 无法保证多次执行结果一致。

因此，CodeRunner 不应承担正式模拟执行职责。

它更适合承担：

```text
模拟结果后的自定义分析
图表再加工
报告生成
诊断指标扩展
```

## 9. 和前面创新点的关系

本次发现可以与前面的几个创新点串成完整可靠性链条：

```text
结构规范约束验证
-> 固定验证器
-> 固定模拟管线
-> 证据保持型解释
-> 污染签名检测
-> 可审计工作流
```

其中：

- 结构规范约束验证：解决“检查标准漂移”；
- 固定验证器：解决“同一项目五次检查五种结果”；
- 固定模拟管线：解决“同一模拟五次执行五种流程”；
- 证据保持型解释：解决“只有 JSON 不够友好，但 LLM 不能篡改结论”；
- 污染签名检测：解决“两数之和、哈希表”等离域幻觉；
- 可审计工作流：解决“到底执行了什么工具、产生了什么结果”的追踪问题。

## 10. 可发展为论文方法贡献

这可以写成论文中的一个方法模块：

```text
Tool-first execution policy for hydrodynamic model workflows
```

中文：

```text
面向水动力模型工作流的工具优先执行策略
```

论文表述建议：

> SWMM-2D-Agentic adopts a tool-first execution policy for deterministic hydrodynamic modelling tasks. Instead of allowing LLMs to repeatedly generate ad hoc scripts for rainfall parsing, SWMM execution, overflow extraction, and CA2D simulation, the system routes such operations to pre-validated domain tools. The LLM is used to interpret user intent, select tools, organize the workflow, and explain evidence-grounded outputs, while deterministic tools retain authority over model execution.

中文表述：

> SWMM-2D-Agentic 针对确定性的水动力模型任务采用工具优先执行策略。系统不允许 LLM 反复临时生成降雨解析、SWMM 运行、节点溢流导出和 CA2D 模拟代码，而是将这些操作路由到经过验证的领域工具。LLM 负责理解用户意图、选择工具、组织流程和解释证据约束输出，确定性工具保留模型执行的裁决权。

## 11. 可评价指标

后续 benchmark 可以增加以下指标：

- Fixed-tool routing accuracy：固定工具路由准确率；
- Ad hoc script avoidance rate：临时脚本避免率；
- Simulation pipeline success rate：模拟管线成功率；
- Run artifact completeness：运行产物完整率；
- Repeatability under same request：同请求重复执行一致性；
- Tool execution trace completeness：工具执行轨迹完整性；
- LLM intervention count before execution：执行前 LLM 干预次数；
- Incorrect CodeRunner routing rate：错误路由到 CodeRunner 的比例。

## 12. 本次结论

本次案例说明：

1. `rain1.txt` 可以被固定解析器读取；
2. SWMM 输入文件可以被 PySWMM 启动；
3. SWMM 到 CA2D 的完整固定管线可以跑通；
4. 失败主要来自请求没有稳定路由到固定模拟工具；
5. 对确定性工程任务，应采用 Tool-first execution policy；
6. LLM 的价值不是临时重写工程代码，而是正确选择、组织和解释已验证工具。

一句话总结：

> 对 SWMM-2D-Agentic 而言，可靠的 Agentic 不是“让 LLM 去写模拟程序”，而是“让 LLM 把经过验证的模拟工具组织成可执行、可追踪、可解释的工作流”。
