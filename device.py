"""Explicit Wi-Fi operations for known 368K Launcher themes. No boot flashing."""
import base64, functools, json, logging, pathlib, re, shlex, socket, threading, time, uuid
from journal import write_json
import core

HOST='192.168.3.1'
KNOWN_GRAY='c58fef130c8530f91e52d922d7697362709d8c5addfc1277d7d3696bcddab219'
BASE='/data/codex368k-studio'
LOCK=threading.Lock()
CURRENT=threading.local()
class Session:
 def __enter__(self):
  self.sock=socket.create_connection((HOST,23),timeout=5);self.sock.settimeout(.2)
  try:
   self.hello();self.sock.sendall(b'root\r\n');core.require(b'# ' in self.hello(),'เข้า shell รถไม่ได้')
   self.sock.sendall(b'stty -echo\r\n');self.hello(.3);return self
  except Exception:self.sock.close();raise
 def __exit__(self,*a):self.sock.close()
 def hello(self,seconds=2):
  out=bytearray();end=time.monotonic()+seconds;state=0;command=0
  while time.monotonic()<end:
   try:b=self.sock.recv(65536)
   except socket.timeout:continue
   if not b:break
   for c in b:
    if state==0:
     if c==255:state=1
     else:out.append(c)
    elif state==1:
     if c in (251,252,253,254):command=c;state=2
     elif c==250:state=3
     else:state=0
    elif state==2:
     if command==253:self.sock.sendall(bytes([255,252,c]))
     if command==251:self.sock.sendall(bytes([255,253 if c in (1,3) else 254,c]))
     state=0
    elif state==3:
     if c==255:state=4
    elif state==4:state=0 if c==240 else 3
  return bytes(out)
 def run(self,command,timeout=90):
  marker='DONE_'+uuid.uuid4().hex;self.sock.sendall((command+"; printf '\\n"+marker+":%s\\n' \"$?\"\r\n").encode())
  out=bytearray();end=time.monotonic()+timeout
  while time.monotonic()<end:
   try:b=self.sock.recv(65536)
   except socket.timeout:continue
   if not b:raise ConnectionError('การเชื่อมต่อรถขาด ตรวจสถานะก่อนลองอีกครั้ง')
   out.extend(b);normalized=bytes(out).replace(b'\r',b'')
   match=re.search(rb'\n'+marker.encode()+rb':(\d+)\n',normalized)
   if match:
    text=normalized[:match.start()].lstrip(b'# ').decode(errors='replace').strip()
    core.require(int(match[1])==0,'คำสั่งบนรถไม่ผ่าน: '+text);return text
  raise TimeoutError('รถไม่ตอบกลับภายในเวลาที่กำหนด')
 def hash(self,path):
  value=self.run('sha256sum '+shlex.quote(path)).split()[0]
  core.require(re.fullmatch('[0-9a-f]{64}',value),'รถส่งแฮชไม่ถูกต้อง');return value
 def upload(self,local,remote,progress=lambda s:None):
  raw=pathlib.Path(local).read_bytes();b64=base64.b64encode(raw);ready='READY_'+uuid.uuid4().hex;done='UP_'+uuid.uuid4().hex
  command=f"stty -icanon -echo min 1 time 0; printf '\\n{ready}\\n'; head -c {len(b64)} | base64 -d > {shlex.quote(remote)}; rc=$?; stty icanon; printf '\\n{done}:%s\\n' \"$rc\""
  self.sock.sendall((command+'\r\n').encode());pending=bytearray();deadline=time.monotonic()+360
  while ready.encode() not in pending:
   core.require(time.monotonic()<deadline,'หมดเวลารออัปโหลด')
   try:b=self.sock.recv(65536)
   except socket.timeout:continue
   core.require(b,'การเชื่อมต่อขาด');pending.extend(b)
  self.sock.settimeout(20);last=0
  for i in range(0,len(b64),65536):
   self.sock.sendall(b64[i:i+65536])
   if time.monotonic()-last>3:progress('ส่งไฟล์ '+str(min(100,round((i+65536)*100/len(b64))))+'%');last=time.monotonic()
  self.sock.settimeout(.2);pending=bytearray()
  while time.monotonic()<deadline:
   try:b=self.sock.recv(65536)
   except socket.timeout:continue
   core.require(b,'การเชื่อมต่อขาด');pending.extend(b)
   match=re.search(done.encode()+rb':(\d+)\n',bytes(pending).replace(b'\r',b''))
   if match:core.require(int(match[1])==0,'เขียนไฟล์อัปโหลดไม่สำเร็จ');break
  else:raise TimeoutError('อัปโหลดเกินกำหนดเวลา')
  core.require(self.hash(remote)==core.sha(raw),'แฮชไฟล์ที่ส่งขึ้นรถไม่ตรง')

def locked(fn):
 @functools.wraps(fn)
 def wrapped(*a,**kw):
  core.require(LOCK.acquire(blocking=False),'มีงานบนรถกำลังทำอยู่ รอให้จบก่อน')
  try:return fn(*a,**kw)
  finally:LOCK.release()
 return wrapped

def evidence(s,progress):
 progress('อ่านข้อมูลจอรถ');pid=s.run('pidof Launcher');core.require(pid.isdigit(),'ต้องมี Launcher เพียง process เดียว')
 disk=s.hash('/usr/bin/Launcher');running=s.hash('/proc/'+pid+'/exe')
 return {'host':HOST,'pid':pid,'disk_sha256':disk,'running_sha256':running,'uptime':s.run('cat /proc/uptime')}

def check(progress=lambda m:None,exports=None):
 if exports is not None:return reconcile(exports,progress)
 return basic_check(progress)

@locked
def basic_check(progress=lambda m:None):
 with Session() as s:
  result=evidence(s,progress)
  return result

def accepted_hashes(exports,matching=None):
 hashes={core.STOCK_SHA,KNOWN_GRAY};old,t,entries=core.stock()
 if matching in hashes:return hashes
 for file in pathlib.Path(exports).glob('project-*/manifest.json'):
  try:
   manifest=json.loads(file.read_text(encoding='utf-8'))
   if matching is not None and manifest.get('candidate_sha256')!=matching:continue
   candidate=(file.parent/'Launcher.theme.bin').read_bytes()
   if core.sha(candidate)!=manifest['candidate_sha256']:continue
   r=core.read_resources(candidate,t);repl={e['path']:candidate[e['offset']:e['offset']+e['length']] for e in r if e['path'] in core.ALLOWED}
   core.verify(old,candidate,t,repl);hashes.add(core.sha(candidate))
  except Exception:continue
 return hashes

class DeviceFailure(ValueError):
 def __init__(self,message,report):super().__init__(message);self.details=report

def abandoned_commit(s):
 raw=s.run(f'if test -f {BASE}/commit.lock/owner; then cat {BASE}/commit.lock/owner; else echo UNKNOWN; fi')
 match=re.fullmatch(r'(\d+) ([0-9a-f]{32}) ([0-9a-f-]{36})',raw)
 if not match:return False,None
 pid,key,boot_id=match.groups();current=s.run('cat /proc/sys/kernel/random/boot_id')
 alive=s.run(f'if test -d /proc/{pid}; then echo ALIVE; else echo EXITED; fi')=='ALIVE'
 return current!=boot_id or not alive,raw

@locked
def clear_commit_lock(exports,key,progress=lambda m:None):
 with Session() as s:
  before=evidence(s,progress)
  core.require(before['running_sha256'] in accepted_hashes(exports,before['running_sha256']),'process จอไม่ตรงชุดที่รองรับ')
  abandoned,owner=abandoned_commit(s);core.require(abandoned,'ยังยืนยันไม่ได้ว่าเจ้าของล็อกหยุดทำงาน ห้ามปลดล็อก')
  digest=core.sha(owner.encode())
  # Recheck owner identity at the mutation boundary; only our lock metadata is removed.
  escaped=shlex.quote(owner)
  s.run(f'test "$(cat {BASE}/commit.lock/owner)" = {escaped} && rm {BASE}/commit.lock/owner && rmdir {BASE}/commit.lock')
  core.require(s.hash('/usr/bin/Launcher')==before['disk_sha256'],'Launcher เปลี่ยนระหว่างตรวจล็อก')
  result={'status':'ABANDONED_LOCK_CLEARED','message':'ปลดล็อกงานที่หยุดแล้ว ตรวจผลล่าสุดอีกครั้งก่อนติดตั้ง/คืนค่า','owner_sha256':digest,'launcher_unchanged':True}
  save_report(exports,key,result);return result

def save_report(exports,key,report):
 context=getattr(CURRENT,'report',None)
 if context is not None and context.get('id')==key:context.update(report);report=context
 write_json(pathlib.Path(exports)/('device-'+key+'.json'),report)

@locked
def reconcile(exports,progress=lambda m:None):
 """Read disk/process and remote job state; never retry, rollback or reboot."""
 files=sorted(pathlib.Path(exports).glob('device-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
 latest=None;key=None
 for file in files:
  match=re.fullmatch('device-([0-9a-f]{32})\\.json',file.name)
  if not match:continue
  try:
   candidate=json.loads(file.read_text(encoding='utf-8'))
   if not candidate.get('before') and not candidate.get('write_intent'):continue
   latest=candidate;key=match[1];break
  except Exception:continue
 with Session() as s:
  result=evidence(s,progress);known=accepted_hashes(exports,result['running_sha256'])|accepted_hashes(exports,result['disk_sha256'])
  busy=False;state='NO_SAVED_JOB'
  if latest and latest.get('write_intent') and latest.get('action')=='install':
   remote=BASE+'/'+key
   state=s.run(f'if test -f {remote}/status.txt; then cat {remote}/status.txt; else echo NO_STATUS; fi')
   worker=s.run(f'if test -f {remote}/worker.pid; then cat {remote}/worker.pid; else echo NONE; fi')
   if worker.isdigit():
    command=s.run(f'if test -f /proc/{worker}/cmdline; then cat /proc/{worker}/cmdline; else echo EXITED; fi')
    busy=remote+'/install.sh' in command
  locked_commit=s.run(f'if test -d {BASE}/commit.lock; then echo LOCKED; else echo FREE; fi')=='LOCKED'
  can_clear=abandoned_commit(s)[0] if locked_commit else False
  if busy:outcome='REMOTE_JOB_RUNNING';message='ฝั่งรถยังทำงานอยู่ คงระบบไฟและรอ แล้วตรวจผลอีกครั้ง'
  elif latest and latest.get('expected_sha256')==result['disk_sha256']:
   boot=s.hash('/dev/mmcblk0p3')
   core.require(not latest.get('boot_before') or latest['boot_before']==boot,'แฮชบูตไม่ตรงบันทึก ต้องตรวจเพิ่มเติมก่อนเขียน')
   outcome='VERIFIED_ON_RECONNECT';message='ตรวจไฟล์บนรถแล้ว ตรงกับไฟล์ที่ตั้งใจเขียน ไม่ต้องติดตั้งซ้ำ'
  elif latest and latest.get('before',{}).get('disk_sha256')==result['disk_sha256']:
   outcome='PREVIOUS_FILE_PRESENT';message='รถยังใช้ไฟล์ก่อนทำงาน หรือได้คืนไฟล์เดิมแล้ว แก้สาเหตุและตรวจสถานะก่อนลองใหม่'
  elif result['disk_sha256'] in known:outcome='KNOWN_FILE_PRESENT';message='พบ Launcher ชุดที่ตรวจแล้วบนรถ'
  else:outcome='NEEDS_RESTORE';message='ไฟล์บนดิสก์ไม่ตรงชุดที่ตรวจไว้ ถ้า process เดิมยังเป็นชุดที่รองรับ สามารถใช้ปุ่มคืนต้นฉบับได้'
  if locked_commit:message+=' · มีล็อกการเขียนค้าง '+('ปลดล็อกได้เมื่อยืนยันรถจอด' if can_clear else 'ยังยืนยันไม่ได้ว่าเจ้าของล็อกหยุดแล้ว')
  result.update(outcome=outcome,message=message,remote_status=state,commit_locked=locked_commit,can_clear_lock=can_clear,
                can_install=not busy and not locked_commit and result['disk_sha256']==result['running_sha256'] and result['disk_sha256'] in known,
                can_restore=not busy and not locked_commit and result['running_sha256'] in known)
  if latest and not busy:
   latest.update(status=outcome,reconciled=result);save_report(exports,key,latest)
  return result

def tracked(action,exports_index,key_index):
 def decorate(fn):
  @functools.wraps(fn)
  def wrapped(*args,**kwargs):
   exports=args[exports_index];key=args[key_index]
   core.require(re.fullmatch('[0-9a-f]{32}',key),'รหัสงานบนรถไม่ถูกต้อง')
   report={'id':key,'action':action,'status':'PREPARING','phase':'เริ่มตรวจ','write_intent':False,'remote_path':BASE+'/'+key}
   CURRENT.report=report
   callback=kwargs.get('progress',args[key_index+1] if len(args)>key_index+1 else lambda m:None)
   def progress(message):
    report['phase']=message
    if message.startswith('แทนไฟล์'):report['write_intent']=True
    save_report(exports,key,report);callback(message)
   newargs=list(args[:key_index+1]);newargs.append(progress)
   try:
    save_report(exports,key,report);result=fn(*newargs)
    report.update(result);save_report(exports,key,report);return dict(report)
   except Exception as e:
    report.update(status='RESULT_UNKNOWN' if report['write_intent'] else 'FAILED_BEFORE_REPLACE',error=str(e))
    report['recovery']='ยังไม่ทราบผล กดตรวจผลล่าสุดก่อน ห้ามเขียนซ้ำอัตโนมัติ' if report['write_intent'] else 'หยุดก่อนแทนไฟล์ แก้สาเหตุแล้วสร้าง/ติดตั้งใหม่ได้ ตรวจการเชื่อมต่อก่อน'
    try:save_report(exports,key,report)
    except Exception:logging.exception('Could not save device failure journal')
    raise DeviceFailure(str(e)+' — '+report['recovery'],dict(report)) from e
   finally:CURRENT.report=None
  return wrapped
 return decorate

@tracked('install',1,2)
@locked
def install(folder,exports,key,progress=lambda m:None):
 folder=pathlib.Path(folder);manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
 candidate=(folder/'Launcher.theme.bin').read_bytes();core.require(core.sha(candidate)==manifest['candidate_sha256'],'ไฟล์ candidate เปลี่ยนหลัง build')
 old,t,entries=core.stock();r=core.read_resources(candidate,t)
 repl={e['path']:candidate[e['offset']:e['offset']+e['length']] for e in r if e['path'] in core.ALLOWED}
 core.verify(old,candidate,t,repl)
 # Verify patch metadata against the complete validated candidate, never trust JSON alone.
 reconstructed=bytearray(old)
 for patch in manifest['patches']:
  core.require(re.fullmatch(r'resource-[0-9]+\.patch',patch['file']),'ชื่อแพตช์ไม่ถูกต้อง')
  offset=patch['offset'];size=patch['bytes'];payload=(folder/patch['file']).read_bytes()
  core.require(type(offset) is int and type(size) is int and 0<=offset<offset+size<=len(old),'ช่วงแพตช์ไม่ถูกต้อง')
  core.require(offset%4096==size%4096==0 and len(payload)==size and core.sha(payload)==patch['sha256'],'แพตช์ไม่ตรง')
  core.require(candidate[offset:offset+size]==payload,'แพตช์ไม่ตรง candidate');reconstructed[offset:offset+size]=payload
 core.require(reconstructed==candidate,'แพตช์สร้าง candidate ไม่ครบ')
 report={'action':'install','status':'PREPARING','expected_sha256':core.sha(candidate),'vehicle_launcher_signals_or_reboot':False};save_report(exports,key,report)
 remote=BASE+'/'+key;next_file='/usr/bin/Launcher.studio-'+key+'.next'
 with Session() as s:
  before=evidence(s,progress);report['before']=before
  core.require(before['disk_sha256']==before['running_sha256'],'ไฟล์บนดิสก์กับ process ต่างกัน ตรวจผลล่าสุดก่อนติดตั้งซ้ำ ถ้าไฟล์ไม่ตรงชุดที่ตรวจไว้ให้คืนต้นฉบับก่อนเปิดใหม่')
  core.require(before['disk_sha256'] in accepted_hashes(exports,before['disk_sha256']),'Launcher รถไม่ตรงกับต้นฉบับหรือชุดที่รองรับ')
  core.require('aarch64' in s.run('uname -m'),'สถาปัตยกรรมรถไม่ตรงรุ่น')
  free=int(s.run("df -k /usr/bin | tail -n 1 | awk '{print $4}'"));core.require(free>400000,'พื้นที่ว่างบนรถไม่พอสำหรับสำรอง')
  boot_before=s.hash('/dev/mmcblk0p3');report['boot_before']=boot_before;save_report(exports,key,report)
  progress('สำรอง Launcher ปัจจุบันและตรวจต้นฉบับ')
  s.run(f'mkdir -p {remote} && cp -p /usr/bin/Launcher {remote}/Launcher.previous && sync',120)
  core.require(s.hash(remote+'/Launcher.previous')==before['disk_sha256'],'สำรองไฟล์ปัจจุบันไม่ตรง')
  stock_remote=BASE+'/Launcher.stock'
  if s.run(f'if test -f {stock_remote}; then echo FOUND; else echo MISSING; fi')=='MISSING':
   # First use on an untouched, verified dashboard does not require a
   # project-specific backup filename from the development vehicle.
   source='/usr/bin/Launcher' if before['disk_sha256']==core.STOCK_SHA else '/usr/bin/Launcher.codex.original'
   core.require(s.hash(source)==core.STOCK_SHA,'ไม่พบสำเนา Launcher ต้นฉบับที่ตรงรุ่นบนรถ')
   s.run(f'cp -p {source} {stock_remote} && sync',120)
  core.require(s.hash(stock_remote)==core.STOCK_SHA,'สำเนาต้นฉบับไม่ตรง')
  for patch in manifest['patches']:s.upload(folder/patch['file'],remote+'/'+patch['file'],progress)
  progress('สร้าง candidate ในไฟล์ชั่วคราว')
  s.run(f'test ! -e {next_file} && cp -p {stock_remote} {next_file}',120)
  for patch in manifest['patches']:
   s.run(f'dd if={remote}/{patch["file"]} of={next_file} bs=4096 seek={patch["offset"]//4096} count={patch["bytes"]//4096} conv=notrunc',120)
  expected=core.sha(candidate);core.require(s.hash(next_file)==expected,'candidate บนรถไม่ตรง หยุดก่อนแทนไฟล์')
  script=f'''#!/bin/sh
set -eu
BASE={remote}
printf '%s\\n' "$$" > "$BASE/worker.pid"
COMMIT_LOCK={BASE}/commit.lock
LOCKED=0
release_lock() {{ if [ "$LOCKED" = 1 ]; then rm -f "$COMMIT_LOCK/owner"; rmdir "$COMMIT_LOCK"; fi; }}
hash_file() {{ sha256sum "$1" | cut -d ' ' -f 1; }}
status() {{ printf '%s\\n' "$1" > "$BASE/status.next"; mv -f "$BASE/status.next" "$BASE/status.txt"; sync; }}
trap 'rc=$?; release_lock; if [ "$rc" != 0 ]; then status FAILED_$rc; fi' 0
exec >> "$BASE/install.log" 2>&1
status CHECKING
mkdir "$COMMIT_LOCK"
LOCKED=1
printf '%s %s %s\\n' "$$" {key} "$(cat /proc/sys/kernel/random/boot_id)" > "$COMMIT_LOCK/owner"
test "$(pidof Launcher)" = {before['pid']}
test "$(hash_file /usr/bin/Launcher)" = {before['disk_sha256']}
test "$(hash_file /proc/{before['pid']}/exe)" = {before['running_sha256']}
test "$(hash_file "$BASE/Launcher.previous")" = {before['disk_sha256']}
test "$(hash_file {next_file})" = {expected}
test -x {next_file}
sync
mv -f {next_file} /usr/bin/Launcher
sync
if [ "$(hash_file /usr/bin/Launcher)" != {expected} ]; then
 cp -p "$BASE/Launcher.previous" /usr/bin/Launcher.studio-restore.next
 test "$(hash_file /usr/bin/Launcher.studio-restore.next)" = {before['disk_sha256']}
 mv -f /usr/bin/Launcher.studio-restore.next /usr/bin/Launcher
 sync
 status HASH_FAILED_PREVIOUS_RESTORED
 release_lock
 trap - 0
 exit 1
fi
printf '%s\\n' {expected} > {BASE}/last-installed.sha256
status INSTALLED_VERIFIED
'''
  script_file=folder/('install-'+key+'.sh');script_file.write_text(script,encoding='ascii',newline='\n')
  s.upload(script_file,remote+'/install.sh');s.run('/bin/sh -n '+remote+'/install.sh')
  progress('แทนไฟล์แบบ atomic แล้วตรวจอ่านกลับ คงไฟรถไว้')
  s.run(f"nohup /bin/sh {remote}/install.sh </dev/null >{remote}/nohup.log 2>&1 & printf '%s\\n' DISPATCHED")
  deadline=time.monotonic()+180
  while time.monotonic()<deadline:
   state=s.run(f'if test -f {remote}/status.txt; then cat {remote}/status.txt; else echo STARTING; fi')
   report['remote_status']=state;save_report(exports,key,report)
   if state=='INSTALLED_VERIFIED':break
   core.require(not state.startswith(('FAILED','HASH_FAILED')),'ติดตั้งไม่ผ่าน ดู log บนรถ: '+state)
   time.sleep(2)
  else:raise TimeoutError('หมดเวลารอสถานะ ห้ามเขียนซ้ำจนตรวจผลบนรถ')
  after=evidence(s,progress);report['after']=after;report['boot_after']=s.hash('/dev/mmcblk0p3')
  core.require(after['disk_sha256']==expected,'แฮชหลังติดตั้งไม่ตรง')
  core.require(after['pid']==before['pid'] and after['running_sha256']==before['running_sha256'],'process จอเปลี่ยนระหว่างติดตั้ง')
  core.require(report['boot_after']==boot_before,'แฮชบูตเปลี่ยนระหว่างงาน')
  report['status']='INSTALLED_VERIFIED_AWAIT_NORMAL_POWER_CYCLE';save_report(exports,key,report)
  return report

@tracked('restore',0,1)
@locked
def restore(exports,key,progress=lambda m:None):
 with Session() as s:
  before=evidence(s,progress)
  # A restore is also allowed while the prior process still runs after an install.
  accepted=accepted_hashes(exports,before['disk_sha256'])|accepted_hashes(exports,before['running_sha256'])
  core.require(before['running_sha256'] in accepted,'process Launcher ไม่ตรงชุดที่รองรับ ต้องตรวจด้วยผู้เชี่ยวชาญก่อนคืนค่า')
  stock_remote=BASE+'/Launcher.stock'
  if s.run(f'if test -f {stock_remote}; then echo FOUND; else echo MISSING; fi')=='MISSING':stock_remote='/usr/bin/Launcher.codex.original'
  core.require(s.hash(stock_remote)==core.STOCK_SHA,'สำเนาต้นฉบับไม่ตรง')
  boot=s.hash('/dev/mmcblk0p3');save_report(exports,key,{'before':before,'expected_sha256':core.STOCK_SHA,'boot_before':boot});progress('ตรวจสำเนาและเตรียมคืน Launcher ต้นฉบับ')
  next_file='/usr/bin/Launcher.studio-restore-'+key+'.next'
  s.run(f'cp -p {stock_remote} {next_file} && sync',120);core.require(s.hash(next_file)==core.STOCK_SHA,'สำเนาคืนค่าไม่ตรง')
  progress('แทนไฟล์คืนค่าแบบ atomic แล้วตรวจอ่านกลับ คงไฟรถไว้')
  # Recheck current file at the final mutation boundary.
  restore_script=f"""set -e
trap 'rm -f {BASE}/commit.lock/owner; rmdir {BASE}/commit.lock' 0
printf '%s %s %s\\n' "$$" {key} "$(cat /proc/sys/kernel/random/boot_id)" > {BASE}/commit.lock/owner
test "$(pidof Launcher)" = {before['pid']}
test "$(sha256sum /proc/{before['pid']}/exe | cut -d ' ' -f 1)" = {before['running_sha256']}
test "$(sha256sum /usr/bin/Launcher | cut -d ' ' -f 1)" = {before['disk_sha256']}
mv -f {next_file} /usr/bin/Launcher
sync
"""
  s.run(f'mkdir -p {BASE} && mkdir {BASE}/commit.lock && /bin/sh -c '+shlex.quote(restore_script),120)
  core.require(s.hash('/usr/bin/Launcher')==core.STOCK_SHA,'แฮชหลังคืนค่าไม่ตรง')
  after=evidence(s,progress);core.require(after['pid']==before['pid'] and after['running_sha256']==before['running_sha256'],'process จอเปลี่ยนระหว่างคืนค่า')
  core.require(s.hash('/dev/mmcblk0p3')==boot,'แฮชบูตเปลี่ยน')
  report={'status':'STOCK_RESTORED_AWAIT_NORMAL_POWER_CYCLE','before':before,'after':after,'stock_sha256':core.STOCK_SHA,
          'boot_preserved':True,'launcher_signals_or_reboot':False}
  save_report(exports,key,report);return report
