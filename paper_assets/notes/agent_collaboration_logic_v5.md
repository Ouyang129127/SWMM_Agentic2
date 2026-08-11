# SWMM-2D-Agentic 论文 Agent 协同工作逻辑图 V5

本版在 V4 的基础上，将中层两个模块互换：

- 左中：`诊断与核查模块`
- 右中：`证据构建模块`

这样右上方的 `模型计算模块` 可以更自然地下接右中方的 `证据构建模块`，再由证据表横向输入左中方的 `诊断与核查模块`，减少一部分跨图斜线和交叉。

## 阅读顺序

本版建议按以下路径阅读：

```text
左上任务编排
-> 右上模型计算
-> 右中证据构建
-> 左中诊断与核查
-> 下方解释、报告与评价
```

这种排布更接近“Z 字形”阅读路径。

## 文件位置

浏览器查看：

```text
paper_assets/figures/agent_collaboration_logic_v5.html
```

矢量图源文件：

```text
paper_assets/figures/agent_collaboration_logic_v5.svg
```

