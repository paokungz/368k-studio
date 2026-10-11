"""Offline 368K theme engine. Known firmware, bounded appearance edits only."""
import functools, gzip, hashlib, io, json, os, pathlib, re, struct, types, uuid, zipfile
from PIL import Image, ImageOps, ImageChops
from qrc import STOCK_SHA, tables_from_elf, read_resources
import boot_lab

BASE=pathlib.Path(__file__).resolve().parent
PRIVATE=pathlib.Path(os.environ.get('STUDIO_PRIVATE_DIR',str(pathlib.Path(os.environ.get('LOCALAPPDATA',str(pathlib.Path.home())))/'368KStudio'/'private'))).expanduser().resolve()

def asset_file(name):
 name=name.lstrip('/')
 local=(PRIVATE/'assets'/name).resolve()
 require(local.is_relative_to((PRIVATE/'assets').resolve()),'Invalid asset path')
 if local.is_file():return local
 bundled=(BASE/'assets'/name).resolve()
 require(bundled.is_relative_to((BASE/'assets').resolve()) and bundled.is_file(),'ไม่พบภาพ เตรียมสำเนาส่วนตัวตามคู่มือก่อน')
 return bundled

def readiness():
 try:
  stock()
  marker=json.loads((PRIVATE/'ready.json').read_text(encoding='utf-8'))
  require(marker.get('launcher_sha256')==STOCK_SHA and marker.get('resources')==3076,'ชุดภาพส่วนตัวยังเตรียมไม่ครบ')
  require((PRIVATE/'assets/res_sport/SPORT_NIGHT_BG_24.png').is_file(),'ยังไม่ได้เตรียมชิ้นภาพส่วนตัว')
  return True,None
 except Exception as e:return False,str(e)
PARTS={
 'wallpaper':{'label':'วอลเปเปอร์ทั้งจอ','paths':[f'/res_sport/SPORT_NIGHT_BG_{n}.png' for n in (6,12,18,24)],'size':[1024,600]},
 'ring':{'label':'พื้นวงรอบเครื่อง','paths':['/res/Other/dark/sport/bg0.png','/res/Other/dark/sport/bg0_1.png'],'size':[470,518]},
 'left':{'label':'แผงข้อมูลซ้าย','paths':['/res_sport/SPORT_NIGHT_BG_LEFT_3.png'],'size':[329,324]},
 'right':{'label':'แผงมาตรวัดขวา','paths':['/res_sport/SPORT_NIGHT_BG_RIGHT_3.png'],'size':[329,324]},
 'gear':{'label':'พื้นช่องเกียร์','paths':['/res_sport/SPORT_NIGHT_GEAR_bg.png'],'size':[140,103]},
 'glow':{'label':'แสงพื้น','paths':['/res_sport/SPORT_NIGHT_BG_sport.png'],'size':[462,83]},
 'speed':{'label':'สีตัวเลขความเร็ว','paths':[f'/res_sport/SPORT_NIGHT_SPEED_{n}.png' for n in range(10)]+['/res_sport/SPORT_NIGHT_SPEED_km_h.png','/res_sport/SPORT_NIGHT_SPEED_mph.png','/res_sport/SPORT_NIGHT_SPEED_deco.png'],'size':[70,146],'colorOnly':True},
 'rpm_numbers':{'label':'สีตัวเลขรอบเครื่อง','paths':[f'/res_sport/SPORT_NIGHT_RPM_NUM_{s}_{n}.png' for s in ('BIG','SMALL') for n in range(8)]+['/res_sport/SPORT_NIGHT_RPM_NUM_unit.png'],'size':[34,28],'colorOnly':True},
 'rpm_accent':{'label':'สีวง/ขีดรอบเครื่อง','paths':['/res/Other/dark/sport/'+n+'.png' for n in ('deco','deco_1','kedu','kedu_1','bar_normal','pointer')],'size':[470,518],'colorOnly':True},
}
ALLOWED={p for v in PARTS.values() for p in v['paths']}
COLOR_PATHS={p for v in PARTS.values() if v.get('colorOnly') for p in v['paths']}

def red_pixel(r,g,b):return r>g*1.4 and r>b*1.3 and r>0

def require(condition,message):
 if not condition: raise ValueError(message)
def sha(b): return hashlib.sha256(b).hexdigest()
def png(im,colors=0):
 if colors:
  im=im.quantize(colors=colors,method=Image.Quantize.FASTOCTREE).convert('RGBA')
 out=io.BytesIO();im.save(out,format='PNG',optimize=True);return out.getvalue()
def decode(b):
 require(len(b)<=32*1024*1024,'รูปใหญ่เกิน 32 MB')
 with Image.open(io.BytesIO(b)) as src:
  require(src.width*src.height<=32_000_000,'รูปมีจำนวนพิกเซลมากเกินไป')
  require(src.format in ('PNG','JPEG','GIF','WEBP','BMP'),'รองรับ PNG JPG GIF WEBP BMP')
  im=ImageOps.exif_transpose(src).convert('RGBA');im.load();return im

@functools.lru_cache(maxsize=1)
def stock():
 file=PRIVATE/'data/Launcher.original'
 require(file.is_file(),'ยังไม่มี Launcher ต้นฉบับ ใช้ prepare_private.py ตามคู่มือ README')
 b=file.read_bytes();require(sha(b)==STOCK_SHA,'Launcher ต้นฉบับไม่ตรงรุ่นที่รองรับ')
 t=tables_from_elf(b);r=read_resources(b,t);require(len(r)==3076,'จำนวน resource ไม่ตรงรุ่น')
 return b,t,r

def validate_config(config):
 require(isinstance(config,dict),'โปรเจกต์ไม่ถูกต้อง')
 parts=config.get('parts',{});require(isinstance(parts,dict) and set(parts)<=set(PARTS),'ส่วนที่เลือกไม่รองรับ')
 for k,v in parts.items():
  require(isinstance(v,dict),'ข้อมูลส่วนภาพไม่ถูกต้อง')
  require(type(v.get('enabled',False)) is bool,'enabled ต้องเป็น boolean')
  require(v.get('mode','tint') in ('tint','image'),'วิธีแก้ภาพไม่รองรับ')
  if PARTS[k].get('colorOnly'):
   require(v.get('mode','tint')=='tint','ตัวเลขและวงรอบเครื่องปรับได้เฉพาะสี')
   require(v.get('opacity',100)==100,'ตัวเลขและวงรอบเครื่องต้องคงความทึบเดิม')
  require(v.get('fit','cover') in ('cover','contain','stretch'),'วิธีจัดภาพไม่รองรับ')
  require(type(v.get('opacity',100)) in (int,float) and 0<=v.get('opacity',100)<=100,'ความทึบต้องอยู่ระหว่าง 0–100')
  require(re.fullmatch(r'#[0-9a-fA-F]{6}',v.get('color','#afafaf')) is not None,'ค่าสีไม่ถูกต้อง')
  require(v.get('colors',0) in (0,64,128,256),'จำนวนสี PNG ไม่ถูกต้อง')
  for axis in ('x','y'):
   require(type(v.get(axis,0.5)) in (int,float) and 0<=v.get(axis,0.5)<=1,'ตำแหน่งครอปต้องอยู่ระหว่าง 0–1')
 return parts

def convert_image(b,size,fit='cover',centering=(.5,.5),colors=0):
 im=decode(b)
 if fit=='cover': im=ImageOps.fit(im,tuple(size),Image.Resampling.LANCZOS,centering=centering)
 elif fit=='contain': im=ImageOps.pad(im,tuple(size),Image.Resampling.LANCZOS,color=(0,0,0,255),centering=centering)
 else: im=im.resize(tuple(size),Image.Resampling.LANCZOS)
 return Image.open(io.BytesIO(png(im,colors))).convert('RGBA')

def transform(original,options,image=None,wallpaper=False,color_only=False):
 old=decode(original)
 if color_only:
  color=tuple(int(options.get('color','#ffffff')[i:i+2],16) for i in (1,3,5))
  new=Image.new('RGBA',old.size)
  new.putdata([(r,g,b,a) if a==0 or red_pixel(r,g,b) else (*[(c*max(r,g,b)+127)//255 for c in color],a) for r,g,b,a in old.get_flattened_data()])
  return png(new)
 if options.get('mode')=='image':
  require(image is not None,'เลือกภาพก่อนสร้างไฟล์')
  if wallpaper and options.get('opacity',100)==100 and options.get('colors',0)==0:
   with Image.open(io.BytesIO(image)) as source:
    if source.format=='PNG' and source.size==old.size and not source.getexif():return image
  new=convert_image(image,old.size,options.get('fit','cover'),(options.get('x',.5),options.get('y',.5)),options.get('colors',0))
  if not wallpaper: new.putalpha(ImageChops.multiply(new.getchannel('A'),old.getchannel('A')))
 else:
  color=tuple(int(options.get('color','#afafaf')[i:i+2],16) for i in (1,3,5))
  new=Image.new('RGBA',old.size)
  new.putdata([(*[min(255,c+((299*r+587*g+114*b)//1000)//4) for c in color],a) for r,g,b,a in old.get_flattened_data()])
 alpha=new.getchannel('A').point([int(v*options.get('opacity',100)/100+.5) for v in range(256)])
 new.putalpha(alpha)
 # Keep RGB values of fully transparent source pixels stable in background masks.
 if not wallpaper:
  visible=old.getchannel('A').point(lambda a:255 if a else 0)
  new=Image.composite(new,old,visible)
 return png(new)

def replacements(config,image_loader):
 b,t,r=stock();parts=validate_config(config);result={}
 indexed={e['path']:e for e in r}
 for key,opt in parts.items():
  if not opt.get('enabled'):continue
  image=image_loader(opt.get('image','example-wallpaper')) if opt.get('mode')=='image' else None
  for name in PARTS[key]['paths']:
   e=indexed[name];result[name]=transform(b[e['offset']:e['offset']+e['length']],opt,image,key=='wallpaper',PARTS[key].get('colorOnly',False))
 return result

def pack(old,tables,entries,repl):
 require(set(repl)<=ALLOWED,'พยายามแก้ resource นอกขอบเขตพื้นหลัง')
 candidate=bytearray(old);budgets=[]
 groups=sorted({e['group'] for e in entries if e['path'] in repl})
 for group in groups:
  data=bytearray();shared={}
  for e in entries:
   if e['group']!=group:continue
   payload=repl.get(e['path'],old[e['offset']:e['offset']+e['length']]);key=sha(payload)
   if key not in shared:
    shared[key]=len(data);data.extend(struct.pack('>I',len(payload))+payload)
   struct.pack_into('>I',candidate,e['node_offset']+10,shared[key])
  start,capacity=tables[group]['data']
  budgets.append({'group':group,'capacity':capacity,'used':len(data),'remaining':capacity-len(data)})
  require(len(data)<=capacity,f'ภาพใหญ่เกินพื้นที่ {group} ลดจำนวนสี PNG เป็น 256 / 128 / 64 แล้วลองใหม่')
  candidate[start:start+capacity]=data+bytes(capacity-len(data))
 return bytes(candidate),groups,budgets

def verify(old,new,tables,repl):
 require(sha(old)==STOCK_SHA and len(old)==len(new),'ไฟล์ฐานหรือขนาด Launcher ไม่ตรง')
 require(set(repl)<=ALLOWED and tables_from_elf(new)==tables,'โครงสร้าง ELF เปลี่ยน')
 before=read_resources(old,tables);after=read_resources(new,tables)
 require(len(before)==len(after)==3076,'จำนวน resource เปลี่ยน')
 changed=[]
 for a,b in zip(before,after):
  require(all(a[k]==b[k] for k in ('path','group','flags','language','country','node_offset')),'metadata resource เปลี่ยน')
  source=old[a['offset']:a['offset']+a['length']];actual=new[b['offset']:b['offset']+b['length']]
  name=a['path']
  if name in repl:
   require(a['flags']==0 and actual==repl[name],'ภาพที่ฝังไม่ตรงกับภาพที่แปลง')
   require(decode(source).size==decode(actual).size,'ขนาด component เปลี่ยน')
   if name in COLOR_PATHS:
    left,right=decode(source),decode(actual)
    for pa,pb in zip(left.get_flattened_data(),right.get_flattened_data()):
     require(pa[3]==pb[3],'ความทึบของตัวเลข/วงรอบเครื่องเปลี่ยน')
     if pa[3]==0 or red_pixel(*pa[:3]):require(pa==pb,'พิกเซลโปร่งหรือส่วนรอบสูงสีแดงเปลี่ยน')
   if source!=actual:changed.append({'path':name,'group':a['group'],'sha256':sha(actual),'bytes':len(actual)})
  else:require(source==actual,'resource นอกส่วนที่เลือกเปลี่ยน: '+name)
 groups={e['group'] for e in before if e['path'] in repl}
 intervals=[(tables[g]['data'][0],sum(tables[g]['data'])) for g in groups]
 intervals += [(e['node_offset']+10,e['node_offset']+14) for e in before if e['group'] in groups]
 position=0
 for start,end in sorted(intervals):
  require(old[position:start]==new[position:start],'ข้อมูลนอกภาพหรือโค้ดเปลี่ยน');position=end
 require(old[position:]==new[position:],'ข้อมูลนอกภาพหรือโค้ดเปลี่ยน')
 return changed

def prepare(config,image_loader):
 old,tables,entries=stock();repl=replacements(config,image_loader)
 new,groups,budgets=pack(old,tables,entries,repl)
 changed=verify(old,new,tables,repl)
 return new,repl,groups,budgets,changed

def build_theme(folder,config,image_loader,progress=lambda m:None):
 folder=pathlib.Path(folder);require(not folder.exists(),'โฟลเดอร์ผลลัพธ์มีอยู่แล้ว');folder.mkdir(parents=True)
 progress('แปลงภาพและตรวจ resource ทั้งหมด');new,repl,groups,budgets,changed=prepare(config,image_loader)
 old,tables,entries=stock();require(changed,'ยังไม่ได้เลือกส่วนที่ต้องการเปลี่ยน')
 (folder/'Launcher.theme.bin').write_bytes(new)
 verify(old,(folder/'Launcher.theme.bin').read_bytes(),tables,repl)
 patches=[];reconstruct=bytearray(old)
 for i,g in enumerate(groups):
  start=min(tables[g][k][0] for k in ('struct','name','data'))//4096*4096
  end=(sum(tables[g]['data'])+4095)//4096*4096;payload=new[start:end];name=f'resource-{i}.patch'
  (folder/name).write_bytes(payload);reconstruct[start:end]=payload
  patches.append({'file':name,'offset':start,'bytes':len(payload),'sha256':sha(payload)})
 require(reconstruct==new,'แพตช์สร้างไฟล์กลับมาไม่ตรง')
 images=folder/'converted';images.mkdir()
 for name,payload in repl.items():(images/(name.strip('/').replace('/','__'))).write_bytes(payload)
 manifest={'kind':'sport-theme','status':'OFFLINE_VERIFIED_NOT_INSTALLED','candidate_sha256':sha(new),'original_sha256':STOCK_SHA,
           'candidate_bytes':len(new),'changed_resources':changed,'unchanged_resources':3076-len(changed),
           'patches':patches,'budgets':budgets,'code_unchanged':True,'vehicle_write_performed':False,
           'protected_warning_resources_identical':True,
           'appearance_color_resources_changed':[e['path'] for e in changed if e['path'] in COLOR_PATHS],
           'number_shapes_alpha_and_red_zone_preserved':True}
 (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 (folder/'project.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
 (folder/'README.txt').write_text('368K Sport night theme\nไฟล์ Launcher และภาพที่แปลง ตรวจแล้วบนคอม ยังไม่ติดตั้งบนรถ\nเปลี่ยนเฉพาะภาพ/สีที่เลือก คงรูปทรงตัวเลข alpha ส่วนเตือนรอบสูง ไฟเตือน และโค้ด\nดู manifest.json สำหรับ SHA และขอบเขตการเปลี่ยน\n',encoding='utf-8')
 return manifest

def build_boot(folder,source,progress=lambda m:None):
 progress('แปลง GIF เป็น 99 เฟรมและแพ็ก initramfs')
 folder=pathlib.Path(folder);require(not folder.exists(),'โฟลเดอร์ผลลัพธ์มีอยู่แล้ว')
 source_folder=folder.parent/'sources';source_folder.mkdir(exist_ok=True)
 gif=source_folder/(uuid.uuid4().hex+'.gif');gif.write_bytes(source)
 require((PRIVATE/'data/boot.original.img').is_file(),'ยังไม่มีสำเนาบูต ใช้ prepare_private.py --boot ตามคู่มือ')
 return boot_lab.build(types.SimpleNamespace(boot=PRIVATE/'data/boot.original.img',gif=gif,out=folder,overwrite=False))
