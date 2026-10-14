# 四组新增雨情：计算与诊断执行结果

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11 (Asia/Shanghai)
- Verification Status: UNVERIFIED（因果准确性未由专家评分；工件来源与结构已复查）
- Version Label: urban_four_result_v3

## 执行结果

- Type: simulation + analysis
- Status: 全部四个场景已处理；四组模拟成功，完整补证后HTML交付为0/4。
- Exit Code: 1（最终调度器；表示未实现全部端到端交付，不表示四组模拟失败）。
- Working Directory: E:\SWMM_Agentic\u4。原项目未移动，原记录不覆盖。
- 最终续跑段调度耗时合计570.047秒，约9.50分钟；不是整次实验总耗时。
- 原第三组墙钟历时7396.316秒，约123.27分钟，跨越线程/监控中断；活动计算时间未知，原30分钟硬超时未执行，不能将其报告为合规限时运行。
- 总共四次新模拟：前三次在原目录，最后一次在短目录；没有重新模拟任何已算案例。短目录副本与续跑仍对应相同四场雨，不新增独立场景。
- 每组累计completion尝试不超过21、补证尝试不超过2；没有扩大轮数或自动重试双峰120的解析失败。
- 最终调度器与子进程均已结束；最终execution.lock已移除。此前两段停止调度器的锁可恢复地改名留档。

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\u4\scripts\finish_urban_four_short_20261011.py' --plan 'E:\SWMM_Agentic\u4\models\urban_drainage\batches\urban_four_short_20261011_v3\plan.json' --execute
```

## 场景与分阶段状态

| 事件 | 最大地表水深 / m | 采样冒溢输入体积 / m³ | 诊断事件数 | 最新阶段结果 | completion尝试累计 | 补证尝试累计 |
|---|---:|---:|---:|---|---:|---:|
| 单峰160 mm | 1.035233 | 745.667603 | 13 | 初版HTML保留；补证后诊断上下文超限 | 7 | 2 |
| 双峰120 mm | 0.229738 | 43.422613 | 5 | 初次诊断两次JSON解析失败；不重试 | 2 | 0 |
| 三峰120 mm | 0.169212 | 34.136519 | 5 | r2结构化诊断与核验完成；HTML材料阶段失败 | 6 | 2 |
| 三峰160 mm | 0.480505 | 201.388487 | 14 | 初版HTML保留；补证后诊断上下文超限 | 4 | 1 |

体积来自CA2D边界采样后的source_volume_m3，不代替SWMM原生总冒溢积分。最大地表水深是模拟网格结果，不是实测水深或诊断准确性指标。所有四组都发生正地表入流。

## 可用产物

- [单峰160：补证前初版HTML](<E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/runs/chicago_like_single_4h_160mm_5min__baseline__batch_20261011_additions_v1_01/diagnosis_tasks/f0cea8c3e8204e7fa79625baeca0c4f9/display_reports/r1/20261011_112524_97b4f0c0/模拟诊断报告.html>)
- [三峰120：当前r2结构化诊断Markdown](<E:/SWMM_Agentic/u4/models/urban_drainage/runs/chicago_like_triple_4h_120mm_5min__baseline__batch_20261011_additions_v1_03/diagnosis_tasks/8fcabaab70f647bf907b3d03094a2992/preliminary_report_r2.md>)
- [三峰160：补证前初版HTML](<E:/SWMM_Agentic/u4/models/urban_drainage/runs/chicago_like_triple_4h_160mm_5min__baseline__batch_1011_04/diagnosis_tasks/ed8a7092101e41398c637ee575c799c6/display_reports/r1/20261011_135342_0c88834e/模拟诊断报告.html>)
- [最终状态汇总](E:/SWMM_Agentic/u4/models/urban_drainage/batches/urban_four_short_20261011_v3/batch_summary.json)
- [独立工件复查](E:/SWMM_Agentic/u4/models/urban_drainage/batches/urban_four_short_20261011_v3/artifact_inspection.json)
- [最终冻结计划](E:/SWMM_Agentic/u4/models/urban_drainage/batches/urban_four_short_20261011_v3/plan.json)
- [短路径/配置恢复说明](E:/SWMM_Agentic/u4/models/urban_drainage/batches/urban_four_short_20261011_v3/README.md)
- [原执行与监控中断说明](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/batches/urban_four_20261011_v1/continuation_note.md)

两份HTML均通过历史材料来源、文件哈希、章节/事件覆盖及嵌入图像完整性检查。单峰160有13个事件、19张嵌入图；三峰160有14个事件、20张嵌入图。它们是补证前的初版，不是补证后的当前完整交付。补证后state可见证据已变化，因此两份初版不能通过当前证据绑定检查；不能把它们计为端到端成功。

三峰120的r2绑定复查通过，当前内部Markdown及48/48引用核验可供专家检查，但没有合格r2 HTML。

## 失败分类

### 单峰160与三峰160：输入预算超限

单峰160成功保存3份补证文件，可见证据94→128。修订诊断HTTP400：消息2491778 tokens，超过供应商响应注明的1048576 tokens上限。

三峰160成功保存2份补证文件，最终128项可见证据。初版诊断与124/124引用核验及HTML完成；第一轮补证后请求为1269463 tokens，超过同一上限。

没有成功生成对应补证后的诊断或新HTML。没有换模型、压缩/截断证据、追加重试。两者应归为补证—输入容量衔接失败，不能归为水力模拟失败，也不能据此声称诊断结论在因果上错误。

### 双峰120：结构化输出解析失败

两次返回均JSONDecodeError（property name未按JSON要求使用双引号），修正后仍未通过。r0没有合格诊断或报告。原始返回和尝试审计均保留；没有因路径修复而重试这组。

### 三峰120：修订成功，但报告数据范围不兼容

r2诊断完成，48/48引用检查通过，三个补证文件及61项可见证据已绑定；HTML在materials阶段KeyError('G4')，尚未发生r2报告文字LLM调用。

只读复查表明：Report材料按(event_id, metric_name)单条选择local_process_series，补证的较窄过程记录覆盖首轮完整过程记录，随后仍按首轮local_structure的全部目标节点邻接管段取值。P6:E001选中过程缺G4/G5，P42:E001选中过程缺G39/G40。不是模型中不存在这些管段，也不是诊断JSON缺引用。当前核心没有做兼容修复，失败留档。

## 环境与准备故障（不与诊断算法失败混用）

原补证JSON路径262字符、临时文件261字符，Windows长路径未启用。独立写入测试复现FileNotFoundError，短工作副本可正常写入，已有补证文件证实路径补救有效。此故障由新批次路径规划造成，不能作为诊断推理质量的反例。

短副本初次遗漏原项目.env，两个修订诊断在llm.py的API配置检查中失败；原配置随后只在本地逐字节复制，没有打印密钥或修改模型/供应商。这是本次执行准备错误，不是模型推理失败。两个失败的completion尝试均保留并仍计入累计上限。

原生审计network_call_started在调用配置函数之前设True，不证明实际HTTP已发出。根据llm.py客户端构造前的require_api_key检查，这两次Missing API key没有发出有效provider请求。不能使用该布尔标记直接计算真实HTTP请求准确率或费用。

原调度器停止后第三组在中断期间自然结束，报告出现APIConnectionError；原超时监控未执行。网络失败、路径失败、配置遗漏和时间监控异常均保留，不能删去后把本批描述成无干预成功。

## 一致性、预算与论文使用边界

- 原冻结85项输入/代码未改变；短副本最终冻结94项均未改变。
- 前三组48项模拟工件，在原项目与短目录两处逐一SHA256核对，无变化。
- 初次入口94项联合离线测试通过；短路径8项离线检查通过；恢复守卫及执行前后只读校验通过。不是四组端到端成功率证明。
- 累计completion尝试19次（单峰7、双峰2、三峰120为6、三峰160为4），包括两个本地配置失败；并非19次成功HTTP调用，也非SDK内部HTTP重试总数。最后续跑段新增6次尝试。
- 有usage的原生审计合计prompt_tokens=3687498、completion_tokens=309829；缺usage的失败请求未计入，不能直接推算费用。
- 单峰160的120/120与三峰160的124/124属于初版引用核验，不能升级为补证后验证；三峰120的48/48为当前r2引用核验。引用检查不等于unsupported rate或专家诊断准确率。
- 失败可保留在任务流程评估中，但应分阶段、分环境/解析/输入预算/报告兼容性解释；未产出诊断的病例不能记作unsupported rate=0。
- 本次遵循实验执行技能保留失败、分开记账和来源冻结要求；没有修改诊断核心、核验核心或报告核心，也没有进行专家因果验证。

至此urban_drainage的单/双/三峰×80/120/160 mm九场主矩阵均有模拟结果；60 mm额外案例不计入这九场。当前新增四场均未达到补证后HTML闭环成功，不能用已有初版产物掩盖这一点。

