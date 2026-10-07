# 第一部分“模拟基本场景”：固定句式与当前确认进度

## 当前已确认的表达

用户已接受开头总述的简短现象与演变概括，也接受第五部分的自然技术表达作为第一版；本轮仅固定第一部分的两段场景描述。

- 总述保留：[总述试写v3](./report_agent_examples/intro_probe_20261007_v3/报告总述_试写.md)。
- 第五部分逐节点分析保留：[自然技术表达试写v2](./report_agent_examples/event_natural_probe_20261007_v2/逐节点分析_试写.md)。
- 第一部分采用：[本轮固定模板输出](./report_agent_examples/scene_template_20261007_v1/模拟基本场景_模板输出.md)。

## 固定句式

> 本次模拟针对UrbanDrainage区域的基准方案，采用历时4小时、累计雨量80毫米的单峰降雨。模拟从00:00开始，降雨于04:00结束，计算继续至07:00，覆盖降雨期间及雨停后3小时的管网和地表变化。

> 报告依次呈现降雨过程、地表积水分布与演变、管网冒溢及其地表联系，并结合节点来水与相邻管段的流量变化解释主要现象。

普通降雨模拟按上述句式填入真实的模型展示名、方案、降雨历时、累计雨量、雨型、开始时刻、降雨结束时刻、计算结束时刻和雨后时长。数据来自当前模拟材料；雨后时长按实际计算结束与降雨结束时刻计算。

小时数为整数时直接写小时，其他时长用小时与分钟组合。正文只使用短时刻，跨午夜标注次日等关系；标题和序号仍由页面显示，不在正文中重复。无降雨、计算与雨同时结束等情况按真实场景调整相应短句，不为了套句式新增雨后模拟。

## 程序与提示词已接入

- [场景模板配置](../workflow_agents/reporting/prompts/scene_template_v1.json)：固定开头、报告内容段落，以及已由用户认可的模型展示名称映射。`UrbanDrainage scenario family`在本节展示为`UrbanDrainage区域`，源模型元数据不修改。
- [场景组装程序](../workflow_agents/reporting/scene.py)：读取真实材料，格式化时长、雨型和短时刻，构造固定段落。
- [场景专门提示词](../workflow_agents/reporting/prompts/scene_fixed_v1.md)：要求模型使用`fixed_sections.scene`，其他章节按各自职责写作。
- [报告正文组装](../workflow_agents/reporting/narrative.py)：场景首段作为一个完整事实标记加入事实表末尾，原有标记顺序不变；正式组装以程序固定内容填写scene，模型原始响应保留，审计来源记录为`program_template`。
- [生成流程](../workflow_agents/reporting/pipeline.py)：版本为`report_agent_v1.7_fixed_scene`。
- [独立构建程序](../scripts/build_report_scene.py)：只构建本节，与已确认的总述和逐节点分析基线合并，保持其他字段原样；本轮未调用语言模型重写场景。
- [降雨形态分类](../workflow_agents/reporting/materials.py)：沿用已有峰值识别，单个峰值为单峰、两个峰值明确为双峰、三个及以上为多峰。当前模拟的单峰分类不变。

## 当前产出与验证

实际材料仍为`20261005_104641`运行、`6b2fbc831220478db26b1006c694e884`诊断任务r2。本轮结果与用户认可的两段逐字一致，数值由当前模拟填写。

输出目录`report_previews/report_agent_examples/scene_template_20261007_v1/`包含正文、`scene.json`、事实表、合并正文及`assembly_result.json`。来源明确记录为程序模板，没有声称这两段是模型新写的。

`python -m unittest discover -s tests -q`：163项通过，其中Report Agent相关44项。新增检查验证模型随意写的场景数值不会进入最终正文且原始响应保留；跨午夜和实际雨后时长正确；单峰、双峰、多峰分别识别。

原HTML与任务状态未修改；合并正文只替换scene，已确认的intro、节点正文及其他章节保持原样。人工核对保存在本轮输出目录`editorial_review.json`。修改前文件保存在`tmp/report_scene_template_20261007/`。

后续继续对标降雨特征、地表淹没与演变、管网冒溢及地表联系、主要结论。完整HTML将在各部分确认后整合，不将当前尚未优化的其他章节当作已完成的最终报告。
