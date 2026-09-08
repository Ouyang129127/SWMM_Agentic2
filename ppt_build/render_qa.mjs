import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { FileBlob, PresentationFile } from 'file:///C:/Users/ouyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const require = createRequire(import.meta.url);
const sharp = require('C:/Users/ouyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const ppt='E:/SWMM_Agentic/SWMM-Agentic2/ppt_output/SWMM-Agentic2_项目宣传版.pptx';
const out='E:/SWMM_Agentic/SWMM-Agentic2/ppt_build/qa_render';
await fs.mkdir(out,{recursive:true});
const p=await PresentationFile.importPptx(await FileBlob.load(ppt));
console.log('slides', p.slides.length);
const thumbs=[];
for (let i=0;i<p.slides.length;i++) {
  const png=await p.export({slide:p.slides[i], format:'png', scale:1});
  const buf=Buffer.from(await png.arrayBuffer());
  const file=path.join(out, `slide-${String(i+1).padStart(2,'0')}.png`);
  await fs.writeFile(file, buf);
  thumbs.push(buf);
}
const meta=await sharp(thumbs[0]).metadata();
const w=meta.width, h=meta.height;
const tw=320, th=Math.round(h*tw/w);
const composites=[];
for (let i=0;i<thumbs.length;i++) {
  const resized=await sharp(thumbs[i]).resize(tw,th).png().toBuffer();
  composites.push({input:resized,left:(i%4)*tw,top:Math.floor(i/4)*th});
}
await sharp({create:{width:tw*4,height:th*5,channels:3,background:'#f4f6f8'}}).composite(composites).png().toFile(path.join(out,'contact-sheet.png'));
console.log(path.join(out,'contact-sheet.png'));
