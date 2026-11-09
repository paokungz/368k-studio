import {PARTS,SIZES,transformPixels,fitRect} from './model.mjs';
export function canvas(w,h){const c=document.createElement('canvas');c.width=w;c.height=h;return c;}
function label(ctx,value,x,y,size=24,color='#ecf6fc',align='left'){ctx.fillStyle=color;ctx.font=`600 ${size}px system-ui, sans-serif`;ctx.textAlign=align;ctx.fillText(value,x,y);}
function rounded(ctx,x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke();}}
/** Original, code-drawn placeholders. No manufacturer's PNG/font is shipped. */
export function concept(path){
  const [w,h]=SIZES[path],c=canvas(w,h),x=c.getContext('2d');
  if(/BG_\d+\.png$/.test(path)){
    const g=x.createLinearGradient(0,0,w,h);g.addColorStop(0,'#07151f');g.addColorStop(.5,'#183c46');g.addColorStop(1,'#101e29');x.fillStyle=g;x.fillRect(0,0,w,h);
    x.strokeStyle='#2c5564';x.lineWidth=1;for(let n=-600;n<1600;n+=100){x.beginPath();x.moveTo(n,0);x.lineTo(n+600,h);x.stroke();}
  }else if(/bg0(?:_1)?\.png$/.test(path)){
    x.beginPath();x.arc(w/2,h/2,202,0,Math.PI*2);x.arc(w/2,h/2,174,0,Math.PI*2,true);x.fillStyle='rgba(155,192,208,.35)';x.fill('evenodd');
    x.strokeStyle='#759ba9';x.lineWidth=2;x.beginPath();x.arc(w/2,h/2,202,0,Math.PI*2);x.stroke();
  }else if(/BG_(LEFT|RIGHT)_3/.test(path)){
    rounded(x,9,8,w-18,h-16,18,'rgba(70,100,114,.45)','#557c8f');
  }else if(path.includes('GEAR_bg'))rounded(x,2,4,w-4,h-8,20,'rgba(85,123,140,.6)','#7196a5');
  else if(path.includes('BG_sport')){const g=x.createLinearGradient(0,0,w,0);g.addColorStop(0,'rgba(70,135,170,0)');g.addColorStop(.5,'rgba(120,185,210,.45)');g.addColorStop(1,'rgba(70,135,170,0)');x.fillStyle=g;x.fillRect(0,30,w,22);}
  else if(/SPEED_\d/.test(path))label(x,path.match(/SPEED_(\d)/)[1],w/2,119,105,'#f4faff','center');
  else if(/SPEED_(km_h|mph)/.test(path))label(x,path.includes('km_h')?'km/h':'mph',w/2,80,22,'#f4faff','center');
  else if(path.includes('SPEED_deco')){x.fillStyle='#d8f2ff';x.fillRect(8,h-22,w-16,3);}
  else if(/RPM_NUM_(BIG|SMALL)_\d/.test(path))label(x,path.match(/_(\d)\.png/)[1],w/2,24,24,'#ecf6fc','center');
  else if(path.includes('RPM_NUM_unit'))label(x,'rpm',w/2,20,12,'#ecf6fc','center');
  else {
    x.strokeStyle='#b9def2';x.lineWidth=path.includes('bar_normal')?12:3;
    if(path.includes('kedu')){for(let n=0;n<61;n++){const a=(130+n*280/60)*Math.PI/180;x.strokeStyle=n>45?'#ef5d36':'#b9def2';x.beginPath();x.moveTo(w/2+Math.cos(a)*165,h/2+Math.sin(a)*165);x.lineTo(w/2+Math.cos(a)*(n%5===0?153:158),h/2+Math.sin(a)*(n%5===0?153:158));x.stroke();}}
    else if(path.includes('pointer')){x.beginPath();x.moveTo(w/2-6,h/2+186);x.lineTo(w/2+7,h/2+186);x.lineTo(w/2,h/2+156);x.closePath();x.fillStyle='#d6f4ff';x.fill();}
    else {x.beginPath();x.arc(w/2,h/2,188,Math.PI*.72,Math.PI*2.28);x.stroke();}
  }
  return c;
}
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
  const stock=new Map(Object.keys(SIZES).map(path=>[path,concept(path)])),cache=new Map();
  let state;
  function get(path,original=false){
    const source=state.templates.get(path)?.image||stock.get(path),key=Object.keys(PARTS).find(k=>PARTS[k].paths.includes(path));
    const option=state.config.parts[key];if(original||!option.enabled)return source;
    if(!cache.has(path))cache.set(path,transformed(source,option,PARTS[key],state.images.get(option.image)?.image));
    return cache.get(path);
  }
  function render(next){
    state=next;const x=target.getContext('2d');x.clearRect(0,0,1024,600);x.fillStyle='#08121a';x.fillRect(0,0,1024,600);
    for(const key of ['wallpaper','left','right','glow','gear','ring']){const p=PARTS[key];x.drawImage(get(p.paths.at(-1),next.original),...p.at);}
    for(const name of ['deco','kedu','pointer'])x.drawImage(get(`/res/Other/dark/sport/${name}.png`,next.original),289,38);
    const center=[524,297];for(let n=0;n<=10;n++){const a=(130+n*28)*Math.PI/180,px=center[0]+Math.cos(a)*143,py=center[1]+Math.sin(a)*143;if(n<8)x.drawImage(get(`/res_sport/SPORT_NIGHT_RPM_NUM_BIG_${n}.png`,next.original),px-17,py-14);else label(x,String(n),px,py+10,24,'#f17845','center');}
    if(next.rpm>0){x.save();x.strokeStyle=next.original||!next.config.parts.rpm_accent.enabled?'#b9def2':next.config.parts.rpm_accent.color;x.lineWidth=9;x.beginPath();x.arc(...center,195,Math.PI*.72,Math.PI*.72+next.rpm/7000*Math.PI*1.12);x.stroke();x.restore();}
    const digits=String(next.speed);let px=524-digits.length*35;for(const d of digits){x.drawImage(get(`/res_sport/SPORT_NIGHT_SPEED_${d}.png`,next.original),px,213);px+=70;}
    x.drawImage(get('/res_sport/SPORT_NIGHT_SPEED_km_h.png',next.original),489,315);
    label(x,'16:54',772,67,28);label(x,'S',512,565,35,'#f2f8fc','center');label(x,'ODO 0000 km',512,593,21,'#ecf6fc','center');
    label(x,'TIRE / PSI',37,198,15,'#a8c4d0');label(x,'F    33.1',38,246,26);label(x,'R   39.5',38,308,26);label(x,'36°C   /   47°C',38,353,17);label(x,'13.3 V',38,431,24);
    for(const [base,letter,low,col,fraction]of [[814,'F','E','#a7e455',.8],[935,'H','C','#4ec8f5',.3]]){label(x,letter,base,190,19);label(x,low,base,444,19);rounded(x,base,210,18,200,8,'#152d3a','#7594a1');for(let n=0;n<8;n++){x.fillStyle=n>=8*fraction?'#294351':col;x.fillRect(base+3,215+(7-n)*23,12,19);}}
    label(x,'KEY',34,558,17,'#a8e452');label(x,'ABS',233,558,18,'#ffd15e');label(x,'OIL',815,558,18,'#ff8456');label(x,'ENGINE',913,558,17,'#ffd15e');
    if(next.guides){const p=PARTS[next.selected];if(p.at){x.strokeStyle='#bcdfba';x.lineWidth=2;x.setLineDash([8,6]);x.strokeRect(...p.at,...p.size);x.setLineDash([]);}}
  }
  return {render,get,clear:()=>cache.clear(),stock};
}
