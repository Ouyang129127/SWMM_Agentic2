# Site_Drainage_Model 九场计算诊断批次

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11
- Verification Status: UNVERIFIED（指科学机制准确性）
- Version Label: site_nine_20261011_v1

## 已获授权的范围

Site_Drainage_Model / baseline，单峰、双峰、三峰 × 80、120、160 mm，4 h 降雨。排除 60 mm。用户已明确批准新增模型专用入口并执行全过程。

使用现有模型、已有固定工具和当前核心 Agent 配置，不改算法、提示词、地形、管网参数及雨型。九个独立短运行 ID 与长雨型名通过 plan.json、summary.json 及各场 checkpoint 关联，不以文件夹短名代替情景身份。

## 执行边界

- 顺序执行，各场独立子进程；每场最多 2 轮补证、21 次受控 completion 调用尝试、1,800 s 墙钟硬超时。
- 只允许 evidence_lookup / saved_result_extract 等已有结果补证，不重新模拟、不让 LLM 生成任意执行代码。
- 不覆盖或重试已有 checkpoint，不修改 urban 批次及历史失败。
- 单场失败保留记录并继续其他场景；遇共享认证/限流 HTTP 401/403/429 停止启动后续场景。
- 固定 85 个输入/核心代码文件哈希；每场前复查。
- 模拟完成后显式将运行结果交接至工作流状态，再启动证据构建。
- 核验引用存在不等于机制正确；成功 HTML 也不等于专家准确性验证。

## 命令

工作目录：E:/SWMM_Agentic/SWMM-Agentic2

离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_site_nine_batch -v
```

预检（不运行模拟、不发送 LLM 请求）：

```powershell
.\.venv\Scripts\python.exe scripts\run_site_drainage_batch_20261011.py --plan models\Site_Drainage_Model\batches\site_nine_20261011_v1\plan.json
```

用户已批准的实际执行：

```powershell
.\.venv\Scripts\python.exe -u scripts\run_site_drainage_batch_20261011.py --plan models\Site_Drainage_Model\batches\site_nine_20261011_v1\plan.json --execute
```

## 输出

- runs/s9_1011_01 至 runs/s9_1011_09：模拟、证据、诊断任务及报告。
- 本批目录各场 JSON checkpoint 和日志、batch_summary.json、execution.lock（运行期间）。
- 运行结束后另存 execution_result.md，分列模拟完成、结构化诊断与当前 HTML，不隐藏部分完成状态。

