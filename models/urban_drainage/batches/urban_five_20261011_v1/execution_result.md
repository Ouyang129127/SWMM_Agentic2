## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11
- Verification Status: UNVERIFIED（执行与文件存在性已核对；未做完整数值/诊断准确性验证）
- Version Label: urban_five_execution_v1

## Experiment Result

- ID: urban_five_20261011_v1
- Type: simulation + diagnostic workflow
- Status: failed / partial results retained
- Exit Code: 1
- 工作目录：E:\SWMM_Agentic\SWMM-Agentic2
- 执行时间：2026-10-11 09:52–09:55（Asia/Shanghai，约150秒，含顺序调度等待）
- SWMM–CA2D模拟完成：5/5。
- 证据构建、LLM诊断、核验及简报完成：0/5。
- 实际程序发起的LLM调用：0；自动补证轮数：0；未重试失败案例。

实际执行命令：

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\run_urban_drainage_batch.py' --plan 'E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\batches\urban_five_20261011_v1\plan.json' --execute
```

## 模拟产出

下表来自各新运行的summary.json；溢流体积是保存结果采样积分量，不是独立的物理验证。水深是合成地表模型输出，不代表经实测验证的真实淹没。

| 事件 | 保存结果溢流体积（m³） | 最大地表水深（m） | SWMM/地表时刻数 | 核心文件完整 | 输出文件数/字节 |
|---|---:|---:|---|---|---|
| chicago_like_single_4h_80mm_5min.txt | 34.527 | 0.216 | 421/85 | 是 | 18/60144623 |
| chicago_like_single_4h_120mm_5min.txt | 269.740 | 0.694 | 421/85 | 是 | 18/60793709 |
| chicago_like_double_4h_80mm_5min.txt | 0.000 | 0.000 | 421/85 | 是 | 18/60061914 |
| chicago_like_double_4h_160mm_5min.txt | 278.362 | 0.580 | 421/85 | 是 | 18/60964016 |
| chicago_like_triple_4h_80mm_5min.txt | 0.000 | 0.000 | 421/85 | 是 | 18/60062144 |

每个新run_id与事件绑定见plan.json；每运行保存的核心文件包括summary.json、SWMM的RPT/OUT与节点/管段/溢流TSV、CA2D地表水深与耦合边界TSV。各summary.json约6071字节（实际大小逐案例不同）。

## 失败原因与保留策略

新增批处理入口在调用原模拟工具后，没有执行网页入口原本负责的模拟完成状态交接。模拟输出已齐备，但workflow_state.json仍为SCENARIO_READY；run_workflow_stage因状态不符拒绝进入证据构建。五组均在同一接续点停止，未调用诊断模型。

此次批处理已退出，execution.lock已正常移除。旧案例未覆盖，新模拟结果及全部失败检查点、日志和batch_summary.json均保留。按experiment-agent不自动重试的要求，等待用户确认修复并继续。

建议后续仅修复批处理状态交接，再从当前保存结果构建证据并继续诊断，不重新模拟。需要另存修订后的执行计划，保留此次失败记录，不将其改写为成功。
