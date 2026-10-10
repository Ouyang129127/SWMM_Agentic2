// Offline rendering and export of the editable HTML/SVG architecture figure.
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const { chromium } = require('C:/Users/ouyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const stem = path.join(__dirname, 'agent_collaboration_logic_morandi_vertical_v2_20261008');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1600},deviceScaleFactor:2});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(stem+'.html').href);
    await page.evaluate(() => document.fonts.ready);
    const svg = page.locator('#architecture');
    const exported = await page.evaluate(() => {
      const el = document.querySelector('#architecture').cloneNode(true);
      const style = document.createElementNS('http://www.w3.org/2000/svg','style');
      style.textContent = document.querySelector('style').textContent;
      el.insertBefore(style,el.firstChild);
      el.setAttribute('width','1280'); el.setAttribute('height','1350');
      return '<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(el);
    });
    fs.writeFileSync(stem+'.svg',exported,'utf8');
    await svg.screenshot({path:stem+'.png'});
    const bounds = await page.evaluate(() => {
      const texts=[...document.querySelectorAll('#architecture text')];
      return texts.filter(t => {const b=t.getBBox();return b.x<0||b.y<0||b.x+b.width>1280||b.y+b.height>1350;}).map(t=>t.textContent);
    });
    console.log(JSON.stringify({png:stem+'.png',svg:stem+'.svg',pageErrors:errors,outsideViewBox:bounds},null,2));
    if(errors.length||bounds.length)process.exitCode=1;
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
