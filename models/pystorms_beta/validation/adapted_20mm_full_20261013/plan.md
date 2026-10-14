# beta 改编模型：20 mm 完整诊断流程试跑

## Material Passport
- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-13 (Asia/Shanghai)
- Verification Status: UNVERIFIED（执行与来源核对不等同于水力或因果准确性验证）
- Version Label: beta-adapted-20mm-full-v1

## 已授权范围
独立运行 `ba20_20261013_p1`，使用 `adapted_s1_wsqrt` 情景。165 个子汇水区坡度为 1%，宽度为 sqrt(面积 m²)，其余配置沿用上一轮改编试验。原始文件与 baseline 不覆盖。

源 INP：validation/width_screening_20261012/swmm/model_slope1_widthsqrtA_40mm.inp；SHA256：be438d3e9dd9e8c7130dad71e311651f0460852f09ba8010d7b0809df01c0ebf。

降雨：events/chicago_like_single_4h_20mm_5min.txt；SHA256：a378a2850a7941f3d480dda18f68e78740283dfba33999a1d9e2dbbbb7fcec50。4 h 单峰，总量 20 mm，峰值约 36.682 mm/h。

保留 base_30 潮位、既有理想化地表、CA2D dt=10 s。SWMM 保存 1 min、边界与 CA2D 保存 5 min，雨后延长 20 h，总时段 24 h。

## 执行与停机
情景准备 → 耦合模拟 → 显式状态交接 → 证据构建 → 初步诊断 → 引用核验 → 结构化报告与 HTML；如有可执行补证，仅调用已有结果的固定工具，最多两轮，每场最多 21 次已配置 completion 调用。沿用已有流程的解析/验证补正，不新增自动重试或改变诊断逻辑。各阶段 30 min 硬上限；异常保留产物，不重新模拟。

## 判读边界
上一轮 40 mm 改编试验仍有不收敛与异常瞬时溢流，本场必须记录数值质量，不能预设改编已解决这些问题。匿名坐标、合成道路与高程只验证给定模型中的解释，不作为真实淹没复现。程序成功、引用核查通过、专家判断准确分别记录；失败不计算成 unsupported rate=0。
