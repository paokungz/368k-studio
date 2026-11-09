/** Shared project contract and image math. No network, device or firmware code. */
import {FACTORY_ASSETS} from './factory.mjs';
const sport = n => `/res_sport/SPORT_NIGHT_${n}.png`;
const common = n => `/res/Other/dark/sport/${n}.png`;
export const PARTS = {
  wallpaper: {label:'วอลเปเปอร์',size:[1024,600],at:[0,0],paths:[6,12,18,24].map(n=>sport('BG_'+n))},
  ring: {label:'พื้นวงรอบเครื่อง',size:[470,518],at:[289,38],paths:[common('bg0'),common('bg0_1')]},
  left: {label:'แผงข้อมูลซ้าย',size:[329,324],at:[0,149],paths:[sport('BG_LEFT_3')]},
  right: {label:'แผงมาตรวัดขวา',size:[329,324],at:[695,149],paths:[sport('BG_RIGHT_3')]},
  gear: {label:'พื้นช่องเกียร์',size:[140,103],at:[442,497],paths:[sport('GEAR_bg')]},
  glow: {label:'แสงพื้น',size:[462,83],at:[281,465],paths:[sport('BG_sport')]},
  speed: {label:'สีตัวเลขความเร็ว',size:[70,146],colorOnly:true,paths:[...Array.from({length:10},(_,i)=>sport('SPEED_'+i)),...['km_h','mph','deco'].map(n=>sport('SPEED_'+n))]},
  rpm_numbers: {label:'สีตัวเลขรอบเครื่อง',size:[34,28],colorOnly:true,paths:[...['BIG','SMALL'].flatMap(s=>Array.from({length:8},(_,n)=>sport(`RPM_NUM_${s}_${n}`))),sport('RPM_NUM_unit')]},
  rpm_accent: {label:'สีวง / ขีดรอบเครื่อง',size:[470,518],colorOnly:true,paths:['deco','deco_1','kedu','kedu_1','bar_normal','pointer'].map(common)},
};
export const BACKGROUND_PATHS = Object.values(PARTS).filter(p=>!p.colorOnly).flatMap(p=>p.paths);
export const SIZES = Object.fromEntries(Object.values(PARTS).flatMap(p=>p.paths.map(n=>[n,[...p.size]])));
SIZES[common('bg0_1')]=[468,518];
for(const [path,asset]of Object.entries(FACTORY_ASSETS))if(Object.hasOwn(SIZES,path))SIZES[path]=[...asset.size];
export const PART_INFO={
  wallpaper:{description:'ภาพพื้นหลังขนาดเต็มจอ ลายถนนอยู่ด้านล่าง ซ้อนหลังเกจและแผงข้อมูล ไม่รวมตัวเลข',region:'ทั้งจอ · 1024×600',tip:'วาดพื้นหลังได้ทั้งภาพ แต่อย่าวาดตัวเลขหรือไฟเตือนติดลงไป'},
  ring:{description:'พื้นวงกลมสีน้ำเงินกลางจอ รวมพื้นผิวและแสงของเกจ ไม่รวมขีดรอบและเลขรอบ',region:'วงกลมกลางจอ รอบตัวเลขความเร็ว',tip:'มี bg0 และ bg0_1 คนละขนาด รักษาขอบโปร่งและขนาด canvas'},
  left:{description:'พื้นแผงสีน้ำเงินด้านซ้าย รองข้อมูลลมยาง อุณหภูมิยางและแรงดันไฟ ไม่ใช่ตัวข้อมูล',region:'ซ้ายจอ · ใต้ข้อมูลยางและแบตเตอรี่',tip:'ลดลายบริเวณตัวหนังสือเพื่อให้อ่านค่าชัด'},
  right:{description:'พื้นแผงสีน้ำเงินด้านขวา รองมาตรวัดน้ำมันและอุณหภูมิ ไม่รวมแท่งระดับ',region:'ขวาจอ · หลังแถบน้ำมันและอุณหภูมิ',tip:'แท่งระดับ/ตัว F E H C เป็นอีกชั้นหนึ่ง'},
  gear:{description:'พื้นกรอบใต้เกจสำหรับอักษร S/ตำแหน่งเกียร์ ไม่ใช่ตัวอักษร S',region:'กึ่งกลางด้านล่างของวงเกจ',tip:'รักษาความโปร่งและขนาด 140×103'},
  glow:{description:'แถบแสงสีน้ำเงินรองส่วนล่างของวงเกจ เป็นภาพซ้อนโปร่ง ไม่ใช่เกจทั้งวง',region:'แนวนอนใต้ความเร็ว เหนือช่องเกียร์',tip:'ดูบนพื้นลายตารางเพื่อเห็นพื้นที่โปร่งของไฟล์'},
  speed:{description:'ภาพตัวเลขความเร็ว 0–9, หน่วย km/h/mph และเส้นตกแต่งใต้ตัวเลข',region:'เลขขนาดใหญ่กึ่งกลางวงเกจ',tip:'โหมดนี้ปรับสีเท่านั้น คงรูปทรงและ alpha ของ glyph เดิม'},
  rpm_numbers:{description:'ภาพตัวเลขรอบเครื่อง 0–7 ทั้ง BIG/SMALL และหน่วย rpm ตัวเลข 8–10 สีแดงเป็นชั้นคงเดิม',region:'ตัวเลขเล็กรอบวงเกจ',tip:'BIG กับ SMALL เป็นภาพคนละขนาด ไม่ใช่ไฟล์เดียวที่ย่อในเว็บ'},
  rpm_accent:{description:'เส้นกรอบ/ขีดสเกล/แถบรอบปกติและ pointer ที่ใช้ซ้อนบนพื้นวงเกจ',region:'เส้นและขีดรอบเกจกลางจอ',tip:'เปลี่ยนเฉพาะสีที่อนุญาต พิกเซลเขตรอบสูงสีแดงคงเดิม'},
};
export const LIMITS = {file:8*1024*1024,project:24*1024*1024,total:16*1024*1024,pixels:16_000_000,images:48};
export const PALETTE = ['#ffffff','#e5e7eb','#afafaf','#666666','#333333','#000000','#ff4d4d','#ff8a4c','#ffc247','#ffe66d','#d4fa42','#8bea4f','#34d399','#00cfb7','#38e8ed','#50baff','#3678ff','#6d62ff','#a27bff','#dc6aff','#ff66b8','#ff9fbe','#bc8460','#a8c7a1'];
export function require(ok,message){if(!ok)throw new Error(message);}
export function defaultConfig(){return {version:2,bootImage:'example-animation',parts:Object.fromEntries(Object.entries(PARTS).map(([k,p])=>[k,{enabled:false,mode:k==='wallpaper'?'image':'tint',color:p.colorOnly?'#e5f3ff':'#afafaf',opacity:100,fit:'cover',colors:0,x:.5,y:.5}]))};}
function plain(o){return o!==null&&typeof o==='object'&&!Array.isArray(o);}
export function normalizeConfig(input){
  require(plain(input)&&plain(input.parts),'โปรเจกต์ต้องมี parts');
  require(Object.keys(input.parts).every(k=>Object.hasOwn(PARTS,k)),'มี component ที่ยังไม่รองรับ');
  const next=defaultConfig();
  for(const [key,raw] of Object.entries(input.parts)){
    require(plain(raw),'ข้อมูล component ไม่ถูกต้อง');const p=next.parts[key];
    for(const name of ['enabled','mode','color','opacity','fit','colors','x','y','image','imageName'])if(Object.hasOwn(raw,name))p[name]=raw[name];
    require(typeof p.enabled==='boolean','enabled ต้องเป็น boolean');
    require(['tint','image'].includes(p.mode)&&['cover','contain','stretch'].includes(p.fit),'วิธีจัดภาพไม่ถูกต้อง');
    require(typeof p.color==='string'&&/^#[0-9a-f]{6}$/i.test(p.color),'สี HEX ต้องมี 6 หลัก');
    require(Number.isFinite(p.opacity)&&p.opacity>=0&&p.opacity<=100,'ความทึบต้องอยู่ระหว่าง 0–100');
    require([0,64,128,256].includes(p.colors),'จำนวนสี PNG ไม่ถูกต้อง');
    for(const axis of ['x','y'])require(Number.isFinite(p[axis])&&p[axis]>=0&&p[axis]<=1,'จุดครอปต้องอยู่ระหว่าง 0–1');
    if(p.image!==undefined)require(typeof p.image==='string'&&(/^[a-f0-9]{32}$/.test(p.image)||p.image==='example-wallpaper'),'รหัสภาพไม่ถูกต้อง');
    if(p.imageName!==undefined)require(typeof p.imageName==='string'&&p.imageName.length<=160,'ชื่อภาพยาวเกินกำหนด');
    if(PARTS[key].colorOnly)require(p.mode==='tint'&&p.opacity===100,'ตัวเลขและวงรอบเครื่องปรับได้เฉพาะสีและคงความทึบ');
  }
  // Keep boot outside Artist Mode; do not silently export an unrelated boot edit.
  return next;
}
export function canonicalTemplate(name){
  if(typeof name!=='string'||name.includes('..')||name.includes('\\'))return null;
  const clean='/'+name.replace(/^\/+|\/+$/g,'');
  return Object.keys(SIZES).find(p=>clean===p||clean.endsWith(p))||null;
}
export function validateEnvelope(value){
  require(plain(value),'ไฟล์โปรเจกต์ไม่ถูกต้อง');
  if(value.application!==undefined)require(value.application==='368K Studio','ไม่ใช่โปรเจกต์ 368K Studio');
  const config=normalizeConfig(value.config||value),images=value.images||{},templates=value.artist?.templateImages||{};
  require(plain(images)&&Object.keys(images).length<=LIMITS.images,'จำนวนภาพมากเกินไป');
  require(plain(templates)&&Object.keys(templates).length<=Object.keys(SIZES).length,'จำนวน template มากเกินไป');
  let bytes=0;
  for(const [id,b64] of Object.entries(images)){
    require(/^[a-f0-9]{32}$/.test(id)&&typeof b64==='string'&&/^[A-Za-z0-9+/]*={0,2}$/.test(b64)&&b64.length%4===0,'ข้อมูลภาพในโปรเจกต์ไม่ถูกต้อง');
    require(b64.length<=Math.ceil(LIMITS.file/3)*4,'ภาพในโปรเจกต์ใหญ่เกิน 8 MB');bytes+=b64.length*3/4;
  }
  for(const [path,b64] of Object.entries(templates)){
    require(Object.hasOwn(SIZES,path)&&typeof b64==='string'&&/^[A-Za-z0-9+/]*={0,2}$/.test(b64)&&b64.length%4===0,'ข้อมูล template ไม่ถูกต้อง');
    require(b64.length<=Math.ceil(LIMITS.file/3)*4,'template ใหญ่เกิน 8 MB');bytes+=b64.length*3/4;
  }
  require(bytes<=LIMITS.total,'ภาพรวมเกิน 16 MB ลดขนาดภาพก่อน');
  for(const p of Object.values(config.parts))if(p.enabled&&p.mode==='image')require(p.image&&Object.hasOwn(images,p.image),'โปรเจกต์ขาดภาพที่ component ใช้ กรุณาส่งออกจากต้นทางใหม่');
  return {config,images,templates};
}
export function redPixel(r,g,b){return r>g*1.4&&r>b*1.3&&r>0;}
export function transformPixels(pixels,options,colorOnly=false){
  const out=new Uint8ClampedArray(pixels.length),rgb=[1,3,5].map(i=>parseInt(options.color.slice(i,i+2),16));
  for(let n=0;n<pixels.length;n+=4){
    const [r,g,b,a]=pixels.slice(n,n+4);
    if(a===0||(colorOnly&&redPixel(r,g,b))){out.set([r,g,b,a],n);continue;}
    const value=colorOnly?Math.max(r,g,b):Math.floor(Math.floor((299*r+587*g+114*b)/1000)/4);
    for(let c=0;c<3;c++)out[n+c]=colorOnly?Math.floor((rgb[c]*value+127)/255):Math.min(255,rgb[c]+value);
    out[n+3]=colorOnly?a:Math.floor(a*options.opacity/100+.5);
  }
  return out;
}
export function fitRect(sw,sh,dw,dh,fit,x=.5,y=.5){
  if(fit==='stretch')return [0,0,sw,sh,0,0,dw,dh];
  const scale=fit==='cover'?Math.max(dw/sw,dh/sh):Math.min(dw/sw,dh/sh);
  if(fit==='cover'){const w=dw/scale,h=dh/scale;return [(sw-w)*x,(sh-h)*y,w,h,0,0,dw,dh];}
  const w=sw*scale,h=sh*scale;return [0,0,sw,sh,(dw-w)/2,(dh-h)/2,w,h];
}
export function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let n=0;n<8;n++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^0xffffffff)>>>0;}
/** Store-only ZIP; bounded input and no external dependencies or executable content. */
export function zipFiles(files){
  const encode=new TextEncoder(),entries=[],local=[],central=[];let offset=0;
  for(const [name,data] of files){
    require(typeof name==='string'&&!name.includes('..')&&!name.startsWith('/')&&!name.includes('\\'),'ชื่อไฟล์ ZIP ไม่ถูกต้อง');
    const n=encode.encode(name),b=data instanceof Uint8Array?data:encode.encode(data);
    const header=new Uint8Array(30+n.length),v=new DataView(header.buffer),crc=crc32(b);
    v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(12,0x21,true);
    v.setUint32(14,crc,true);v.setUint32(18,b.length,true);v.setUint32(22,b.length,true);v.setUint16(26,n.length,true);header.set(n,30);
    local.push(header,b);entries.push({n,b,crc,offset});offset+=header.length+b.length;
  }
  let centralSize=0;
  for(const e of entries){const h=new Uint8Array(46+e.n.length),v=new DataView(h.buffer);v.setUint32(0,0x02014b50,true);v.setUint16(4,20,true);v.setUint16(6,20,true);v.setUint16(8,0x800,true);v.setUint16(14,0x21,true);v.setUint32(16,e.crc,true);v.setUint32(20,e.b.length,true);v.setUint32(24,e.b.length,true);v.setUint16(28,e.n.length,true);v.setUint32(42,e.offset,true);h.set(e.n,46);central.push(h);centralSize+=h.length;}
  const end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,entries.length,true);v.setUint16(10,entries.length,true);v.setUint32(12,centralSize,true);v.setUint32(16,offset,true);
  return new Blob([...local,...central,end],{type:'application/zip'});
}
