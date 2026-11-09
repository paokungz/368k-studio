import {PARTS,transformPixels,fitRect} from './model.mjs';
import {FACTORY_ASSETS} from './factory.mjs';
export function canvas(w,h){const c=document.createElement('canvas');c.width=w;c.height=h;return c;}
function label(ctx,value,x,y,size=24,color='#ecf6fc',align='left'){ctx.fillStyle=color;ctx.font=`600 ${size}px system-ui, sans-serif`;ctx.textAlign=align;ctx.fillText(value,x,y);}
function rounded(ctx,x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke();}}
export function transformed(source,option,part,image){
  const c=canvas(source.width||source.naturalWidth,source.height||source.naturalHeight),x=c.getContext('2d',{willReadFrequently:true});x.drawImage(source,0,0);
  const original=x.getImageData(0,0,c.width,c.height);
  if(option.mode!=='image'||part.colorOnly){original.data.set(transformPixels(original.data,option,part.colorOnly));x.putImageData(original,0,0);return c;}
  x.clearRect(0,0,c.width,c.height);
  const rect=fitRect(image.naturalWidth||image.width,image.naturalHeight||image.height,c.width,c.height,option.fit,option.x,option.y);
  if(option.fit==='contain'){x.fillStyle='#000';x.fillRect(0,0,c.width,c.height);x.clearRect(rect[4],rect[5],rect[6],rect[7]);}
  x.drawImage(image,...rect);
  const next=x.getImageData(0,0,c.width,c.height);
  for(let n=0;n<next.data.length;n+=4){
    if(part!==PARTS.wallpaper){
      if(original.data[n+3]===0){next.data.set(original.data.slice(n,n+4),n);continue;}
      next.data[n+3]=Math.floor(next.data[n+3]*original.data[n+3]/255);
    }
    next.data[n+3]=Math.floor(next.data[n+3]*option.opacity/100+.5);
  }
  x.putImageData(next,0,0);return c;
}
export function renderer(target){
  const stock=new Map(),cache=new Map();
  const ready=Promise.all(Object.entries(FACTORY_ASSETS).map(async([path,info])=>{
    const image=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('โหลด PNG โรงงานไม่สำเร็จ: '+path));im.src=new URL('./factory'+path,import.meta.url).href;});
    if(image.naturalWidth!==info.size[0]||image.naturalHeight!==info.size[1])throw Error('ขนาด PNG โรงงานไม่ตรง: '+path);
    const copy=canvas(...info.size);copy.getContext('2d').drawImage(image,0,0);stock.set(path,copy);
  }));
  let state;
  function get(path,original=false){
    const source=(!original&&state.templates.get(path)?.image)||stock.get(path),key=Object.keys(PARTS).find(k=>PARTS[k].paths.includes(path));
    if(!source)throw Error('ไม่พบชิ้นภาพ '+path);
    const option=state.config.parts[key];if(original||!option?.enabled)return source;
    if(!cache.has(path))cache.set(path,transformed(source,option,PARTS[key],state.images.get(option.image)?.image));
    return cache.get(path);
  }
  function render(next){
    state=next;const x=target.getContext('2d');x.clearRect(0,0,1024,600);x.fillStyle='#08121a';x.fillRect(0,0,1024,600);
    const sport=n=>'/res_sport/SPORT_NIGHT_'+n+'.png',common=n=>'/res/Other/dark/sport/'+n+'.png';
    const draw=(path,a,b)=>x.drawImage(get(path,next.original),a,b);
    for(const key of ['wallpaper','left','right','glow','gear','ring']){const p=PARTS[key];x.drawImage(get(key==='wallpaper'?p.paths.at(-1):p.paths[0],next.original),...p.at);}
    if(next.rpm>0){x.save();x.beginPath();x.moveTo(524,282);x.arc(524,282,290,Math.PI*.55,Math.PI*.55+next.rpm/7000*Math.PI);x.closePath();x.clip();draw(common('bar_normal'),289,38);x.restore();}
    for(const name of ['deco','bg1','bar_warn','kedu','pointer'])draw(common(name),289,38);
    const coords=[[508,449],[393,427],[350,368],[351,300],[371,231],[414,173],[465,143],[524,143],[583,173],[633,231],[650,306]];
    coords.forEach(([a,b],n)=>draw(sport('RPM_NUM_BIG_'+(n>=8?'10000_':'')+n),a,b));
    const digits=String(next.speed);let px=524-digits.length*35;for(const d of digits){draw(sport('SPEED_'+d),px,245);px+=70;}
    draw(sport('SPEED_deco'),441,374);draw(sport('SPEED_km_h'),492,397);draw(sport('RPM_NUM_unit'),649,343);
    for(const [name,a,b]of [['WAF_OIL_bg',836,188],['WAF_OIL_normal_bar',814,191],['WAF_OIL_F',836,167],['WAF_OIL_E',816,431],['WAF_OIL_icon',863,382],['WAF_WATER_bg',949,188]])draw(sport(name),a,b);
    x.save();x.beginPath();x.rect(900,367,90,55);x.clip();draw(sport('WAF_WATER_normal_bar'),930,191);x.restore();
    for(const [name,a,b]of [['WAF_WATER_red_bar_7',930,191],['WAF_WATER_H',949,167],['WAF_WATER_C',927,431],['WAF_WATER_icon',979,384],['TIRE_Wheel',80,171],['TIRE_F_Wheel_green',205,220],['TIRE_BODY',198,252],['TIRE_R_Wheel_green',205,332]])draw(sport(name),a,b);
    for(const [value,a,b,size]of [['psi',124,195,23],['°C',124,221,23],['F',85,251,22],['33.1',119,256,28],['36',119,291,28],['R',85,338,22],['39.5',119,339,28],['47',119,373,28],['13.3',109,443,30],['v',182,443,17],['16:54',725,65,31]])label(x,value,a,b,size);
    label(x,'S',510,557,49,'#fff','center');label(x,'ODO 0000 km',511,588,28,'#fff','center');
    factoryWarnings(x);
    if(next.guides){const p=PARTS[next.selected],at=p.at||({speed:[450,240],rpm_numbers:[325,100],rpm_accent:[289,38]}[next.selected]),size=p.at?p.size:({speed:[210,162],rpm_numbers:[390,410],rpm_accent:[470,518]}[next.selected]);x.strokeStyle='#bcdfba';x.lineWidth=2;x.setLineDash([8,6]);x.strokeRect(...at,...size);x.setLineDash([]);}
  }
  return {render,get,ready,clear:()=>cache.clear(),stock};
}
function factoryWarnings(x){
  const stroke=(points,color,width=3)=>{x.strokeStyle=color;x.lineWidth=width;x.beginPath();points.forEach(([a,b],i)=>i?x.lineTo(a,b):x.moveTo(a,b));x.stroke();};
  x.save();x.strokeStyle='#99f500';x.lineWidth=5;x.beginPath();x.arc(40,546,8,0,Math.PI*2);x.stroke();stroke([[33,546],[14,546],[14,552],[23,552],[23,547]],'#99f500',5);
  x.strokeStyle='#ffd100';x.lineWidth=3;x.beginPath();x.arc(252,546,18,0,Math.PI*2);x.stroke();label(x,'ABS',252,551,13,'#ffd100','center');
  stroke([[799,535],[819,535],[824,540],[848,536],[840,550],[821,550],[815,542],[799,542],[799,535]],'#ff792b');stroke([[808,534],[808,529],[822,529]],'#ff792b');
  stroke([[910,534],[920,534],[920,530],[934,530],[934,534],[941,534],[945,540],[953,540],[953,553],[945,553],[942,560],[919,560],[917,554],[910,554],[910,534]],'#ffd100');x.restore();
}
