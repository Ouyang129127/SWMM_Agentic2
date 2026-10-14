# beta 子汇水区坡度单参数对照

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-12 (Asia/Shanghai)
- Verification Status: UNVERIFIED（预实验设计；不代表现场校准）
- Version Label: beta-slope-1pct-single-40mm-v1

## 已获同意的试验

将 165 个子汇水区的 Slope 从 100.0（%）调整为 1.0（%），其他参数不变。1% 是理想化试验值，不是该匿名场地的实测值。原 beta.inp、SI baseline 与全部已有结果保留。

比较对象为已完成的 bs40_20261012_p1：4 h、5 min 单峰 40 mm，2016-10-08 00:00–04:00，雨峰 01:35，计算至次日 00:00。选择此场是为了对照其雨后单点冒溢尖峰，并非按 LLM 是否接受请求选样。

从该场已执行的 model_with_event.inp 复制实验输入，只修改 SUBCATCHMENTS 中的坡度字段，以数据行逐项核查其他输入一致性。宽度 0.3048 m、面积、不透水率、糙率、入渗、洼蓄、初始状态、设施、潮位 base_30、动态波求解参数和 1 min 报告间隔不变。不改变 CA2D 地表；本轮不执行 CA2D、Evidence Builder、Diagnosis、Verification 或 Report Agent。

## 执行与观察

使用现有 simulation_timing.export_native_reports 执行一次 SWMM，输出到本目录 swmm/。已有 100% 场景不重算。保留新 RPT、OUT、节点/管段/冒溢表、执行记录和输入差异。阶段硬时限 30 min；失败留档不自动重试。

比较原生径流累计量及系统产流过程、入网流量峰值和峰时、冒溢节点数与采样片段数、原生洪水损失、保存样本积分洪水量、雨停后单点尖峰、连续性误差及原生非收敛报告。积分注明使用一分钟保存值而非引擎内部累计；原生 RPT 体积注明舍入。

原 40 mm CA2D 输入为保存流量经既有区间平均边界处理的体积，不能用它当作 SWMM 原生洪水累计。新试验的采样积分只作同口径水力比较，不宣称已生成新的地表积水结果。

## 判读边界

该试验回答固定模型和雨型下改变坡度是否改变产流、尖峰和求解表现；一个试验不能证明原始坡度设置错误，也不能证明所有异常均由坡度引起。无实测数据，不称为校准。若仅表现为径流被拖延或截断在窗口外，应检查尾段产流和蓄水，不把暂时无冒溢视为问题解决。

若需要进一步调整宽度、潮位、步长或计算窗口，另行讨论并保留独立版本，本轮不连带改动。
