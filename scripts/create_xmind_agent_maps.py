import json
import uuid
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "paper_assets" / "xmind"


def xid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def topic(title, children=None, note=None):
    item = {
        "id": xid("topic"),
        "title": title,
    }
    if children:
        item["children"] = {"attached": children}
    if note:
        item["notes"] = {"plain": {"content": note}}
    return item


def sheet(root_title, children, sheet_title):
    return {
        "id": xid("sheet"),
        "title": sheet_title,
        "rootTopic": topic(root_title, children),
        "topicPositioning": "fixed",
    }


def write_xmind(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "creator": {
            "name": "Codex",
            "version": "1.0",
        },
        "created": "2026-07-25T00:00:00+08:00",
        "modified": "2026-07-25T00:00:00+08:00",
    }
    manifest = {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
            "manifest.json": {},
        }
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def v2_content():
    return [
        sheet(
            "SWMM-2D-Agentic Agent 协同逻辑 V2",
            [
                topic(
                    "用户 / 专家任务",
                    [
                        topic("自然语言问题"),
                        topic("降雨情景"),
                        topic("诊断需求"),
                    ],
                ),
                topic(
                    "Orchestrator Agent",
                    [
                        topic("任务理解"),
                        topic("流程拆解"),
                        topic("工具选择"),
                    ],
                ),
                topic(
                    "Scenario Agent",
                    [
                        topic("降雨事件识别"),
                        topic("情景配置"),
                        topic("边界条件组织"),
                        topic("连接：降雨事件库 / 情景库"),
                    ],
                ),
                topic(
                    "Simulation Agent",
                    [
                        topic("SWMM-2D 标准化模拟流程调度"),
                        topic(
                            "SWMM 管网模型",
                            [
                                topic("节点"),
                                topic("管段"),
                                topic("泵站"),
                                topic("子汇水区"),
                            ],
                        ),
                        topic(
                            "CA2D 二维地表积水模型",
                            [
                                topic("DEM"),
                                topic("网格"),
                                topic("阻力"),
                                topic("节点映射"),
                            ],
                        ),
                    ],
                ),
                topic(
                    "SWMM 原始输出",
                    [
                        topic("nodes.tsv"),
                        topic("links.tsv"),
                        topic("node_flooding.tsv"),
                        topic("rpt / out"),
                    ],
                ),
                topic(
                    "CA2D 原始输出",
                    [
                        topic("由 SWMM 溢流输入与 CA2D 地表模型共同生成"),
                        topic("surface_depth.tsv"),
                        topic("max depth map"),
                        topic("final depth map"),
                    ],
                ),
                topic(
                    "Data Extraction Agent",
                    [
                        topic(
                            "Evidence Table",
                            [
                                topic("evidence_id"),
                                topic("object_id"),
                                topic("metric"),
                                topic("value"),
                                topic("time"),
                                topic("source_file"),
                            ],
                        )
                    ],
                ),
                topic(
                    "Flood Diagnosis Agent",
                    [
                        topic("热点识别"),
                        topic("风险排序"),
                        topic("致灾因子判断"),
                        topic("Diagnosis Claims"),
                    ],
                ),
                topic(
                    "Evidence Verification Agent",
                    [
                        topic("证据核查"),
                        topic("无证据建议拦截"),
                        topic("Verified Claims and Recommendations"),
                        topic("Unsupported Items"),
                    ],
                ),
                topic(
                    "Evidence Explanation Agent",
                    [
                        topic("结构化证据翻译成人话"),
                    ],
                ),
                topic(
                    "Report Agent",
                    [
                        topic("Evidence-grounded Emergency Brief"),
                        topic("Benchmark Outputs"),
                        topic("论文 Results：Fig. 4 / Fig. 5 / Fig. 6 / Fig. 7"),
                    ],
                ),
            ],
            "V2 纵向协同逻辑",
        )
    ]


def v5_content():
    return [
        sheet(
            "SWMM-2D-Agentic Agent 协同逻辑 V5",
            [
                topic(
                    "1. 任务编排模块",
                    [
                        topic("用户 / 专家任务：自然语言问题、降雨情景、诊断需求"),
                        topic("Orchestrator Agent：任务理解、流程拆解、工具选择"),
                        topic("Scenario Agent：降雨识别、情景配置、边界条件"),
                        topic("Simulation Agent：SWMM-2D 标准化模拟流程调度"),
                    ],
                ),
                topic(
                    "2. 模型计算模块",
                    [
                        topic("降雨事件库 / 情景库：events, scenario configs"),
                        topic("SWMM 管网模型：节点、管段、泵站、子汇水区"),
                        topic("SWMM 原始输出：nodes、links、node_flooding、rpt/out"),
                        topic("CA2D 二维地表积水模型：DEM、网格、阻力、节点映射"),
                        topic("CA2D 原始输出：SWMM 溢流 + CA2D 地表模型共同生成"),
                    ],
                ),
                topic(
                    "3. 证据构建模块",
                    [
                        topic("Data Extraction Agent：模型结果结构化抽取"),
                        topic(
                            "Evidence Table",
                            [
                                topic("evidence_id"),
                                topic("object_id"),
                                topic("metric"),
                                topic("value"),
                                topic("time"),
                                topic("source_file"),
                            ],
                        ),
                        topic("Scenario Summary：run_id、event、scenario、关键统计指标"),
                    ],
                ),
                topic(
                    "4. 诊断与核查模块",
                    [
                        topic("Flood Diagnosis Agent：热点识别、风险排序、致灾因子"),
                        topic("Diagnosis Claims：热点、风险等级、优先级"),
                        topic("Evidence Verification Agent：证据核查、无证据建议拦截"),
                        topic("Verified / Unsupported：有证据支持或证据不足"),
                    ],
                ),
                topic(
                    "5. 解释、报告与评价模块",
                    [
                        topic("Evidence Explanation Agent：结构化证据翻译成人话"),
                        topic("Report Agent：证据约束应急简报生成"),
                        topic("Emergency Brief：管理部门可读简报"),
                        topic("Benchmark Outputs：task success、F1、Spearman、unsupported rate"),
                        topic("论文 Results：Fig. 4、Fig. 5、Fig. 6、Fig. 7"),
                    ],
                ),
                topic(
                    "推荐阅读路径",
                    [
                        topic("左上：任务编排"),
                        topic("右上：模型计算"),
                        topic("右中：证据构建"),
                        topic("左中：诊断与核查"),
                        topic("下方：解释、报告与评价"),
                    ],
                ),
            ],
            "V5 方正版模块逻辑",
        )
    ]


def main():
    write_xmind(OUT_DIR / "agent_collaboration_logic_v2.xmind", v2_content())
    write_xmind(OUT_DIR / "agent_collaboration_logic_v5.xmind", v5_content())
    print(OUT_DIR / "agent_collaboration_logic_v2.xmind")
    print(OUT_DIR / "agent_collaboration_logic_v5.xmind")


if __name__ == "__main__":
    main()
