# urban_drainage 九场雨型矩阵补充（2026-10-11）

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: input preparation（仅准备合成输入，不执行水力模拟或诊断）
- Origin Date: 2026-10-11
- Verification Status: VERIFIED_INPUTS（已核对文件与解析兼容性；不代表水力结果或诊断准确性已验证）
- Version Label: urban_nine_storm_inputs_v1
- 来源：现有单峰、双峰、三峰 80 mm TXT；以保存后的实际数值缩放，不重新拟合雨型。
- 授权范围：新增单峰 160 mm、双峰 120 mm、三峰 120 mm、三峰 160 mm；原有六个降雨输入及历史模拟结果不修改。

## 新增文件

| 文件 | 雨型 | 总雨量 / mm | 相对原80 mm曲线倍数 | 最大5分钟平均雨强 / mm/h | 峰值处总和校正 / mm/h |
|---|---|---:|---:|---:|---:|
| [chicago_like_single_4h_160mm_5min.txt](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/events/chicago_like_single_4h_160mm_5min.txt) | 单峰 | 160 | 2 | 293.464 | 0.000 |
| [chicago_like_double_4h_120mm_5min.txt](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/events/chicago_like_double_4h_120mm_5min.txt) | 双峰 | 120 | 1.5 | 141.250 | -0.010 |
| [chicago_like_triple_4h_120mm_5min.txt](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/events/chicago_like_triple_4h_120mm_5min.txt) | 三峰 | 120 | 1.5 | 146.648 | -0.012 |
| [chicago_like_triple_4h_160mm_5min.txt](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/events/chicago_like_triple_4h_160mm_5min.txt) | 三峰 | 160 | 2 | 195.546 | 0.000 |

全部采用 `timestamp,value`，value 单位 mm/h；48 个5分钟区间与04:00终止零值，共49行数据。时间跨度为2024-01-01 00:00至04:00，区间起点值表示之后5分钟内的恒定雨强。

## 生成规则与峰位

每个原始雨强先乘以2或1.5，以half-up规则保留三位小数。然后把目标雨量对应的雨强总和与舍入总和之差加到全局最大雨强区间，保证精确总雨量。总雨量为 Σ(雨强×5/60)，不是梯形积分。

- 单峰：峰值区间01:35–01:40。
- 双峰：局部峰值区间00:40–00:45与02:50–02:55；保留01:50–02:10的20分钟无雨间隔。
- 三峰：局部峰值区间00:25–00:30、01:50–01:55、03:15–03:20；保留01:10–01:25和02:35–02:50的两个15分钟无雨间隔。
- 对照前后峰数、峰位和所有零值时段均一致。细微舍入修正已记录于events.json，不将结果描述成数学上无误差的完全比例缩放。

这些是Chicago-like合成雨型；没有当地IDF标定、没有重现期。80/120/160 mm表示雨量条件，不预设各模型的积水严重程度。

## 九场主矩阵与额外对照

| 雨型 | 80 mm | 120 mm | 160 mm |
|---|---|---|---|
| 单峰 | 已有输入 | 已有输入 | 本次新增 |
| 双峰 | 已有输入 | 本次新增 | 已有输入 |
| 三峰 | 已有输入 | 本次新增 | 本次新增 |

单峰60 mm保持为第10个额外低雨量对照。九场主矩阵输入已齐备，不代表九场模拟或诊断已经完成。本次没有创建新的run目录，没有修改批处理执行计划，也没有重试历史失败案例。既有五场的诊断成功/失败状态不变。

## 校验与曲线图

独立校验检查了：

1. 原有六个TXT的SHA256完全一致。
2. 新增四场的精确总雨量、三位小数、非负值、49行、5分钟间隔和终止零值。
3. 相对原曲线的缩放、舍入校正、峰位、峰数、有效降雨历时和干湿时段。
4. 既有rainfall_context解析函数的雨量、历时、最大雨强及行数兼容性。
5. 九场主矩阵的全部文件存在、总雨量与峰数正确。
6. 已目视检查九场对比图：统一纵轴0–320 mm/h，无峰值截断、无明显标题或刻度重叠。

- [四场新增曲线图](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/rainfall_generation/20261011/additional_rainfall_curves.png)
- [九场矩阵对比图](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/rainfall_generation/20261011/rainfall_comparison_nine_events.png)
- [九场矩阵矢量图](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/rainfall_generation/20261011/rainfall_comparison_nine_events.svg)
- [生成元数据](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/rainfall_generation/20261011/events.json)
- [独立校验结果](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/rainfall_generation/20261011/validation.json)

复用20261009的读取与绘图工具，新增单独的校验脚本：[validate_and_plot_urban_storms_20261011.py](E:/SWMM_Agentic/SWMM-Agentic2/scripts/validate_and_plot_urban_storms_20261011.py)。它不重写降雨文件，不调用模拟或LLM；添加--plot时仅导出图像，已存在的图像拒绝覆盖。

```powershell
# 只读复查
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\validate_and_plot_urban_storms_20261011.py'
```

如需后续模拟，可沿用既有雨后延长3小时的设置；本次只记录该建议，没有执行模拟。

