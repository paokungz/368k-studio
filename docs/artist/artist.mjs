import {PARTS,SIZES,PART_INFO,BACKGROUND_PATHS,LIMITS,PALETTE,require,defaultConfig,normalizeConfig,validateEnvelope,canonicalTemplate,zipFiles} from './model.mjs';
import {canvas,renderer} from './canvas.mjs';
const $=id=>document.getElementById(id);
const view=renderer($('dashboard'));
let config=defaultConfig(),images=new Map(),templates=new Map(),selected='wallpaper',original=false,busy=false,dirty=false,invalidColor=false,frame=0,initialized=false;
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
function id(){const bytes=crypto.getRandomValues(new Uint8Array(16));return [...bytes].map(n=>n.toString(16).padStart(2,'0')).join('');}
function dataUrl(bytes,mime='image/png'){let binary='';for(let n=0;n<bytes.length;n+=32768)binary+=String.fromCharCode(...bytes.subarray(n,n+32768));return `data:${mime};base64,${btoa(binary)}`;}
function unbase64(value){const binary=atob(value);return Uint8Array.from(binary,c=>c.charCodeAt(0));}
function base64(bytes){return dataUrl(bytes).split(',')[1];}
function signature(bytes){
  const starts=a=>a.every((b,n)=>bytes[n]===b);
  if(starts([137,80,78,71,13,10,26,10]))return 'image/png';
  if(starts([255,216,255]))return 'image/jpeg';
  if(starts([71,73,70,56]))return 'image/gif';
  if(starts([66,77]))return 'image/bmp';
  if(starts([82,73,70,70])&&String.fromCharCode(...bytes.slice(8,12))==='WEBP')return 'image/webp';
  throw Error('รองรับเฉพาะไฟล์ภาพ PNG JPG WEBP GIF BMP ที่อ่านได้ ไม่รองรับ SVG');
}
async function decode(bytes,name='ภาพ'){
  require(bytes.length>0&&bytes.length<=LIMITS.file,'ไฟล์ภาพต้องไม่เกิน 8 MB');
  const mime=signature(bytes);
  if(mime==='image/png'&&bytes.length>=24){const v=new DataView(bytes.buffer,bytes.byteOffset);require(v.getUint32(16)*v.getUint32(20)<=LIMITS.pixels,'ภาพต้องไม่เกิน 16 ล้านพิกเซล');}
  const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
  try{
    const image=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('อ่านภาพไม่สำเร็จ'));im.src=url;});
    require(image.naturalWidth*image.naturalHeight<=LIMITS.pixels,'ภาพต้องไม่เกิน 16 ล้านพิกเซล');
    // Copy before revoking the URL; project owns decoded pixels, never a remote URL.
    const copy=canvas(image.naturalWidth,image.naturalHeight);copy.getContext('2d').drawImage(image,0,0);
    return {bytes,image:copy,mime,name:name.slice(0,160)};
  }finally{URL.revokeObjectURL(url);}
}
async function canvasBytes(image){const blob=await new Promise((resolve,reject)=>image.toBlob(b=>b?resolve(b):reject(Error('แปลง PNG ไม่สำเร็จ')),'image/png'));return new Uint8Array(await blob.arrayBuffer());}
function usedImages(next=config,map=images){const used=new Map();for(const p of Object.values(next.parts))if(p.image&&map.has(p.image))used.set(p.image,map.get(p.image));return used;}
function budget(map,refs){const sum=[...map.values(),...refs.values()].reduce((n,v)=>n+v.bytes.length,0);require(sum<=LIMITS.total,'ภาพรวมเกิน 16 MB ลดขนาดภาพหรือเริ่มโปรเจกต์ใหม่');}
function snapshot(){
  const checked=normalizeConfig(config),items=usedImages();budget(items,templates);
  const value={application:'368K Studio',version:1,config:checked,images:Object.fromEntries([...items].map(([key,v])=>[key,base64(v.bytes)])),artist:{version:1,previewBasis:templates.size?'factory-plus-local-templates':'factory-png-reference',templateImages:Object.fromEntries([...templates].map(([key,v])=>[key,base64(v.bytes)])),notes:'Factory PNG reference; text, values and positions are simulated. Confirm masks, colors and QRC capacity in Studio. Boot edits are outside Artist Mode.'}};
  const text=JSON.stringify(value,null,2);require(new TextEncoder().encode(text).length<=LIMITS.project,'ไฟล์โปรเจกต์ใหญ่เกิน 24 MB');validateEnvelope(value);return text;
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function state(){return {config,images,templates,selected,original,guides:$('guides').checked,speed:Number($('sample-speed').value),rpm:Number($('sample-rpm').value)};}
function render(){if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=0;try{view.render(state());}catch(e){notice(e.message,true);}});}
function partButtons(){
  const buttons=Object.entries(PARTS).map(([key,p],n)=>{
    const b=document.createElement('button');b.className='part'+(key===selected?' active':'')+(config.parts[key].enabled?' enabled':'');b.dataset.part=key;b.setAttribute('aria-pressed',String(key===selected));
    const thumb=document.createElement('img');thumb.src=factoryUrl(representativePath(key));thumb.alt='';thumb.className='part-thumb';b.append(thumb);
    for(const text of [p.label,'']){const node=document.createElement(text===''?'small':'span');node.textContent=text;b.append(node);}
    b.onclick=()=>selectPart(key);return b;
  });$('parts').replaceChildren(...buttons);
}
function buttons(){const locked=busy||!initialized;for(const b of document.querySelectorAll('button,input,select'))b.disabled=locked;$('image-mode').disabled=locked||PARTS[selected].colorOnly===true;$('opacity').disabled=locked||PARTS[selected].colorOnly===true;for(const name of ['save-project','export-layers'])$(name).disabled=locked||invalidColor;}
function factoryUrl(path){return new URL('./factory'+path,import.meta.url).href;}
function representativePath(key){return key==='wallpaper'?PARTS[key].paths.at(-1):key==='rpm_accent'?PARTS[key].paths.find(p=>p.endsWith('/kedu.png')):PARTS[key].paths[0];}
function selectPart(key){selected=key;invalidColor=false;$('guides').checked=true;partButtons();editor();render();}
function componentInfo(){
  const p=PARTS[selected],info=PART_INFO[selected];$('part-description').textContent=info.description;$('part-region').textContent=info.region;$('part-tip').textContent=info.tip;$('file-count').textContent=`PNG ในส่วนนี้ · ${p.paths.length} ไฟล์`;
  const files=p.paths.map(path=>{const row=document.createElement('a');row.className='file-row';row.href=factoryUrl(path);row.target='_blank';row.rel='noopener';const img=document.createElement('img');img.src=factoryUrl(path);img.alt=path.split('/').at(-1);const text=document.createElement('span');text.textContent=path;const dim=document.createElement('small');dim.textContent=SIZES[path].join(' × ')+' px';row.append(img,text,dim);return row;});$('part-files').replaceChildren(...files);
}
function componentGallery(){
  $('component-cards').replaceChildren(...Object.entries(PARTS).map(([key,p])=>{const b=document.createElement('button');b.className='component-card';b.dataset.component=key;const im=document.createElement('img');im.src=factoryUrl(representativePath(key));im.alt=p.label;const title=document.createElement('b');title.textContent=p.label;const detail=document.createElement('span');detail.textContent=PART_INFO[key].description;const filename=document.createElement('small');filename.textContent=representativePath(key).split('/').at(-1)+(p.paths.length>1?` + อีก ${p.paths.length-1} ไฟล์`:'');b.append(im,title,detail,filename);b.onclick=()=>{$('components').close();selectPart(key);};return b;}));
}
function editor(){
  const p=config.parts[selected],def=PARTS[selected];$('part-title').textContent=def.label;$('component-size').textContent=def.colorOnly?`ปรับเฉพาะสี · ${def.paths.length} PNG (ขนาดจริงในรายการ)`:(def.size.join(' × ')+' px'+(selected==='ring'?' · อีก variant 468 × 518':''));$('enabled').checked=p.enabled;
  $('image-mode').classList.toggle('active',p.mode==='image');$('color-mode').classList.toggle('active',p.mode==='tint');$('image-controls').hidden=p.mode!=='image'||def.colorOnly;$('color-controls').hidden=p.mode==='image';
  for(const [input,key,mul]of [['fit','fit',1],['crop-x','x',100],['crop-y','y',100],['opacity','opacity',1]])$(input).value=typeof p[key]==='number'?p[key]*mul:p[key];
  $('tint').value=p.color;if(!invalidColor){$('hex').value=p.color;$('hex').removeAttribute('aria-invalid');}for(const [i,k]of ['red','green','blue'].entries()){$(k).value=parseInt(p.color.slice(1+i*2,3+i*2),16);$(k+'-value').value=$(k).value;}
  $('opacity-value').value=p.opacity+'%';$('component-note').textContent=def.colorOnly?'ปรับเฉพาะสี คงรูปทรง / alpha และพิกเซลสีแดงเดิม':p.colors?'โปรเจกต์เดิมมีการลดจำนวนสี ภาพนี้แสดงสีเต็ม Studio จะตรวจและลดสีตอนสร้างไฟล์':'คงขนาด canvas และ mask เดิม ตำแหน่งใน preview เป็นการประมาณ';
  const image=images.get(p.image);$('source-thumb').hidden=false;$('source-thumb').src=image?dataUrl(image.bytes,image.mime):factoryUrl(representativePath(selected));$('image-name').textContent=image?.name||'PNG โรงงาน · '+representativePath(selected).split('/').at(-1);
  $('template-status').textContent=templates.size?`โหลด template ส่วนตัว ${templates.size} ชิ้น`:'ใช้ PNG โรงงานเป็นต้นแบบ';$('basis').textContent=templates.size?`${templates.size} template ส่วนตัว + PNG โรงงาน · ข้อมูลเป็นค่าจำลอง`:'Sport night โรงงาน · PNG ต้นฉบับ / ข้อมูลและตัวอักษรจำลอง';componentInfo();buttons();
}
function changed(){dirty=true;invalidColor=false;view.clear();partButtons();editor();render();}
async function task(message,work){if(busy)return;busy=true;buttons();notice(message);try{await work();}catch(e){notice(e.message,true);}finally{busy=false;editor();}}
async function upload(file){
  if(!file)return;await task('กำลังอ่านภาพใน browser…',async()=>{
    require(file.size<=LIMITS.file,'ภาพใหญ่เกิน 8 MB');const item=await decode(new Uint8Array(await file.arrayBuffer()),file.name),key=id();
    const next=normalizeConfig(config);Object.assign(next.parts[selected],{image:key,imageName:item.name,enabled:true,mode:'image'});
    const nextImages=usedImages(next,new Map([...images,[key,item]]));budget(nextImages,templates);config=next;images=nextImages;changed();notice('ใส่ภาพแล้ว ไฟล์ยังอยู่ใน browser กดบันทึกโปรเจกต์เพื่อเก็บงาน');
  });$('image-file').value='';
}
async function importProject(file){
  if(!file)return;await task('กำลังเปิดโปรเจกต์…',async()=>{
    require(file.size<=LIMITS.project,'โปรเจกต์ใหญ่เกิน 24 MB');const parsed=validateEnvelope(JSON.parse(await file.text())),nextImages=new Map(),nextTemplates=new Map();
    for(const [key,value]of Object.entries(parsed.images))nextImages.set(key,await decode(unbase64(value),'ภาพจากโปรเจกต์'));
    for(const [path,value]of Object.entries(parsed.templates)){const item=await decode(unbase64(value),'template');require(item.image.width===SIZES[path][0]&&item.image.height===SIZES[path][1],'ขนาด template ในโปรเจกต์ไม่ตรง');nextTemplates.set(path,item);}
    budget(nextImages,nextTemplates);config=parsed.config;images=nextImages;templates=nextTemplates;selected='wallpaper';original=false;$('compare').setAttribute('aria-pressed','false');$('compare').textContent='เทียบกับโรงงาน';changed();dirty=false;notice('เปิดโปรเจกต์แล้ว ส่วนที่ไม่ได้แก้หรือแนบ template ใช้ PNG โรงงานเป็นฐาน');
  });$('project-file').value='';
}
async function importTemplates(files){
  await task('กำลังอ่านโฟลเดอร์ template…',async()=>{
    const next=new Map(templates);let count=0;
    for(const file of files){
      const path=canonicalTemplate(file.webkitRelativePath||file.name);if(!path)continue;
      require(file.size<=LIMITS.file,'template ใหญ่เกิน 8 MB');const item=await decode(new Uint8Array(await file.arrayBuffer()),file.name);
      require(item.mime==='image/png','template ต้องเป็น PNG');require(item.image.width===SIZES[path][0]&&item.image.height===SIZES[path][1],`ขนาด ${file.name} ต้องเป็น ${SIZES[path].join('×')} px`);next.set(path,item);count++;
    }
    require(count>0,'ไม่พบ template ที่รองรับ เลือกโฟลเดอร์ templates ที่เก็บชื่อ res_sport และ res/Other/dark/sport ตามเดิม');budget(usedImages(),next);templates=next;changed();notice(`อ่าน template ${count} ชิ้นแล้ว ส่วนอื่นใช้ PNG โรงงาน ข้อมูลมาตรวัดเป็นค่าจำลอง`);
  });$('template-files').value='';
}
async function exportLayers(sample=false){await task(sample?'กำลังเตรียม template ตัวอย่าง…':'กำลังแปลงชิ้นภาพ PNG…',async()=>{
  const files=[];view.clear();view.render(state());
  for(const path of BACKGROUND_PATHS)files.push([(sample?'templates':'png')+path,await canvasBytes(sample?view.stock.get(path):view.get(path))]);
  if(!sample){const was=original;original=false;view.render({...state(),guides:false});files.push(['preview.png',await canvasBytes($('dashboard'))]);original=was;view.render(state());files.push(['project.json',snapshot()]);files.push(['palette.json',JSON.stringify(Object.fromEntries(Object.entries(config.parts).map(([key,p])=>[key,{enabled:p.enabled,color:p.color,opacity:p.opacity,mode:p.mode,colors:p.colors}])),null,2)]);}
  files.push(['README.txt',sample?'Factory visual PNG reference, re-encoded from browser canvases. No firmware or font included. Artwork remains with its respective rights holders. Keep exact canvas size and alpha boundaries.':'Artist design preview only. Uses factory PNGs plus any user-loaded templates. Text/fonts/positions are simulated. These files are NOT an installable Launcher. Open project.json in Studio using your verified private firmware, build and verify there. Color-only settings are in project.json/palette.json. Full-color PNG; quantization and QRC capacity are checked by Studio.']);
  download(zipFiles(files),sample?'368K-Factory-Templates.zip':'368K-Artist-Design.zip');notice(sample?'ส่งออก template ภาพโรงงานแล้ว ไม่มี firmware หรือฟอนต์แนบ':'ส่งออก PNG / preview / project / palette แล้ว ใช้ project.json เปิดต่อใน Studio');
});}
async function fresh(){
  config=defaultConfig();images=new Map();templates=new Map();selected='wallpaper';original=false;$('guides').checked=false;$('sample-speed').value=0;$('speed-value').value='0 km/h';$('sample-rpm').value=0;$('rpm-value').value='0 rpm';$('compare').setAttribute('aria-pressed','false');$('compare').textContent='เทียบกับโรงงาน';view.clear();partButtons();editor();render();dirty=false;
}
function setColor(color){if(!/^#[0-9a-f]{6}$/i.test(color)){invalidColor=true;$('hex').setAttribute('aria-invalid','true');buttons();notice('ใส่สี HEX 6 หลัก เช่น #38bdf8',true);return;}Object.assign(config.parts[selected],{color:color.toLowerCase(),enabled:true,mode:'tint'});changed();}
function bind(){
  $('enabled').onchange=()=>{const p=config.parts[selected];if($('enabled').checked&&p.mode==='image'&&!images.has(p.image)){$('enabled').checked=false;$('image-file').click();return;}p.enabled=$('enabled').checked;changed();};
  $('image-mode').onclick=()=>{const p=config.parts[selected];if(!images.has(p.image)){$('image-file').click();return;}p.mode='image';p.enabled=true;changed();};
  $('color-mode').onclick=()=>{Object.assign(config.parts[selected],{mode:'tint',enabled:true});changed();};
  for(const [input,key,mul]of [['fit','fit',1],['crop-x','x',.01],['crop-y','y',.01],['opacity','opacity',1]])$(input).oninput=()=>{const p=config.parts[selected];if(p.mode==='image'&&!images.has(p.image)){notice('เลือกภาพที่จะใช้แทนก่อนปรับค่าภาพ หรือเลือกปรับสีเพื่อเปลี่ยนพื้นเดิม',true);editor();return;}p[key]=input==='fit'?$(input).value:Number($(input).value)*mul;p.enabled=true;changed();};
  $('tint').oninput=()=>setColor($('tint').value);$('hex').oninput=()=>setColor($('hex').value.startsWith('#')?$('hex').value:'#'+$('hex').value);
  for(const k of ['red','green','blue'])$(k).oninput=()=>setColor('#'+['red','green','blue'].map(n=>Number($(n).value).toString(16).padStart(2,'0')).join(''));
  for(const color of PALETTE){const b=document.createElement('button');b.style.backgroundColor=color;b.setAttribute('aria-label',color);b.onclick=()=>setColor(color);$('swatches').append(b);}
  $('image-file').onchange=e=>upload(e.target.files[0]);$('dropzone').ondragover=e=>{e.preventDefault();$('dropzone').classList.add('drag');};$('dropzone').ondragleave=()=>$('dropzone').classList.remove('drag');$('dropzone').ondrop=e=>{e.preventDefault();$('dropzone').classList.remove('drag');if(!busy&&!PARTS[selected].colorOnly)upload(e.dataTransfer.files[0]);};
  $('reset-part').onclick=()=>{config.parts[selected].enabled=false;for(const path of PARTS[selected].paths)templates.delete(path);changed();};$('reset').onclick=()=>{if(!dirty||confirm('คืนทั้งจอเป็นโรงงาน? บันทึกโปรเจกต์เดิมก่อนหากต้องการเก็บ'))task('กำลังคืนแบบโรงงาน…',async()=>{await fresh();notice('แบบโรงงาน ทุก component ยังไม่ได้เปิดแก้ไข');});};
  $('save-project').onclick=()=>task('กำลังจัดไฟล์โปรเจกต์…',async()=>{download(new Blob([snapshot()],{type:'application/json'}),'368K-Artist-project.json');dirty=false;notice('บันทึกโปรเจกต์พร้อมภาพและ template แล้ว เปิดใน Studio เพื่อแปลงและตรวจไฟล์จริง');});
  $('open-project').onclick=()=>$('project-file').click();$('project-file').onchange=e=>importProject(e.target.files[0]);$('load-templates').onclick=()=>$('template-files').click();$('template-files').onchange=e=>importTemplates([...e.target.files]);
  $('sample-templates').onclick=()=>exportLayers(true);$('export-layers').onclick=()=>exportLayers(false);
  $('guides').onchange=render;for(const [input,value,suffix]of [['sample-speed','speed-value',' km/h'],['sample-rpm','rpm-value',' rpm']])$(input).oninput=()=>{$(value).value=$(input).value+suffix;render();};
  $('compare').onclick=()=>{original=!original;$('compare').setAttribute('aria-pressed',String(original));$('compare').textContent=original?'กลับไปดูแบบใหม่':'เทียบกับโรงงาน';render();};
  $('export-preview').onclick=()=>task('กำลังบันทึก preview…',async()=>{const was=original;original=false;view.render({...state(),guides:false});const png=await canvasBytes($('dashboard'));original=was;render();download(new Blob([png],{type:'image/png'}),'368K-Artist-preview.png');notice('บันทึก preview แล้ว เป็นภาพประกอบสำหรับตรวจแบบ ไม่ใช่ screenshot จากรถ');});
  $('help-open').onclick=()=>$('help').showModal();$('help-close').onclick=()=>$('help').close();
  $('components-open').onclick=()=>$('components').showModal();$('components-close').onclick=()=>$('components').close();
  $('dashboard').onclick=e=>{if(busy||!initialized)return;const r=$('dashboard').getBoundingClientRect(),x=(e.clientX-r.left)*1024/r.width,y=(e.clientY-r.top)*600/r.height;selectPart(y>495&&x>440&&x<590?'gear':x>450&&x<660&&y>240&&y<410?'speed':x<329&&y>149&&y<473?'left':x>695&&y>149&&y<473?'right':x>289&&x<759&&y>38&&y<556?'ring':'wallpaper');};
  window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
}
bind();busy=true;buttons();notice('กำลังโหลด PNG โรงงาน…');
view.ready.then(async()=>{initialized=true;componentGallery();await fresh();notice('เริ่มจากแบบโรงงาน เลือกส่วนทางซ้ายหรือกด “รูปไหนคือส่วนไหน” เพื่อเริ่มออกแบบ');}).catch(e=>notice(e.message+' · โหลดหน้าเว็บใหม่เพื่อลองอีกครั้ง',true)).finally(()=>{busy=false;editor();});
