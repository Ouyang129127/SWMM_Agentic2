# 未调用固定模拟工具而误入 CodeRunner 问题分析

## 1. 问题背景

本次记录来自一次重新执行模型检查与 SWMM-2D 耦合模拟的前端实验。

相关证据文件：

- 前端对话历史：`SWMM-2D-Agentic Chat5.html`
- 后台运行日志：Codex 附件 `pasted-text.txt`
- 前端截图：用户提供的三张对话截图

用户观察到：在“执行模拟”这一步，系统没有调用已有的固定模拟工具，而是让 `CodeRunner` 自己生成 Python 脚本。该脚本没有使用项目的真实路径规范，错误地查找 `models/songhua_swmm_2d/model.inp`，最终导致模拟失败。

经对照前端对话和后台日志，该判断成立。

## 2. 前端真实用户输入

前端截图和 HTML 记录显示，用户没有要求系统生成 Python 代码。

真实前端输入是：

```text
请对这个模型进行模拟计算
```

随后 Agent 询问是否使用默认降雨事件：

```text
是否使用默认的降雨事件 events\rain1.txt 进行模拟？
```

用户确认：

```text
是的，使用你说的events\rain1.txt。请继续
```

因此，用户意图非常明确：使用已有模型和已有降雨事件执行模拟计算。

这里不应被解释为“请生成 Python 代码”，也不应进入临时脚本生成链路。

## 3. 后台日志中的“user”不是前端用户

后台日志中出现了如下内部任务文本：

```text
task: 运行songhua_swmm_2d模型的完整SWMM-2D耦合模拟。使用降雨事件文件events/rain1.txt。
...
请生成完整的Python代码来执行这个耦合模拟。
name of file to be saved: swmm_2d_coupled_simulation.py
SWMM status: models/songhua_swmm_2d
```

这段日志被标记为：

```text
---------- TextMessage (user) ----------
```

但它不是前端用户原始输入，而是 `Orchestrator` 或 Web agent 传给 `CodeRunner` 小队的内部任务消息。

这一点非常关键：

> AutoGen 内部日志里的 `TextMessage (user)` 不一定等于真实前端用户输入。它也可能是上层 agent 发给子 agent 的任务。

因此，不能把“请生成完整 Python 代码”归因给用户。该文本是系统内部在工具路由过程中生成的。

## 4. 直接失败表现

`CodeRunner` 生成的第一段脚本使用了错误路径：

```python
project_root = Path("models/songhua_swmm_2d")
inp_file = project_root / "model.inp"
rain_file = project_root / "events" / "rain1.txt"
```

但本项目真实的基线 SWMM 输入路径是：

```text
models/songhua_swmm_2d/swmm/scenarios/baseline/model.inp
```

因此脚本失败：

```text
ValueError: SWMM输入文件不存在: models\songhua_swmm_2d\model.inp
```

后续 `CodeRunner` 又尝试生成“替代方案”，继续用 ad hoc 脚本查找 `model.inp`，仍然没有执行官方固定管线。

## 5. 谁的锅？

### 5.1 直接责任：Orchestrator 误路由

本次最直接的问题是：`Orchestrator` 把“执行模拟”误判成了 `CodeRunner` 的代码生成任务。

按照系统设计，用户确认：

```text
使用 events\rain1.txt 继续模拟
```

应该被路由为：

```text
TaskExecutor.run_swmm_2d_project_from_rainfall(
    model_name="songhua_swmm_2d",
    rainfall_file="events/rain1.txt",
    scenario_name="baseline"
)
```

但实际进入了：

```text
CodeRunner(message, SWMM_status, name)
```

并且内部任务被改写为“生成完整 Python 代码来执行耦合模拟”。

所以，直接背锅的是 Orchestrator 的工具选择错误。

### 5.2 系统设计责任：确定性路由没有兜住

`web_app.py` 中已有确定性模拟路由：

```python
deterministic_simulation_evidence(...)
```

设计目的本来是：如果识别到 rainfall-driven SWMM-2D coupled run，就直接调用固定工具：

```python
run_swmm_2d_project_from_rainfall(...)
```

不再交给 Orchestrator 自由判断。

但是这次用户的确认句是承接式表达：

```text
是的，使用你说的events\rain1.txt。请继续
```

这句话本身没有显式包含“运行模拟”“执行模拟”“耦合模拟”等强触发词，而是依赖上一轮计划中的语境。

当前确定性路由对这种承接式确认识别不够强，导致它没有拦截请求。请求落回 Orchestrator 后，Orchestrator 自由选择工具，最终误入 CodeRunner。

因此，更深一层的锅在系统路由层：

> 固定模拟管线没有被代码级 gatekeeper 强制拦截。

### 5.3 提示词责任：规则存在，但约束不够硬

`prompts.py` 中其实已经写了正确规则：

```text
If the task asks to run a model from a rainfall event file such as events/rain1.txt
or events/<event_name>/rain1.txt, call TaskExecutor with
run_swmm_2d_project_from_rainfall. Do not route this official pipeline to CodeRunner.
```

这说明提示词方向是正确的。

但是提示词只是软约束。实际运行时，Orchestrator 仍然看到了 `CodeRunner` 这个可用工具，而 `CodeRunner` 的职责描述中包含：

```text
simulation, analysis, plotting, or saving task
generates Python code
```

当 Orchestrator 没有稳定识别出“这是固定 tool 已覆盖的官方模拟流程”时，就可能把“模拟 + 保存结果”错误理解为代码生成任务。

因此提示词不是完全写错，而是：

> prompt-only routing 不足以保证工程模拟任务可靠路由。

## 6. 本次错误链条

```text
前端用户：请对这个模型进行模拟计算
        ↓
Agent 计划：使用 events\rain1.txt 执行 SWMM-2D 耦合模拟
        ↓
用户确认：是的，使用 events\rain1.txt，请继续
        ↓
确定性路由没有识别出承接式模拟确认
        ↓
请求交给 Orchestrator 自由判断
        ↓
Orchestrator 误选 CodeRunner
        ↓
内部任务被改写为“生成完整 Python 代码执行耦合模拟”
        ↓
CodeRunner 生成 ad hoc 脚本
        ↓
脚本使用错误路径 models/songhua_swmm_2d/model.inp
        ↓
模拟失败
        ↓
前端最终返回模型完整性 JSON，而不是模拟结果
```

## 7. 研究价值

这次错误非常有研究价值，因为它揭示了一个重要现象：

> 用户意图、Orchestrator 内部任务改写、子 agent 实际执行任务，三者可能发生偏移。

这不是普通的路径错误，而是 agentic workflow 中的任务语义漂移：

```text
用户意图：执行官方模拟
        ↓
内部改写：生成 Python 代码执行模拟
        ↓
实际执行：ad hoc 脚本检查错误路径
```

这说明在工程模拟系统中，只检查 final answer 是不够的，还必须检查 execution trace。

本案例可提炼为论文中的一种失败类型：

```text
Tool-routing drift from fixed pipeline to ad hoc CodeRunner execution
```

中文可表述为：

```text
固定工具管线向临时代码执行链路的路由漂移
```

## 8. 对系统设计的启示

### 8.1 官方固定流程不能交给 LLM 自由判断

对于以下任务，应由代码层直接拦截：

- 模型完整性检查
- 降雨事件检查
- CA2D 静态模型检查
- rainfall-to-SWMM-to-CA2D 官方耦合模拟

这些任务不应让 Orchestrator 在 `TaskExecutor` 和 `CodeRunner` 之间自由选择。

### 8.2 承接式确认也要进入确定性路由

系统应识别以下模式：

```text
上一轮计划包含“使用 rain1.txt 执行模拟”
当前用户说“是的 / 继续 / 请继续 / 按计划执行”
```

此时应直接触发：

```python
run_swmm_2d_project_from_rainfall(...)
```

而不是再次交给 Orchestrator 解释。

### 8.3 CodeRunner 应被禁止执行官方模拟管线

即使用户说“模拟”“保存结果”“生成报告”，只要任务属于官方固定管线覆盖范围，就不应进入 `CodeRunner`。

`CodeRunner` 只适合：

- 固定工具结果之后的自定义图表
- 指标提取
- 额外统计
- 非官方流程的探索性脚本

不应承担正式耦合模拟职责。

## 9. 后续修复方向

本文件只记录原因分析，暂不修改代码。后续可考虑：

1. 强化 `deterministic_simulation_evidence`
   - 从历史上下文中识别“上一轮计划要执行模拟”
   - 当前用户确认时直接调用固定模拟工具

2. 增加 hard gate
   - 如果请求包含 `events/rain1.txt`、`rainfall event`、`耦合模拟`、`SWMM-2D模拟` 等关键词，优先匹配固定工具
   - 匹配成功时禁止进入 Orchestrator 自由工具选择

3. 在 `CodeRunner` 入口增加拒绝逻辑
   - 如果任务文本包含官方耦合模拟关键词，直接返回“必须使用 TaskExecutor”
   - 不生成任何 ad hoc Python 代码

4. 在日志中区分真实用户输入和内部子 agent 任务
   - 避免把 AutoGen 内部 `TextMessage (user)` 误读为前端用户原话
   - 对研究分析非常重要

## 10. 结论

本次错误不是用户要求写 Python 代码造成的。

真实原因是：

> 系统内部把“执行模拟”的用户意图错误改写并路由成了 CodeRunner 代码生成任务。

直接责任在 Orchestrator 的工具选择错误；更深层责任在系统路由层没有用代码级 gatekeeper 强制固定模拟管线；提示词虽写了正确方向，但不足以约束 LLM 在复杂上下文中的实际路由行为。

这为 SWMM-2D-Agentic 后续可靠性设计提供了一个非常清楚的证据：工程模拟 agent 不能只靠 prompt 决定工具调用，必须用确定性路由和执行轨迹审计来保证 tool-first 工作流。
