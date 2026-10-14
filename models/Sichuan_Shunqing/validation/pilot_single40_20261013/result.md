# 顺庆单峰 40 mm 预实验结果

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-13 (Asia/Shanghai)
- Verification Status: PARTIAL（运行、日志和输入一致性已检查；物理准确性与诊断因果准确性未验证）
- Version Label: shunqing-single40-pilot-result-v1

## 结论与执行范围

`sq40_20261013_p1` 已完成情景准备、SWMM–CA2D 耦合模拟和证据构建，首次全场诊断请求被接口以 HTTP 413（Request Entity Too Large）拒绝。没有生成模型诊断结论，故没有执行 Reference_checks、自动补证和 Report Agent 简报。该场必须记为**全流程未完成**，不能用模拟成功替代任务成功；unsupported rate 和诊断准确性均为 N/A，而不是 0。

选用已有 `chicago_like_single_4h_40mm_5min.txt`：总雨量 40 mm、历时 4 h、间隔 5 min，雨峰 2020-07-15 01:35，峰值强度 73.367 mm/h。计算覆盖 2020-07-15 00:00 至次日 00:00。保持 baseline 管网参数、8 个 FREE 出流口、连续道路 v2 与当前单向耦合设置；未改雨量、地形、诊断逻辑或证据结构，未重跑模拟、未重试被拒请求。这是探索性预实验，不是已冻结的正式评估矩阵。

## 已完成阶段及主要输出

| 阶段 | 状态 | 记录 |
| --- | --- | --- |
| 情景准备与模拟 | 完成 | 管网、地表时序，RPT/OUT，最大水深图与动画 |
| Evidence Builder | 完成 | 213,657 条证据；404 个连续冒溢片段，涉及 87 个冒溢节点 |
| Diagnosis Agent | 首次请求失败 | 1 次 configured_completion 调用；HTTP 413；无有效诊断输出 |
| 引用核验、自动补证、简报 | 未执行 | 补证 0 轮；未生成最终报告 |

“404”是同一场降雨内按采样识别的冒溢片段数，不是 404 场降雨，也不能单凭片段数判定真实反复溢流机制。configured_completion 调用次数也不等同于经独立审计的底层 HTTP 请求次数。

## 模拟指标与质量限制

- 冒溢节点：87；最大单节点冒溢流量：20,710.514 L/s，位于 jd65，时刻 01:40，较雨峰晚 5 min。时间接近只表明时序关系，不构成机制归因。
- SWMM 原生冒溢总量：约 1,016,599 m³（RPT 舍入值）；用于地表耦合的采样积分：1,016,727.074 m³，较原生值高约 0.012598%。区间重采样误差另为约 1.51×10⁻⁸ m³，不要将两种误差混为一谈。
- 管网路由连续性误差：+0.139%；地表径流连续性误差：−0.221%；原生报告没有 ERROR/WARNING。但 Most Frequent Nonconverging Nodes 中 psk1–psk5 各为 4.80%，尚需关注局部收敛，不宣称已完成全部数值验证。
- CA2D 内部计算最大水深：12.970 m；最终地表存水约 1,016,726.5 m³。地表采用构造高程、道路与建筑，边界封闭，无地表回流入管网、入渗或其他排水损失，因此大量来水在地表保留。该水深不能作为顺庆真实城市淹没深度或模型实测准确性的证据。

原计划希望测试较低负荷，但本次实测表明：40 mm 对这套约 40 km² 汇水范围的模型已产生广泛冒溢，不能继续称为“轻负荷场景”。最大水深图显示道路附近及局部低处出现积水，这可作为后续分析给定模型现象的材料；管段瓶颈、顶托和地表积水的因果链尚未由本轮 Agent 诊断或人工复核确认。

## 失败边界与复现记录

原全场首轮请求包含 2,440 条可见记录，序列化请求为 72,971,274 个字符。原生 attempt 记录显示错误发生在 completion 阶段，HTTP 状态为 413；没有提供方 token 用量。离线 token 估计只是根据此前案例字符比推算，不能冒充本次真实用量或将本次写成 token 上限错误。

执行结束后复核 19 项冻结输入，哈希全部一致；诊断进程已结束。原始 INP SHA256 仍为 `fc7c00fdb738de0adcbe93535b9cabdc72fef2fa1ea701bb3b937aade5cdf1ea`；雨型 SHA256 为 `acc8ea47e9754f4d70b330aabf9e781f9d92fe8c8192598223ee95d848ae33b3`。保留失败现场，不将其静默替换为小范围诊断成功。

- [执行与阶段记录](execution.json)、[水力指标](hydraulic_quality.json)、[诊断输入预检](diagnosis_input_preflight.json)、[诊断日志](diagnosis.log)、[预先冻结计划](plan.md)。
- [原生诊断失败记录](../../runs/sq40_20261013_p1/diagnosis_tasks/b7555bef02de4449acc3fd774c0c2f7e/diagnosis_attempt_53f0a2bf6a864e7fb1dfe6c8a1b119dd.json)。
- [模拟总览](../../runs/sq40_20261013_p1/summary.json)、[原生管网报告](../../runs/sq40_20261013_p1/swmm/model.rpt)。
- [最大积水深度图](../../runs/sq40_20261013_p1/ca2d/ca2d_max_depth.png)、[积水动画](../../runs/sq40_20261013_p1/ca2d/ca2d_animation.gif)。

后续若选择更小雨量或对同一场的单个冒溢对象进行限定诊断，应作为明确标注的新实验/新任务，保留本场完整记录，不能视为本次全场任务已经成功。
