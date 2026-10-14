# beta 低雨量九场矩阵：剩余八场完整执行

## Material Passport
- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-14 (Asia/Shanghai)
- Verification Status: UNVERIFIED（程序、引用与工程因果正确性分开核验）
- Version Label: beta-lowrain-nine-v1

## 用户确认的矩阵
单峰、双峰、三峰 × 20、40、60 mm，共九场。已完成单峰 20 mm（ba20_7h_20261014），本批次仅执行剩余八场，不重新模拟或重新调用它的诊断。原 80/120/160 mm 清单与结果不删除。

新增六个双/三峰事件以相同雨型的 80 mm 原文件为源，比例缩放强度，保留原时间戳、峰数、峰时和干间隔，强度三位小数并在最大峰修正取整差额，使 5 min 区间积分恰好达到目标总量。来源和生成参数见 events/lowrain_generation_20261014.json；九场独立校验见 events/lowrain_matrix_20261014.json。

所有案例固定 adapted_s1_wsqrt 改编情景：165 个子汇水区坡度 1%，宽度 sqrt(面积 m²)，原潮位 base_30、既有管网、地表、求解与控制设置不修改。2016-10-08 00:00—04:00 降雨，雨后延长 3 h，实际模拟至 07:00。输出间隔 SWMM 1 min、边界及 CA2D 5 min、CA2D dt=10 s；须核对 421 / 85 个保存时刻。

## 流程与边界
逐场单独进程、顺序执行：Scenario → SWMM–CA2D → 显式状态交接 → Evidence Builder → Diagnosis → Reference_checks → 结构化报告及 HTML → 至多两轮固定工具补证及再交付。

每场 completion 调用上限 21 次、完整案例硬超时 30 min；沿用已有解析/验证/报告文案补正。不修改证据结构、不压缩输入、不改诊断对象范围来绕过上下文拒绝。案例失败保留后继续下一场；认证、限流或共用服务错误停止启动剩余案例，不静默重试。父进程监测存活、耗时与日志；超时只终止自己启动的案例进程树，阶段停滞提示不自动杀进程。

新运行使用短目录 bl_1014_01 至 bl_1014_08。冻结配置、模型、事件、代码、静态地表和已完成案例的关键文件哈希，逐场复查；不允许覆盖已存在运行。

数值质量、事件计数、请求大小、引用检查和实际交付状态分别报告。Reference_checks 通过不等于语义 unsupported rate=0 或专家准确率=100%；物理/因果准确性仍待专家评估。剩余不可用证据和未执行案例必须明确列出。

命令：`.venv/Scripts/python.exe -u scripts/run_beta_lowrain_batch_20261014.py --plan models/pystorms_beta/batches/beta_lowrain_20261014_v1/plan.json --execute`。
