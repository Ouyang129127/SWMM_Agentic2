# SWMM-Agentic 中文结构说明

这个项目是根据 `EPANET-Agentic` 的代码组织方式迁移出的 SWMM 版本骨架。

## 目录结构

```text
E:\SWMM_Agentic\SWMM-Agentic
  main.py              多智能体入口
  llm.py               DeepSeek / Qwen 模型客户端配置
  prompts.py           智能体预设提示词
  tools.py             SWMM 工具函数
  requirements.txt     Python 依赖
  run.ps1              Windows 启动脚本
  tasks/               示例任务
  code_dir/            代码执行工作目录
  code_dir/data/       SWMM .inp 文件存放处
  conversation/        后续保存对话或结果说明
```

## 和 EPANET-Agentic 的对应关系

| EPANET-Agentic | SWMM-Agentic |
| --- | --- |
| WNTR / EPANET `.inp` | PySWMM / SWMM `.inp` |
| `is_runnable_inp` 检查水网模型 | `is_runnable_inp` 检查 SWMM 模型结构，可选 PySWMM 运行 |
| `add_multiple_controls` 添加水网控制 | `add_controls` 插入 SWMM `[CONTROLS]` 规则 |
| `apply_disaster_scenario` 添加灾害场景 | `apply_scenario` 添加降雨、管渠、节点、调蓄场景 |
| `CodeRunner` 生成 WNTR 仿真代码 | `CodeRunner` 生成 PySWMM / swmmio 分析代码 |
| `DataAnalyzer` 分析图和结果 | `DataAnalyzer` 分析 SWMM 图、CSV、TXT |

## 智能体分工

### Orchestrator

总调度智能体。负责理解用户任务、拆步骤、决定调用哪个功能。

### TaskExecutor

工具执行智能体。负责调用 `tools.py` 中的固定函数：

- `is_runnable_inp`
- `add_controls`
- `apply_scenario`

### CodeRunner

代码生成和执行入口。内部包含：

- `coder`：用 DeepSeek Reasoner 写 Python 代码
- `coder_user`：执行代码

### DataAnalyzer

结果分析智能体。用 Qwen-VL 分析图片、表格和文本结果。

## 当前已经实现的 SWMM 工具雏形

### `is_runnable_inp`

可以读取 SWMM `.inp`，解析 section，并统计：

- subcatchments
- rain gages
- nodes
- links
- 常见 section 是否缺失

如果传入 `run_simulation=True`，会尝试用 PySWMM 打开并推进至少一步仿真。

### `add_controls`

向 `[CONTROLS]` section 插入 SWMM 控制规则，并另存为新 `.inp`。

### `apply_scenario`

当前支持：

- `rainfall_scale`：缩放 `[TIMESERIES]` 降雨数值
- `conduit_blockage`：通过提高 conduit roughness 模拟堵塞阻力
- `junction_surcharge`：修改 junction surcharge depth
- `storage_initial_depth`：修改 storage initial depth

## 已放入的样例

已复制：

```text
E:\SwmmExample\SwmmExample\Rain.inp
```

到：

```text
E:\SWMM_Agentic\SWMM-Agentic\code_dir\data\example.inp
```

所以示例任务可以直接引用：

```text
data/example.inp
```

