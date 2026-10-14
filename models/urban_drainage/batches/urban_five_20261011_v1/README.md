# urban_drainage 五事件批处理

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run（准备阶段，尚未执行真实实验）
- Origin Date: 2026-10-11
- Verification Status: UNVERIFIED（真实模拟与诊断尚未运行；离线测试和输入预检查通过）
- Version Label: urban_five_20261011_v1

## 已确认的范围

仅urban_drainage/baseline，按顺序新跑：单峰80 mm、单峰120 mm、双峰80 mm、双峰160 mm、三峰80 mm。排除单峰60 mm。五组均为4小时、5分钟区间降雨，模拟延长至雨后3小时。SWMM结果保存1分钟、耦合边界5分钟、CA2D结果保存5分钟，CA2D内部步长沿用现有10秒。

## 执行边界

- 复用既有Scenario、Simulation、Evidence Builder、Diagnosis、引用核验及Report入口，未修改这些核心模块或当前网页改动。
- 每个案例独立进程、顺序执行，生成新的batch专属run_id，拒绝覆盖既有或部分生成的运行目录。
- 每个案例最多两轮补证。只允许既有证据查询与固定的保存结果提取工具；无新增证据、能力不足、重复请求或达到上限时停止，保留不确定性。
- 当前工具的格式/引用纠错保留既有上限；每个案例最多21次程序发起的provider completion调用（诊断与报告合计，不等于供应商SDK底层HTTP重试次数）。无溢流诊断沿用现有确定性说明，不强制补证。
- 单案例硬超时30分钟，每30秒检查进程与日志增长；输出停滞仅提示，不自动改变参数或重算。硬超时前记录终止提示，然后终止该案例，保留部分产出。
- 失败不自动重试；诊断或报告调用发现HTTP 401/403/429时暂停未开始的案例。
- 只有当前版本的结构化诊断、引用核验和HTML简报均交付，才记为完成；仍有补证缺口则记为completed_with_gaps。引用核验不证明因果判断正确。
- 重新启动同一批次会保留已有检查点，跳过完成、失败和中断的案例；未开始的继续。不会自动恢复失败案例的模拟或诊断。残留运行锁需要核对PID后人工处理，不自动清除。
- plan.json冻结77个输入/实现/提示词文件的散列；执行前及每个案例开始前核对。新增测试文件、该README和批次运行日志不在冻结集合。

## 预检查（不模拟、不调用LLM）

工作目录：E:\SWMM_Agentic\SWMM-Agentic2

```powershell
& '.\.venv\Scripts\python.exe' scripts/run_urban_drainage_batch.py --plan models/urban_drainage/batches/urban_five_20261011_v1/plan.json
```

## 正式启动（待用户确认命令）

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\run_urban_drainage_batch.py' --plan 'E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\batches\urban_five_20261011_v1\plan.json' --execute
```

启动后调用项目已配置的LLM服务，仅沿用原诊断和报告入口传送所需证据/报告材料，不上传论文文件。运行记录仍在各案例runs/内；本批次目录保存每案例检查点JSON、日志及batch_summary.json。

## 离线检查记录

84项离线测试通过，涉及新增批处理策略、模拟接口替身下的流程测试、现有补证/调查流程及报告模块。测试不启动真实SWMM/CA2D或API。

第一次测试调用因两个旧测试模块的测试目录导入路径缺失而未加载；补充PYTHONPATH后84项全部通过。真实实验未重试或运行。
