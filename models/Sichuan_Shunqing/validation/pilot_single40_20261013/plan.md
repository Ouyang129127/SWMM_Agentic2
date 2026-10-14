# 顺庆单峰 40 mm：首场全流程预实验

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-13 (Asia/Shanghai)
- Verification Status: UNVERIFIED（执行记录；非独立物理或因果验证）
- Version Label: shunqing-single40-pilot-v1

## 冻结条件

用户要求选一个降雨进行模拟与诊断。本轮选用已有 4 h、40 mm、5 min 单峰候选雨，不作重现期声明。理由是先测试中低负荷的响应和流程，不预设它一定无冒溢、数值可信或能被 LLM 接受。该场是预实验，不据此冻结论文正式矩阵。

- model_name: Sichuan_Shunqing
- run_id: sq40_20261013_p1；如存在则拒绝覆盖。
- event: events/chicago_like_single_4h_40mm_5min.txt
- scenario: baseline；八个原 FREE 出流口，LPS/DYNWAVE，原 1 s 路由步长。
- static: 连续道路 v2，20 m 网格；保持当前地形、建筑、道路构造、单向耦合。
- 时间：2020-07-15 00:00–04:00 降雨，计算至 2020-07-16 00:00；SWMM 报告 1 min、边界区间平均与 CA2D 输出 5 min、CA2D 内步长 10 s。
- 自动补证：仅 evidence_lookup / saved_result_extract / unavailable，已保存结果，最多两轮；不重新模拟或添加新水力情景。
- 模型调用：沿用项目 configured_completion；每场最多 21 次（诊断、原生修正和简报合计），不切换提供方。真实错误保留；不重试 HTTP 拒绝、超限或网络失败。现有工作流对格式、引用校验的限定修正保留。
- 每阶段硬时限 30 min，监测进程和结果增长；停滞只提示，不自动中止。输入哈希、日志与阶段状态留档。

## 阶段与判据

1. Scenario Agent 固定请求；Simulation Agent 执行现有工具，明确发布 RUN_READY。
2. 检查原生 RPT 连续性、ERROR/WARNING、峰值与采样积分差，区分真实冒溢节点和输入节点数。
3. Evidence Builder；离线构建原全场首轮诊断请求并记录规模，不压缩、删事件或改证据结构。
4. 使用现有 Diagnosis → Reference_checks → Report 流程，必要时进行两轮以内的固定工具补证。
5. 完整交付要求当前诊断、引用核查、结构化结果和通过交付检查的 HTML 均完成。任何中间失败单独记录，不把模拟成功称为诊断成功；引用检查通过不等于因果或工程准确性通过。

若数值迹象有疑点，输出仅解释“给定模拟结果”，明确质量限制，不借诊断话术替代引擎验证。此轮不改模型参数、不降低雨量重选样、不优化诊断结构。
