/* Real-browser workflow test. Uses a local static server; no vehicle/API calls. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');const path=require('node:path');const os=require('node:os');const http=require('node:http');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../docs/artist');
async function main(){
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'368k-artist-'));
  const server=http.createServer(async(req,res)=>{
    const p=new URL(req.url,'http://localhost').pathname.replace(/^\/368k-studio\//,'');
    const name=!p||p==='/'?'index.html':p;
    if(!['index.html','artist.mjs','model.mjs','canvas.mjs','style.css'].includes(name)){res.writeHead(404);return res.end();}
    res.setHeader('Content-Type',name.endsWith('.mjs')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(await fs.readFile(path.join(root,name)));
  });await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const url=process.env.ARTIST_TEST_URL||`http://127.0.0.1:${server.address().port}/368k-studio/`;
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
  let page;
  try{
    page=await browser.newPage({viewport:{width:1600,height:1080},deviceScaleFactor:1});const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
    page.on('dialog',d=>d.accept());await page.goto(url);await page.waitForFunction(()=>document.querySelectorAll('[data-part]').length===9);await page.waitForTimeout(150);
    const output=path.resolve(__dirname,'../test-results');await fs.mkdir(output,{recursive:true});await page.screenshot({path:path.join(output,'artist-default.png'),fullPage:true});
    assert.equal(await page.evaluate(async()=>{
      const {canvas,transformed}=await import('./canvas.mjs');const {PARTS}=await import('./model.mjs');
      const source=canvas(4,4);source.getContext('2d').fillRect(0,0,4,4);const transparent=canvas(4,4);
      const result=transformed(source,{mode:'image',fit:'stretch',opacity:100,x:.5,y:.5},PARTS.wallpaper,transparent);
      return result.getContext('2d').getImageData(0,0,1,1).data[3];
    }),0);
    async function ready(){await page.waitForFunction(()=>!document.querySelector('#save-project').disabled);}
    async function download(button){const event=page.waitForEvent('download');await page.locator(button).click();const d=await event;const file=await d.path();await ready();return fs.readFile(file);}
    const initial=JSON.parse(await download('#save-project'));assert.equal(initial.application,'368K Studio');assert.equal(Object.keys(initial.config.parts).length,9);assert.equal(Object.keys(initial.images).length,1);
    const png=Buffer.from(await page.evaluate(()=>{const c=document.createElement('canvas');c.width=600;c.height=300;const x=c.getContext('2d');x.fillStyle='#ff6a8e';x.fillRect(0,0,300,300);x.fillStyle='#536af2';x.fillRect(300,0,300,300);return c.toDataURL().split(',')[1];}),'base64');
    await page.locator('#image-file').setInputFiles({name:'artist-wallpaper.png',mimeType:'image/png',buffer:png});await ready();await page.waitForFunction(()=>document.querySelector('#image-name').textContent==='artist-wallpaper.png');
    await page.locator('[data-part="speed"]').click();assert.equal(await page.locator('#image-mode').isDisabled(),true);assert.equal(await page.locator('#opacity').isDisabled(),true);
    await page.locator('#hex').fill('#38bdf8');await page.locator('#hex').dispatchEvent('input');
    const designed=await download('#save-project');const parsed=JSON.parse(designed);assert.equal(parsed.config.parts.speed.color,'#38bdf8');assert.equal(parsed.config.parts.speed.enabled,true);assert.equal(parsed.config.parts.wallpaper.imageName,'artist-wallpaper.png');
    await fs.writeFile(path.join(temp,'project.json'),designed);
    await page.locator('#project-file').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{not json')});await ready();assert.equal(await page.locator('#notice').evaluate(n=>n.classList.contains('error')),true);
    assert.deepEqual(JSON.parse(await download('#save-project')),parsed);
    await page.locator('#project-file').setInputFiles({name:'project.json',mimeType:'application/json',buffer:designed});await ready();assert.deepEqual(JSON.parse(await download('#save-project')),parsed);
    const templateDir=path.join(temp,'templates');await fs.mkdir(path.join(templateDir,'res_sport'),{recursive:true});
    const panel=Buffer.from(await page.evaluate(()=>{const c=document.createElement('canvas');c.width=329;c.height=324;const x=c.getContext('2d');x.fillStyle='#7799bb';x.fillRect(20,20,150,180);return c.toDataURL().split(',')[1];}),'base64');
    await fs.writeFile(path.join(templateDir,'res_sport/SPORT_NIGHT_BG_LEFT_3.png'),panel);await page.locator('#template-files').setInputFiles(templateDir);await ready();assert.match(await page.locator('#template-status').textContent(),/1 ชิ้น/);
    await page.locator('[data-part="left"]').click();await page.locator('#color-mode').click();await page.locator('#hex').fill('#afafaf');await page.locator('#hex').dispatchEvent('input');await page.locator('#opacity').fill('45');await page.locator('#opacity').dispatchEvent('input');
    const withTemplates=await download('#save-project');assert.equal(Object.keys(JSON.parse(withTemplates).artist.templateImages).length,1);await fs.writeFile(path.join(temp,'project-with-templates.json'),withTemplates);
    await page.locator('#project-file').setInputFiles({name:'project.json',mimeType:'application/json',buffer:withTemplates});await ready();assert.deepEqual(JSON.parse(await download('#save-project')),JSON.parse(withTemplates));
    const designZip=await download('#export-layers');await fs.writeFile(path.join(temp,'design.zip'),designZip);assert.equal(designZip.readUInt32LE(0),0x04034b50);
    const sampleZip=await download('#sample-templates');await fs.writeFile(path.join(temp,'templates.zip'),sampleZip);
    const preview=await download('#export-preview');assert.equal(preview.subarray(1,4).toString(),'PNG');
    await page.locator('[data-part="speed"]').click();await page.locator('#hex').fill('nothex');await page.locator('#hex').dispatchEvent('input');assert.equal(await page.locator('#export-layers').isDisabled(),true);await page.locator('#hex').fill('#38bdf8');await page.locator('#hex').dispatchEvent('input');
    await page.locator('[data-part="wallpaper"]').click();await page.locator('#image-file').setInputFiles({name:'bad.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg onload="window.bad=1"></svg>')});await ready();assert.equal(await page.evaluate(()=>window.bad),undefined);assert.match(await page.locator('#notice').textContent(),/ไม่รองรับ SVG/);
    await page.locator('#sample-speed').fill('120');await page.locator('#sample-speed').dispatchEvent('input');await page.locator('#sample-rpm').fill('6500');await page.locator('#sample-rpm').dispatchEvent('input');
    await page.screenshot({path:path.join(output,'artist-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(output,'artist-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);assert.equal(requests.filter(u=>/^https?:/.test(u)).some(u=>u.includes('/api/')||!u.startsWith(url)),false);
    console.log(JSON.stringify({status:'PASS',checks:['9 components','image upload','color-only guards','project roundtrip','malformed project preserves current work','private template folder and project roundtrip','PNG/ZIP exports','invalid HEX blocks export','SVG rejected','responsive layout','no API/external requests'],artifacts:temp}));
  }finally{if(page)page.removeAllListeners('dialog');await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
