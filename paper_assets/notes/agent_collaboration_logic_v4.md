# SWMM-2D-Agentic 论文 Agent 协同工作逻辑图 V4

本版将图从“过长的纵向结构”和“过宽的横向结构”调整为更接近论文插图的方正版布局。

布局原则：

1. 上层：任务编排模块、模型计算模块。
2. 中层：证据构建模块、诊断与核查模块。
3. 下层：解释、报告与评价模块横向展开。

这样图的阅读顺序仍然是：

```text
左上 -> 右上 -> 左中 -> 右中 -> 下方
```

但整体版式更接近矩形，不会过长，也不会过宽。

## 本版关键调整

1. `Simulation Agent` 使用 `SWMM-2D 标准化模拟流程调度`。
2. `CA2D 原始输出` 明确由 `SWMM 原始输出` 和 `CA2D 二维地表积水模型` 共同生成。
3. 保留五个大模块，但采用 2 列 + 底部汇总模块的方式。
4. 增加颜色图例，区分：
   - LLM / Agent 层。
   - 确定性工具与模型层。
   - 证据与核查层。
   - 报告与论文输出。

## 文件位置

可直接打开：

```text
paper_assets/figures/agent_collaboration_logic_v4.html
```

可用于论文后期矢量编辑：

```text
paper_assets/figures/agent_collaboration_logic_v4.svg
```

