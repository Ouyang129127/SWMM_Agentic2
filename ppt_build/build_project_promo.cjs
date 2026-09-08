const fs = require("fs");
const fsp = fs.promises;
const path = require("path");
const { pathToFileURL } = require("url");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const { chromium } = require("playwright");
const JSZip = require("jszip");

const ROOT = "E:\\SWMM_Agentic\\SWMM-Agentic2";
const BUILD = path.join(ROOT, "ppt_build");
const ASSETS = path.join(BUILD, "assets");
const OUT = path.join(ROOT, "ppt_output");
const FINAL = path.join(OUT, "SWMM-Agentic2_项目宣传版.pptx");

const P = {
  maxDepth: path.join(ROOT, "models\\songhua_swmm_2d\\runs\\rain1__baseline__20260721_165600\\ca2d\\ca2d_max_depth.png"),
  finalDepth: path.join(ROOT, "models\\songhua_swmm_2d\\runs\\rain1__baseline__20260721_165600\\ca2d\\ca2d_final_depth.png"),
  frontend: path.join(ROOT, "outputs\\frontend-desktop.png"),
  rain4: path.join(ROOT, "models\\songhua_swmm_2d\\runs\\rain4__baseline__20260812_101435\\ca2d\\ca2d_max_depth.png"),
  agentFlow: path.join(ROOT, "模拟路线图\\agent_collaboration_logic_morandi_vertical.html"),
  evidenceFlow: path.join(ROOT, "模拟路线图\\evidence_table_generation_flow.html"),
  diagnosisFlow: path.join(ROOT, "模拟路线图\\diagnosis_agent_workflow.html"),
  verificationFlow: path.join(ROOT, "模拟路线图\\verification_agent_workflow.html"),
  graphFlow: path.join(ROOT, "模拟路线图\\ontology_inspired_evidence_graph_morandi.html"),
  webIndex: path.join(ROOT, "模拟路线图\\innovation_presentation\\index.html"),
  webObject: path.join(ROOT, "模拟路线图\\innovation_presentation\\01-object.html"),
  webArchitecture: path.join(ROOT, "模拟路线图\\innovation_presentation\\02-architecture.html"),
  webDiagnosis: path.join(ROOT, "模拟路线图\\innovation_presentation\\03-diagnosis.html"),
  webRelation: path.join(ROOT, "模拟路线图\\innovation_presentation\\04-relation-graph.html"),
  webEval: path.join(ROOT, "模拟路线图\\innovation_presentation\\05-evaluation.html"),
  webPackage: path.join(ROOT, "模拟路线图\\innovation_presentation\\06-evidence-network-package.html"),
  webWorkflow: path.join(ROOT, "模拟路线图\\innovation_presentation\\workflow.html"),
};

const C = {
  bg: "F4F6F8",
  warm: "F3F0EA",
  ink: "17212B",
  ink2: "34403C",
  muted: "617080",
  line: "D8DEE7",
  panel: "FFFFFF",
  panel2: "FBFCFD",
  blue: "DCE9F8",
  blueLine: "5F83AD",
  green: "E0EFE6",
  greenLine: "5B8B69",
  amber: "FFF0C7",
  amberLine: "BD9130",
  rose: "F7E1DF",
  roseLine: "B56A64",
  purple: "EBE5F6",
  purpleLine: "7969A4",
  dark: "25313B",
  dark2: "17212B",
};

const SW = 13.333;
const SH = 7.5;
const FONT = "Microsoft YaHei";
let pptx;

async function exists(p) {
  try { await fsp.access(p); return true; } catch { return false; }
}

async function cropImage(input, output, width = 1600, height = 900) {
  if (await exists(output)) return output;
  if (!(await exists(input))) return null;
  await sharp(input).resize(width, height, { fit: "cover", position: "centre" }).png().toFile(output);
  return output;
}

async function fitImage(input, output, width = 1600, height = 900) {
  if (await exists(output)) return output;
  if (!(await exists(input))) return null;
  await sharp(input)
    .resize(width, height, { fit: "contain", background: "#f4f6f8" })
    .png()
    .toFile(output);
  return output;
}

async function screenshotHtml(browser, input, output) {
  if (await exists(output)) return output;
  if (!(await exists(input))) return null;
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(input).href, { waitUntil: "networkidle" });
  await page.screenshot({ path: output, fullPage: false });
  await page.close();
  return output;
}

function hex(c) { return c.startsWith("#") ? c : `#${c}`; }

function safeShadow() {
  return { type: "outer", color: "8390A0", opacity: 0.16, blur: 1, angle: 45, distance: 1 };
}

function addBg(slide, color = C.bg) {
  slide.background = { color };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: SW, h: 0.08, fill: { color: C.blueLine }, line: { color: C.blueLine } });
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0.08, w: SW, h: 0.035, fill: { color: C.greenLine }, line: { color: C.greenLine } });
}

function addTitle(slide, title, kicker = "") {
  slide.addText(kicker, {
    x: 0.62, y: 0.38, w: 3.2, h: 0.28,
    fontFace: FONT, fontSize: 9, bold: true, color: C.purpleLine,
    margin: 0, breakLine: false, fit: "shrink",
  });
  slide.addText(title, {
    x: 0.62, y: 0.66, w: 11.8, h: 0.55,
    fontFace: FONT, fontSize: 28, bold: true, color: C.ink,
    margin: 0, fit: "shrink",
  });
  slide.addShape(pptx.ShapeType.rect, { x: 0.62, y: 1.34, w: 1.15, h: 0.045, fill: { color: C.greenLine }, line: { color: C.greenLine } });
  slide.addShape(pptx.ShapeType.rect, { x: 1.84, y: 1.34, w: 0.42, h: 0.045, fill: { color: C.roseLine }, line: { color: C.roseLine } });
}

function footer(slide, n) {
  slide.addText("SWMM-Agentic2 · 城市内涝 Agentic 诊断工作流", {
    x: 0.62, y: 7.08, w: 7.5, h: 0.22, fontFace: FONT, fontSize: 8.5, color: C.muted, margin: 0,
  });
  slide.addText(`${n} / 20`, {
    x: 12.0, y: 7.08, w: 0.75, h: 0.22, fontFace: FONT, fontSize: 8.5, color: C.muted, margin: 0, align: "right",
  });
}

function panel(slide, x, y, w, h, fill = C.panel, line = C.line) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.07,
    fill: { color: fill },
    line: { color: line, width: 1 },
    shadow: safeShadow(),
  });
}

function label(slide, text, x, y, w, fill, line, color = C.ink) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.38, rectRadius: 0.06, fill: { color: fill }, line: { color: line, width: 1 } });
  slide.addText(text, { x: x + 0.1, y: y + 0.08, w: w - 0.2, h: 0.16, fontFace: FONT, fontSize: 9.5, bold: true, color, margin: 0, align: "center", fit: "shrink" });
}

function cardText(slide, title, body, x, y, w, h, fill, line) {
  panel(slide, x, y, w, h, fill, line);
  slide.addShape(pptx.ShapeType.rect, { x, y, w: 0.09, h, fill: { color: line }, line: { color: line } });
  slide.addText(title, { x: x + 0.27, y: y + 0.22, w: w - 0.45, h: 0.28, fontFace: FONT, fontSize: 15, bold: true, color: C.ink, margin: 0, fit: "shrink" });
  const bodyHeight = h - 0.82;
  if (body && bodyHeight > 0.18) {
    slide.addText(body, { x: x + 0.27, y: y + 0.66, w: w - 0.45, h: bodyHeight, fontFace: FONT, fontSize: 11.5, color: C.ink2, breakLine: false, valign: "top", fit: "shrink", margin: 0.01 });
  }
}

function stat(slide, num, cap, x, y, w, accent = C.greenLine) {
  slide.addText(num, { x, y, w, h: 0.54, fontFace: "Segoe UI", fontSize: 29, bold: true, color: accent, margin: 0, fit: "shrink" });
  slide.addText(cap, { x, y: y + 0.55, w, h: 0.25, fontFace: FONT, fontSize: 10.5, color: C.muted, margin: 0, fit: "shrink" });
}

function addImage(slide, img, x, y, w, h) {
  if (process.env.NO_IMAGES === "1") {
    panel(slide, x, y, w, h, C.panel2, C.line);
    return;
  }
  if (!img) {
    panel(slide, x, y, w, h, C.panel2, C.line);
    slide.addText("素材未找到", { x, y: y + h / 2 - 0.15, w, h: 0.3, fontFace: FONT, fontSize: 12, color: C.muted, align: "center", margin: 0 });
    return;
  }
  slide.addImage({ path: img, x, y, w, h });
}

async function prepareAssets() {
  await fsp.mkdir(ASSETS, { recursive: true });
  await fsp.mkdir(OUT, { recursive: true });
  const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch {
    const executablePath = fs.existsSync(chrome) ? chrome : edge;
    browser = await chromium.launch({ headless: true, executablePath });
  }
  const assets = {
    maxCover: await cropImage(P.maxDepth, path.join(ASSETS, "max-depth-cover.png")),
    maxFit: await fitImage(P.maxDepth, path.join(ASSETS, "max-depth-fit.png")),
    finalFit: await fitImage(P.finalDepth, path.join(ASSETS, "final-depth-fit.png")),
    frontend: await fitImage(P.frontend, path.join(ASSETS, "frontend-fit.png")),
    rain4: await fitImage(P.rain4, path.join(ASSETS, "rain4-fit.png")),
    agentFlow: await screenshotHtml(browser, P.agentFlow, path.join(ASSETS, "agent-flow.png")),
    evidenceFlow: await screenshotHtml(browser, P.evidenceFlow, path.join(ASSETS, "evidence-flow.png")),
    diagnosisFlow: await screenshotHtml(browser, P.diagnosisFlow, path.join(ASSETS, "diagnosis-flow.png")),
    verificationFlow: await screenshotHtml(browser, P.verificationFlow, path.join(ASSETS, "verification-flow.png")),
    graphFlow: await screenshotHtml(browser, P.graphFlow, path.join(ASSETS, "graph-flow.png")),
    webIndex: await screenshotHtml(browser, P.webIndex, path.join(ASSETS, "web-index.png")),
    webObject: await screenshotHtml(browser, P.webObject, path.join(ASSETS, "web-object.png")),
    webArchitecture: await screenshotHtml(browser, P.webArchitecture, path.join(ASSETS, "web-architecture.png")),
    webDiagnosis: await screenshotHtml(browser, P.webDiagnosis, path.join(ASSETS, "web-diagnosis.png")),
    webRelation: await screenshotHtml(browser, P.webRelation, path.join(ASSETS, "web-relation.png")),
    webEval: await screenshotHtml(browser, P.webEval, path.join(ASSETS, "web-eval.png")),
    webPackage: await screenshotHtml(browser, P.webPackage, path.join(ASSETS, "web-package.png")),
    webWorkflow: await screenshotHtml(browser, P.webWorkflow, path.join(ASSETS, "web-workflow.png")),
  };
  await browser.close();
  return assets;
}

async function patchContentTypes(pptxPath) {
  const buf = await fsp.readFile(pptxPath);
  const zip = await JSZip.loadAsync(buf);
  const contentFile = zip.file("[Content_Types].xml");
  if (!contentFile) throw new Error("Missing [Content_Types].xml");
  let xml = await contentFile.async("string");
  xml = xml.replace(
    /<Override PartName="([^"]+)" ContentType="([^"]+)"\/>/g,
    (match, partName, contentType) => {
      const entryName = partName.replace(/^\//, "");
      return zip.file(entryName) ? match : "";
    }
  );
  zip.file("[Content_Types].xml", xml);
  const out = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
  await fsp.writeFile(pptxPath, out);
}

async function build() {
  const A = await prepareAssets();
  pptx = new pptxgen();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "SWMM-Agentic2";
  pptx.subject = "城市内涝 Agentic 诊断工作流";
  pptx.title = "SWMM-Agentic2 项目宣传版";
  pptx.company = "SWMM-Agentic2";
  pptx.lang = "zh-CN";
  pptx.theme = {
    headFontFace: FONT,
    bodyFontFace: FONT,
    lang: "zh-CN",
    themeColors: [
      { name: "dk1", color: C.ink },
      { name: "lt1", color: "FFFFFF" },
      { name: "dk2", color: C.ink2 },
      { name: "lt2", color: C.bg },
      { name: "accent1", color: C.blueLine },
      { name: "accent2", color: C.greenLine },
      { name: "accent3", color: C.amberLine },
      { name: "accent4", color: C.roseLine },
      { name: "accent5", color: C.purpleLine },
      { name: "accent6", color: C.muted },
      { name: "hlink", color: C.blueLine },
      { name: "folHlink", color: C.purpleLine },
    ],
  };
  pptx.defineLayout({ name: "CUSTOM_WIDE", width: SW, height: SH });
  pptx.layout = "CUSTOM_WIDE";
  const stopAfter = Number(process.env.STOP_AFTER || 0);
  if (stopAfter > 0) {
    const originalAddSlide = pptx.addSlide.bind(pptx);
    pptx.addSlide = (...args) => {
      if (pptx._slides.length >= stopAfter) {
        const err = new Error("STOP_AFTER");
        err.stopAfter = true;
        throw err;
      }
      return originalAddSlide(...args);
    };
  }

  let s;

  try {
  s = pptx.addSlide();
  s.background = { color: C.dark };
  addImage(s, A.maxCover, 0, 0, SW, SH);
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: SW, h: SH, fill: { color: C.dark2, transparency: 24 }, line: { color: C.dark2, transparency: 100 } });
  s.addText("SWMM-Agentic2", { x: 0.72, y: 1.45, w: 8.0, h: 0.78, fontFace: "Segoe UI", fontSize: 38, bold: true, color: "FFFFFF", margin: 0, fit: "shrink" });
  s.addText("城市内涝 Agentic 诊断工作流", { x: 0.74, y: 2.36, w: 7.1, h: 0.48, fontFace: FONT, fontSize: 20, color: "EEF4F7", margin: 0, fit: "shrink" });
  s.addShape(pptx.ShapeType.rect, { x: 0.75, y: 3.08, w: 1.65, h: 0.07, fill: { color: C.greenLine }, line: { color: C.greenLine } });
  s.addText("程序算得准，LLM 问得懂，流程管得住", { x: 7.12, y: 6.48, w: 5.42, h: 0.36, fontFace: FONT, fontSize: 16, bold: true, color: "FFFFFF", align: "right", margin: 0, fit: "shrink" });
  ["SWMM", "CA2D", "Agentic", "Evidence"].forEach((t, i) => label(s, t, 0.76 + i * 1.12, 0.56, 0.92, C.panel, C.line, C.ink));

  s = pptx.addSlide(); addBg(s); addTitle(s, "为什么需要 Agentic", "POSITIONING");
  const rows = [
    ["程序负责", "读取模型、运行模拟、提取指标", C.blue, C.blueLine],
    ["LLM 负责", "理解问题、解释证据、支持追问", C.purple, C.purpleLine],
    ["Agentic 负责", "串联阶段、控制流程、避免漂移", C.green, C.greenLine],
    ["最终产物", "证据链、诊断 claim、核查报告", C.amber, C.amberLine],
  ];
  s.addText("程序、LLM 与 Agentic 各司其职", { x: 0.68, y: 1.95, w: 4.15, h: 1.28, fontFace: FONT, fontSize: 26, bold: true, color: C.ink, margin: 0, breakLine: false, fit: "shrink" });
  s.addText("把可复现计算能力和任务理解能力组织在同一条受控流程里。", { x: 0.72, y: 3.52, w: 3.95, h: 0.92, fontFace: FONT, fontSize: 15.5, color: C.muted, margin: 0, fit: "shrink" });
  rows.forEach((r, i) => cardText(s, r[0], r[1], 5.25, 1.72 + i * 1.1, 6.95, 0.82, r[2], r[3]));
  footer(s, 2);

  s = pptx.addSlide(); addBg(s, C.warm);
  s.addText("模型结果，不再只是一堆文件", { x: 1.0, y: 1.58, w: 11.3, h: 0.82, fontFace: FONT, fontSize: 34, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  [
    ["更省", "减少直接喂海量数据", C.blue, C.blueLine],
    ["更准", "诊断读取结构化证据", C.green, C.greenLine],
    ["更可信", "每条结论都能核查", C.rose, C.roseLine],
  ].forEach((r, i) => cardText(s, r[0], r[1], 1.05 + i * 4.08, 3.12, 3.2, 1.55, r[2], r[3]));
  footer(s, 3);

  s = pptx.addSlide(); addBg(s); addTitle(s, "一次暴雨模拟的结果", "CASE");
  addImage(s, A.maxFit, 0.72, 1.68, 7.35, 4.45);
  stat(s, "0.7592 m", "最大水深", 8.65, 1.95, 3.0, C.blueLine);
  stat(s, "9890", "匹配溢流节点", 8.65, 3.25, 3.0, C.greenLine);
  stat(s, "598535", "CA2D 结果记录", 8.65, 4.55, 3.0, C.roseLine);
  footer(s, 4);

  s = pptx.addSlide(); addBg(s); addTitle(s, "从给水管网到排水内涝", "OBJECT");
  cardText(s, "EPANET", "节点、管段、水源、泵阀", 0.78, 1.72, 4.75, 2.9, C.blue, C.blueLine);
  cardText(s, "SWMM-CA2D", "降雨、管网、冒溢、地表积水", 7.02, 1.72, 4.75, 2.9, C.green, C.greenLine);
  s.addShape(pptx.ShapeType.line, { x: 5.72, y: 3.17, w: 1.1, h: 0, line: { color: C.muted, width: 2, beginArrowType: "none", endArrowType: "triangle" } });
  addImage(s, A.maxFit, 8.62, 3.08, 2.55, 1.18);
  s.addText("对象复杂性变了，Agent 任务也变了", { x: 1.12, y: 5.48, w: 10.9, h: 0.45, fontFace: FONT, fontSize: 20, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  footer(s, 5);

  s = pptx.addSlide(); addBg(s); addTitle(s, "从工具分工到流程分工", "ARCHITECTURE");
  ["情景准备", "耦合模拟", "证据构建", "灾害诊断", "证据核查", "解释报告"].forEach((t, i) => {
    const x = 0.64 + i * 2.05;
    panel(s, x, 2.65, 1.62, 1.22, i % 2 ? C.green : C.blue, i % 2 ? C.greenLine : C.blueLine);
    s.addText(t, { x: x + 0.12, y: 3.08, w: 1.38, h: 0.28, fontFace: FONT, fontSize: 13, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
    if (i < 5) s.addShape(pptx.ShapeType.line, { x: x + 1.69, y: 3.25, w: 0.28, h: 0, line: { color: C.muted, width: 1.2, endArrowType: "triangle" } });
  });
  s.addText("每个阶段都有明确输入、输出和状态。", { x: 2.0, y: 5.12, w: 9.3, h: 0.35, fontFace: FONT, fontSize: 16, color: C.muted, align: "center", margin: 0, fit: "shrink" });
  footer(s, 6);

  s = pptx.addSlide(); addBg(s); addTitle(s, "一条受控的 Agent 工作流", "WORKFLOW");
  addImage(s, A.agentFlow, 0.95, 1.58, 11.35, 4.85);
  s.addText("Scenario / Simulation / Evidence / Diagnosis / Verification / Report", { x: 2.22, y: 6.54, w: 8.9, h: 0.26, fontFace: "Segoe UI", fontSize: 11, color: C.muted, align: "center", margin: 0, fit: "shrink" });
  footer(s, 7);

  s = pptx.addSlide(); addBg(s, C.warm); addTitle(s, "不让 LLM 直接吞原始结果", "DIAGNOSIS");
  ["raw data", "evidence", "claim", "audit", "report"].forEach((t, i) => {
    const x = 0.88 + i * 2.45;
    label(s, t, x, 2.48, 1.65, i === 0 ? C.rose : i === 1 ? C.amber : i === 2 ? C.green : i === 3 ? C.purple : C.blue, i === 0 ? C.roseLine : i === 1 ? C.amberLine : i === 2 ? C.greenLine : i === 3 ? C.purpleLine : C.blueLine);
    if (i < 4) s.addShape(pptx.ShapeType.line, { x: x + 1.7, y: 2.67, w: 0.45, h: 0, line: { color: C.muted, width: 1.4, endArrowType: "triangle" } });
  });
  ["evidence_table.csv", "diagnosis_claims.json", "verification_report.json"].forEach((t, i) => label(s, t, 2.1 + i * 3.1, 4.56, 2.35, C.panel, C.line));
  footer(s, 8);

  s = pptx.addSlide(); addBg(s); addTitle(s, "输出先变成证据", "EVIDENCE");
  addImage(s, A.evidenceFlow, 0.72, 1.62, 7.15, 4.68);
  stat(s, "318411", "evidence records", 8.42, 2.05, 3.0, C.amberLine);
  ["object", "metric", "value", "source"].forEach((t, i) => label(s, t, 8.38 + (i % 2) * 1.72, 3.63 + Math.floor(i / 2) * 0.62, 1.38, i % 2 ? C.green : C.blue, i % 2 ? C.greenLine : C.blueLine));
  footer(s, 9);

  s = pptx.addSlide(); addBg(s); addTitle(s, "证据生成诊断", "CLAIMS");
  panel(s, 0.76, 1.74, 4.1, 4.38, C.panel, C.line);
  s.addText("Top 5 风险对象", { x: 1.02, y: 2.0, w: 2.6, h: 0.28, fontFace: FONT, fontSize: 15, bold: true, color: C.ink, margin: 0 });
  ["Cell 115176 / 0.698 m", "Cell 38021 / 0.638 m", "Cell 9684 / 0.523 m", "Cell 37765 / 0.476 m", "Cell 38278 / 0.458 m"].forEach((t, i) => {
    s.addText(String(i + 1).padStart(2, "0"), { x: 1.02, y: 2.55 + i * 0.52, w: 0.45, h: 0.2, fontFace: "Segoe UI", fontSize: 10, bold: true, color: C.roseLine, margin: 0 });
    s.addText(t, { x: 1.55, y: 2.49 + i * 0.52, w: 2.95, h: 0.25, fontFace: "Segoe UI", fontSize: 12.3, color: C.ink, margin: 0, fit: "shrink" });
  });
  addImage(s, A.diagnosisFlow, 5.28, 1.72, 7.05, 4.05);
  s.addText("claim = 对象 + 指标 + 数值 + evidence_id", { x: 5.65, y: 6.1, w: 6.2, h: 0.32, fontFace: FONT, fontSize: 14, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  footer(s, 10);

  s = pptx.addSlide(); addBg(s); addTitle(s, "结论必须查得到", "VERIFICATION");
  [["50 claims", "诊断结论", C.blueLine], ["50 supported", "证据支撑", C.greenLine], ["0.0", "unsupported rate", C.roseLine]].forEach((r, i) => stat(s, r[0], r[1], 1.1 + i * 3.78, 2.18, 3.3, r[2]));
  addImage(s, A.verificationFlow, 7.35, 4.18, 4.7, 1.78);
  s.addText("无证据输出被显式计量", { x: 1.15, y: 5.52, w: 5.0, h: 0.36, fontFace: FONT, fontSize: 17, bold: true, color: C.ink, margin: 0, fit: "shrink" });
  footer(s, 11);

  s = pptx.addSlide(); addBg(s); addTitle(s, "立体化证据网", "RELATION GRAPH");
  ["雨情", "地表", "节点", "管段", "泵站", "分区"].forEach((t, i) => label(s, t, 0.82 + i * 1.82, 1.72, 1.15, [C.amber, C.green, C.blue, C.purple, C.rose, C.panel2][i], [C.amberLine, C.greenLine, C.blueLine, C.purpleLine, C.roseLine, C.line][i]));
  addImage(s, A.graphFlow, 1.0, 2.5, 11.15, 2.85);
  [["对象层", C.blue, C.blueLine], ["关系层", C.green, C.greenLine], ["证据层", C.amber, C.amberLine]].forEach((r, i) => label(s, r[0], 3.0 + i * 2.22, 5.72, 1.45, r[1], r[2]));
  footer(s, 12);

  s = pptx.addSlide(); addBg(s, C.warm); addTitle(s, "以冒溢节点为锚点", "EVIDENCE PACKAGE");
  addImage(s, A.webPackage, 0.82, 1.62, 7.0, 4.72);
  ["rainfall_context", "node_evidence", "surface_context", "network_context", "relation_paths"].forEach((t, i) => label(s, t, 8.25, 1.92 + i * 0.68, 3.35, i % 2 ? C.green : C.amber, i % 2 ? C.greenLine : C.amberLine));
  s.addText("把局部诊断场景打包给 Agent", { x: 8.26, y: 5.65, w: 3.35, h: 0.35, fontFace: FONT, fontSize: 14.5, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  footer(s, 13);

  s = pptx.addSlide(); addBg(s); addTitle(s, "用指标证明工作流价值", "EVALUATION");
  ["任务成功率", "工具调用准确率", "代码尝试次数", "人工干预次数", "unsupported rate"].forEach((t, i) => {
    const x = 0.8 + i * 2.45;
    panel(s, x, 2.45, 1.85, 1.62, [C.blue, C.green, C.amber, C.purple, C.rose][i], [C.blueLine, C.greenLine, C.amberLine, C.purpleLine, C.roseLine][i]);
    s.addText(t, { x: x + 0.12, y: 3.05, w: 1.6, h: 0.28, fontFace: FONT, fontSize: 12.2, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  });
  s.addText("评价模块量化可靠性、效率和证据约束效果。", { x: 2.0, y: 5.15, w: 9.3, h: 0.35, fontFace: FONT, fontSize: 16, color: C.muted, align: "center", margin: 0, fit: "shrink" });
  footer(s, 14);

  s = pptx.addSlide();
  s.background = { color: C.dark };
  addImage(s, A.maxCover, 0, 0, SW, SH);
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: SW, h: SH, fill: { color: C.dark2, transparency: 18 }, line: { transparency: 100 } });
  s.addText("大规模案例闭环运行", { x: 0.72, y: 0.72, w: 8.5, h: 0.58, fontFace: FONT, fontSize: 28, bold: true, color: "FFFFFF", margin: 0, fit: "shrink" });
  [["10040", "节点"], ["9877", "管段"], ["318411", "条证据"], ["0.0", "unsupported rate"]].forEach((r, i) => {
    const x = 0.88 + i * 3.1;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 4.78, w: 2.45, h: 1.12, rectRadius: 0.07, fill: { color: C.dark2, transparency: 16 }, line: { color: "FFFFFF", transparency: 65 } });
    s.addText(r[0], { x: x + 0.18, y: 5.02, w: 2.08, h: 0.38, fontFace: "Segoe UI", fontSize: 25, bold: true, color: "FFFFFF", align: "center", margin: 0, fit: "shrink" });
    s.addText(r[1], { x: x + 0.18, y: 5.47, w: 2.08, h: 0.22, fontFace: FONT, fontSize: 10.5, color: "EEF4F7", align: "center", margin: 0, fit: "shrink" });
  });
  s.addText("15 / 20", { x: 11.82, y: 7.05, w: 0.8, h: 0.2, fontFace: FONT, fontSize: 8.5, color: "EEF4F7", align: "right", margin: 0 });

  s = pptx.addSlide(); addBg(s); addTitle(s, "从分析工具到交付材料", "APPLICATION");
  addImage(s, A.frontend, 0.72, 1.64, 7.15, 4.72);
  ["风险热点清单", "证据表", "核查报告", "诊断说明"].forEach((t, i) => label(s, t, 8.42, 2.0 + i * 0.72, 3.1, [C.rose, C.amber, C.green, C.blue][i], [C.roseLine, C.amberLine, C.greenLine, C.blueLine][i]));
  s.addText("让模型结果进入城市内涝决策链", { x: 8.42, y: 5.48, w: 3.15, h: 0.38, fontFace: FONT, fontSize: 14.5, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
  footer(s, 16);

  s = pptx.addSlide(); addBg(s, C.warm); addTitle(s, "已形成网页化宣传材料", "APPENDIX A1");
  addImage(s, A.webIndex, 0.75, 1.6, 6.45, 4.45);
  ["总览", "对象创新", "架构创新", "诊断机制", "关系证据网", "评价优化"].forEach((t, i) => label(s, t, 7.75 + (i % 2) * 2.0, 2.0 + Math.floor(i / 2) * 0.82, 1.55, i % 2 ? C.green : C.blue, i % 2 ? C.greenLine : C.blueLine));
  footer(s, 17);

  s = pptx.addSlide(); addBg(s); addTitle(s, "机制图可独立展示", "APPENDIX A2");
  addImage(s, A.webWorkflow, 0.75, 1.62, 6.45, 4.4);
  ["Agent 协同工作逻辑", "evidence_table 生成流程", "DiagnosisAgent 工作机制", "VerificationAgent 工作机制"].forEach((t, i) => cardText(s, t, "可作为现场讲解入口", 7.65, 1.84 + i * 0.94, 3.85, 0.72, i % 2 ? C.green : C.blue, i % 2 ? C.greenLine : C.blueLine));
  footer(s, 18);

  s = pptx.addSlide(); addBg(s); addTitle(s, "诊断规则可配置", "APPENDIX A3");
  [["moderate", "0.27 m", C.amberLine], ["high", "0.40 m", C.roseLine], ["critical", "0.60 m", C.purpleLine]].forEach((r, i) => stat(s, r[1], r[0], 1.45 + i * 3.55, 2.6, 2.5, r[2]));
  s.addText("阈值规则可随场景、城市标准和项目口径调整。", { x: 2.25, y: 5.05, w: 8.6, h: 0.36, fontFace: FONT, fontSize: 16, color: C.muted, align: "center", margin: 0, fit: "shrink" });
  footer(s, 19);

  s = pptx.addSlide(); addBg(s); addTitle(s, "可扩展到多降雨事件", "APPENDIX A4");
  addImage(s, A.rain4, 1.0, 1.62, 7.8, 4.75);
  ["rain1", "rain2", "rain3", "rain4"].forEach((t, i) => label(s, t, 9.35, 2.02 + i * 0.72, 1.7, i === 3 ? C.green : C.panel, i === 3 ? C.greenLine : C.line));
  footer(s, 20);
  } catch (err) {
    if (!err.stopAfter) throw err;
  }

  await pptx.writeFile({ fileName: FINAL });
  await patchContentTypes(FINAL);
  console.log(FINAL);
}

build().catch(err => {
  console.error(err);
  process.exit(1);
});
