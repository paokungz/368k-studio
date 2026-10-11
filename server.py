"""Loopback-only desktop UI service; all device actions are explicit UI requests."""
import argparse, base64, datetime, hashlib, io, json, logging, mimetypes, os, pathlib, re, secrets, socket, sys, threading, traceback, urllib.parse, uuid, webbrowser, zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import core
from journal import write_json
import time,urllib.request

def now():return datetime.datetime.now().astimezone().isoformat()
def instance_lock(data):
 """Windows lock is released by the OS even if the program terminates."""
 import msvcrt
 path=pathlib.Path(data);path.mkdir(parents=True,exist_ok=True)
 handle=(path/'instance.lock').open('a+b');handle.write(b'0');handle.flush();handle.seek(0)
 try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);return handle
 except OSError:handle.close();return None
class Studio:
 def __init__(self,data,exports):
  self.data=pathlib.Path(data).resolve();self.exports=pathlib.Path(exports).resolve()
  self.data.mkdir(parents=True,exist_ok=True);self.exports.mkdir(parents=True,exist_ok=True)
  (self.data/'images').mkdir(exist_ok=True)
  self.token=secrets.token_urlsafe(32);self.jobs={};self.lock=threading.RLock();self.engine_lock=threading.Lock();self.port=None;self.warning=None
  saved=self.data/'jobs.json'
  try:
   if saved.exists():
    self.jobs=json.loads(saved.read_text(encoding='utf-8'))
    core.require(isinstance(self.jobs,dict) and all(isinstance(j,dict) for j in self.jobs.values()),'บันทึกงานไม่ถูกต้อง')
    for j in self.jobs.values():
     if j.get('status')=='running':j.update(status='interrupted',message='โปรแกรมหยุดระหว่างงาน ตรวจผลล่าสุดก่อนเขียนซ้ำ' if j.get('kind','').startswith('device-') else 'งานก่อนปิดโปรแกรมยังไม่เสร็จ สร้างไฟล์ใหม่ได้')
  except Exception:
   self.jobs={};self.warning='บันทึกงานเดิมอ่านไม่ได้ ใช้ปุ่มตรวจผลล่าสุดเพื่อตรวจรถก่อนเขียน';logging.exception('Bad jobs journal')
 def flush_jobs(self):
  with self.lock:write_json(self.data/'jobs.json',{k:dict(v) for k,v in list(self.jobs.items())[-60:]})
 def project(self):
  file=self.data/'project.json'
  if not file.exists():return None
  try:
   config=json.loads(file.read_text(encoding='utf-8'));core.validate_config(config);return config
  except Exception:
   logging.exception('Bad saved project');self.warning='โปรเจกต์เดิมอ่านไม่ได้ จึงเปิดแบบเริ่มต้นให้ สำเนาไฟล์ที่เสียยังเก็บไว้'
   file.replace(self.data/('project-unreadable-'+uuid.uuid4().hex+'.json'));return None
 def image(self,image_id):
  if image_id=='example-wallpaper':return core.asset_file('example-wallpaper.png').read_bytes()
  if image_id=='example-animation':return core.asset_file('example-animation.gif').read_bytes()
  core.require(isinstance(image_id,str) and re.fullmatch('[0-9a-f]{32}',image_id),'รหัสภาพไม่ถูกต้อง')
  path=self.data/'images'/image_id;core.require(path.is_file(),'ไม่พบภาพ เลือกไฟล์ใหม่อีกครั้ง');return path.read_bytes()
 def job(self,kind,work):
  key=uuid.uuid4().hex
  obj={'id':key,'kind':kind,'status':'running','message':'กำลังเริ่ม','time':now()};self.jobs[key]=obj
  self.flush_jobs()
  def progress(message):obj['message']=message;self.flush_jobs()
  def run():
   try:obj['result']=work(key,progress);obj.update(status='done',message='เสร็จแล้ว')
   except Exception as e:
    logging.exception('job failed');obj.update(status='error',message=str(e),details=getattr(e,'details',None))
   finally:
    try:self.flush_jobs()
    except Exception:logging.exception('Job persistence failed')
  threading.Thread(target=run,daemon=True).start();return obj.copy()
 def build(self,config,kind):
  core.require(kind in ('theme','boot'),'ชนิดงานไม่รองรับ')
  core.validate_config(config)
  def work(key,progress):
   folder=self.exports/('project-'+key)
   progress('รอคิวแปลงและตรวจไฟล์')
   with self.engine_lock:
    if kind=='boot':result=core.build_boot(folder,self.image(config.get('bootImage','example-animation')),progress)
    else:result=core.build_theme(folder,config,self.image,progress)
   progress('บันทึกไฟล์และจัดชุดดาวน์โหลด')
   archive=self.exports/('project-'+key+'.zip')
   with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
    for f in folder.rglob('*'):
     if f.is_file():z.write(f,str(f.relative_to(folder)))
   return {'folder':str(folder),'zip':str(archive),'manifest':result,'download':'/download/'+key}
  obj=self.job('build-'+kind,work);self.jobs[obj['id']]['config']=config;self.flush_jobs();return obj

class Handler(BaseHTTPRequestHandler):
 server_version='368KStudio/1.1'
 def log_message(self,fmt,*args):logging.info(fmt,*args)
 @property
 def app(self):return self.server.studio
 def json(self,body,code=200):self.send(json.dumps(body,ensure_ascii=False).encode(),code,'application/json; charset=utf-8')
 def send(self,data,code=200,content='application/octet-stream',attachment=None):
  self.send_response(code);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)))
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
  if attachment:self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
  self.end_headers();self.wfile.write(data)
 def allowed(self):
  expected=f'127.0.0.1:{self.app.port}'
  core.require(self.headers.get('Host')==expected,'Host ไม่ตรงกับโปรแกรม')
  if self.command=='POST':
   core.require(self.headers.get('X-Studio-Token')==self.app.token,'สิทธิ์ session ไม่ถูกต้อง')
   origin=self.headers.get('Origin')
   core.require(origin in (None,'http://'+expected),'ไม่อนุญาตคำสั่งจากเว็บไซต์อื่น')
 def do_GET(self):
  try:
   self.allowed();url=urllib.parse.urlsplit(self.path);p=urllib.parse.unquote(url.path)
   if p in ('/','/index.html'):return self.send((core.BASE/'web/index.html').read_bytes(),content='text/html; charset=utf-8')
   if p in ('/app.js','/style.css'):return self.send((core.BASE/'web'/p[1:]).read_bytes(),content='text/javascript' if p.endswith('.js') else 'text/css')
   if p=='/api/state':
    core.require(self.headers.get('X-Studio-Token')==self.app.token,'สิทธิ์ session ไม่ถูกต้อง')
    config=self.app.project()
    ready,setup_error=core.readiness()
    return self.json({'parts':core.PARTS,'exports':str(self.app.exports),'config':config,'version':'1.1-public','ready':ready,'setupError':setup_error,'bootReady':(core.PRIVATE/'data/boot.original.img').is_file(),'deviceFeatures':ready,'recentJobs':list(self.app.jobs.values())[-30:],'warning':self.app.warning})
   if p.startswith('/assets/'):
    f=core.asset_file(p[len('/assets/'):])
    return self.send(f.read_bytes(),content=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
   if p.startswith('/image/'):
    b=self.app.image(p.rsplit('/',1)[1]);return self.send(b,content='image/'+{'JPEG':'jpeg'}.get(core.Image.open(io.BytesIO(b)).format,core.Image.open(io.BytesIO(b)).format.lower()))
   if p.startswith('/download/'):
    key=p.rsplit('/',1)[1];core.require(re.fullmatch('[a-f0-9]{32}',key),'รหัสผลลัพธ์ไม่ถูกต้อง')
    archive=self.app.exports/('project-'+key+'.zip');core.require(archive.is_file(),'ยังไม่มีไฟล์ดาวน์โหลด')
    return self.send(archive.read_bytes(),attachment='368K-project-'+key[:8]+'.zip')
   if p.startswith('/result/'):
    segments=p.split('/');core.require(len(segments)==4 and re.fullmatch('[a-f0-9]{32}',segments[2]) and segments[3] in ('preview.gif','preview.png'),'ไฟล์ตัวอย่างไม่ถูกต้อง')
    f=self.app.exports/('project-'+segments[2])/segments[3];core.require(f.is_file(),'ยังไม่มีภาพตัวอย่าง')
    return self.send(f.read_bytes(),content=mimetypes.guess_type(str(f))[0])
   return self.json({'error':'ไม่พบหน้า'},404)
  except Exception as e:self.json({'error':str(e)},400)
 def do_POST(self):
  try:
   self.allowed();length=int(self.headers.get('Content-Length',0));core.require(0<length<=46*1024*1024,'ข้อมูลคำขอใหญ่เกินกำหนด')
   data=json.loads(self.rfile.read(length));core.require(isinstance(data,dict),'คำขอไม่ถูกต้อง')
   p=urllib.parse.urlsplit(self.path).path
   if p in ('/api/build','/api/preview') or p.startswith('/api/device/'):
    ready,error=core.readiness();core.require(ready,error)
   if p=='/api/upload':
    raw=base64.b64decode(data['data'],validate=True);im=core.decode(raw)
    key=uuid.uuid4().hex;(self.app.data/'images'/key).write_bytes(raw)
    return self.json({'id':key,'name':str(data.get('name','ภาพ'))[:160],'size':list(im.size),'bytes':len(raw)})
   if p=='/api/preview':
    config=data['config'];core.validate_config(config)
    with self.app.engine_lock:
     repl=core.replacements(config,self.app.image)
     _,tables,entries=core.stock();budget=None;error=None
     try:new,groups,budget=core.pack(core.stock()[0],tables,entries,repl)
     except ValueError as e:error=str(e)
    images={n:'data:image/png;base64,'+base64.b64encode(b).decode() for n,b in repl.items()}
    return self.json({'images':images,'selected':len(repl),'budgets':budget,'buildError':error})
   if p=='/api/save':
    core.validate_config(data['config']);write_json(self.app.data/'project.json',data['config']);return self.json({'saved':True})
   if p=='/api/build':return self.json(self.app.build(data['config'],data.get('kind','theme')))
   if p=='/api/job':
    obj=self.app.jobs.get(data.get('id'));core.require(obj is not None,'ไม่พบงาน');return self.json(obj.copy())
   if p=='/api/open-folder':
    os.startfile(str(self.app.exports));return self.json({'opened':True})
   if p=='/api/quit':
    core.require(not any(j['status']=='running' for j in self.app.jobs.values()),'รอให้งานที่กำลังทำเสร็จก่อนปิดโปรแกรม')
    self.json({'closed':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   if p=='/api/device/check':
    from device import check
    return self.json(self.app.job('device-check',lambda key,progress:check(progress,self.app.exports)))
   if p=='/api/device/reconcile':
    from device import reconcile
    return self.json(self.app.job('device-reconcile',lambda key,progress:reconcile(self.app.exports,progress)))
   if p=='/api/device/unlock':
    core.require(data.get('parked') is True,'ยืนยันรถจอด ดับเครื่อง และเปิดจอ ก่อนปลดล็อก')
    from device import clear_commit_lock
    return self.json(self.app.job('device-unlock',lambda key,progress:clear_commit_lock(self.app.exports,key,progress)))
   if p=='/api/device/install':
    core.require(data.get('parked') is True,'ยืนยันรถจอด ดับเครื่อง และเปิดจอ ก่อนเขียนไฟล์')
    obj=self.app.jobs.get(data.get('build'));core.require(obj and obj['status']=='done' and obj['kind']=='build-theme','ต้องสร้างไฟล์ธีมที่ตรวจผ่านก่อน')
    folder=pathlib.Path(obj['result']['folder'])
    from device import install
    return self.json(self.app.job('device-install',lambda key,progress:install(folder,self.app.exports,key,progress)))
   if p=='/api/device/restore':
    core.require(data.get('parked') is True,'ยืนยันรถจอด ดับเครื่อง และเปิดจอ ก่อนคืนไฟล์')
    from device import restore
    return self.json(self.app.job('device-restore',lambda key,progress:restore(self.app.exports,key,progress)))
   return self.json({'error':'ไม่พบคำสั่ง'},404)
  except Exception as e:
   logging.exception('request failed');self.json({'error':str(e)},400)

def main():
 a=argparse.ArgumentParser();a.add_argument('--no-browser',action='store_true');a.add_argument('--port',type=int,default=8768)
 a.add_argument('--data-dir');a.add_argument('--export-dir');args=a.parse_args()
 data=args.data_dir or str(pathlib.Path(os.environ.get('LOCALAPPDATA',str(pathlib.Path.home())))/'368KStudio-public')
 exports=args.export_dir or str(pathlib.Path.home()/'Documents/368K Studio/exports')
 handle=instance_lock(data)
 if handle is None:
  if args.no_browser:return
  for attempt in range(20):
   try:
    state=json.loads((pathlib.Path(data)/'session.json').read_text(encoding='utf-8'));url=urllib.parse.urlsplit(state['url'])
    core.require(url.scheme=='http' and url.hostname=='127.0.0.1' and url.netloc=='127.0.0.1:'+str(url.port),'URL ของโปรแกรมเดิมไม่ถูกต้อง')
    token=urllib.parse.parse_qs(url.query)['token'][0]
    request=urllib.request.Request('http://'+url.netloc+'/api/state',headers={'X-Studio-Token':token})
    with urllib.request.urlopen(request,timeout=.5) as response:core.require(response.status==200,'โปรแกรมเดิมยังไม่พร้อม')
    webbrowser.open(state['url']);return
   except Exception:time.sleep(.15)
  raise RuntimeError('โปรแกรมเดิมกำลังเปิดหรือไม่ตอบสนอง รอสักครู่แล้วเปิดใหม่')
 app=Studio(data,exports)
 logging.basicConfig(filename=str(app.data/'studio.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
 try:server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 except OSError:server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
 server.studio=app;app.port=server.server_port;url=f'http://127.0.0.1:{app.port}/?token={app.token}'
 write_json(app.data/'session.json',{'url':url,'pid':os.getpid(),'port':app.port})
 if sys.stdout:print('368K Studio '+url,flush=True)
 if not args.no_browser:webbrowser.open(url)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close();handle.close()

if __name__=='__main__':
 try:main()
 except Exception:
  logging.exception('startup failure')
  if getattr(sys,'frozen',False):
   import ctypes
   ctypes.windll.user32.MessageBoxW(0,'เปิดโปรแกรมไม่สำเร็จ ดู studio.log ใน LocalAppData/368KStudio','368K Studio',16)
  else:raise
