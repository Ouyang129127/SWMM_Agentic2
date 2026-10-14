# beta 20 mm：雨后延长 3 h 的完整重算

## Material Passport
- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-14 (Asia/Shanghai)
- Verification Status: UNVERIFIED（执行、引用与工程因果准确性分开判定）
- Version Label: beta-adapted20-7h-v1

## 本轮范围
运行 ba20_7h_20261014；情景 adapted_s1_wsqrt；降雨 chicago_like_single_4h_20mm_5min.txt。与 ba20_20261013_p1 使用相同降雨、坡度 1%、宽度 sqrt(面积 m²)、潮位、管网与合成地表。只改变运行窗口：2016-10-08 00:00 至 07:00，即 4 h 雨 + 3 h 尾段。新窗口真实重新计算，不裁剪旧结果冒充新实验。

既有 24 h 案例及其诊断、失败、补正记录保留。原始模型与 baseline 不修改。输出间隔保持 SWMM 1 min、边界和 CA2D 5 min，CA2D dt=10 s。预期保存 SWMM 421 个时刻、CA2D 85 个时刻；实际产出必须核对。

流程采用已有运行器与工作流 API，不改变诊断架构或 LLM 输入结构：情景 → SWMM–CA2D → 显式状态交接 → Evidence Builder → Diagnosis → Reference_checks → 结构化报告与 HTML。补证仅使用已有结果固定工具，最多两轮；completion 调用最多 21 次。沿用现有解析、引用及报告文案补正规则；失败留档，不重新模拟或无边界重试。

每阶段硬上限 30 min，监测进程与产出。已有 24 h 案例有 −9.314% 管网水量平衡误差，不能预设缩短窗口会改善该问题。本轮分别记录实际数值质量、流程状态、引用状态和未解决证据缺口。专家准确性和语义 unsupported rate 不因程序成功而自动赋值。

命令：`.venv/Scripts/python.exe -u scripts/run_beta_adapted20_7h_20261014.py`。
