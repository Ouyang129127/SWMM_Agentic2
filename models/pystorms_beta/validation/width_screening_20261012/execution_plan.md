# 已确认：beta 汇流宽度单参数预实验

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-12 (Asia/Shanghai)
- Verification Status: UNVERIFIED（理想化参数对照，未现场校准）
- Version Label: beta-width-sqrt-area-single-40mm-v1

用户已同意 proposal.md 中的规则：165 个子汇水区宽度 W_i=√A_i，面积先由 ha 转为 m²，宽度输出 m。保留 1% 坡度，以已有 slope_screening_20261012 试验作为直接对照；原 100% 坡度版仅作背景。新输入从已运行的 1% 坡度试验复制，只修改 SUBCATCHMENTS 的 Width 字段；宽度保留 9 位有效数字，并核查舍入误差。

固定 40 mm 单峰 4 h 降雨、原潮位、管网、其他产流参数、初始状态、24 h 窗口、动态波求解参数和一分钟输出。仅执行现有 simulation_timing.export_native_reports 一次，不执行 CA2D、Evidence Builder 或 LLM，不替换正式 baseline。不扩大为额外宽度倍数或降雨试验，不重算对照。

新输出置于本目录 swmm/，实验输入 model_slope1_widthsqrtA_40mm.inp。调用前拒绝覆盖已有运行结果，记录差异与保护源文件哈希；执行时记录进程、耗时并监控返回，最长 30 min，失败留档不静默重试。

读取新旧原生 RPT、OUT 与保存时序，比较系统径流峰值/峰时、雨后拖尾、末时径流与地表蓄水、入网累计量、冒溢节点/片段、原生洪水损失及保存样本积分、连续性误差与不收敛比例。若宽度增大导致水力负荷增强，不以更多冒溢当作模型错误，也不以少冒溢或小输入当作改编成功。该宽度规则是统一理想化几何假设，不是实际边界恢复或实测校准。
