"""Offline integration tests. Transport is mocked; never connects to the vehicle."""
import io,json,pathlib,shlex,subprocess,tempfile,unittest,unittest.mock as mock
from PIL import Image
import core,device,server,journal

def preset():
 return {'parts':{k:{'enabled':True,'mode':'image' if k=='wallpaper' else 'tint','image':'example-wallpaper','color':'#afafaf','opacity':100 if k=='wallpaper' else 40 if k in ('left','right','glow') else 45,'fit':'cover','colors':0,'x':.5,'y':.5} for k in ('wallpaper','ring','left','right','gear','glow')}}
def image_loader(_):return core.asset_file('example-wallpaper.png').read_bytes()

@unittest.skipUnless((core.PRIVATE/'data/Launcher.original').is_file(),'Private verified firmware required; see prepare_private.py')
class EngineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temporary=tempfile.TemporaryDirectory();cls.root=pathlib.Path(cls.temporary.name);cls.folder=cls.root/'project-test'
  cls.manifest=core.build_theme(cls.folder,preset(),image_loader)
  cls.old,cls.tables,cls.entries=core.stock();cls.new=(cls.folder/'Launcher.theme.bin').read_bytes();cls.repl=core.replacements(preset(),image_loader)
 @classmethod
 def tearDownClass(cls):cls.temporary.cleanup()
 def test_theme_manifest_and_resource_counts(self):
  self.assertEqual(self.manifest['original_sha256'],core.STOCK_SHA)
  self.assertEqual(len(self.manifest['changed_resources']),10)
  self.assertEqual(self.manifest['unchanged_resources'],3066)
 def test_header_mutation_rejected(self):
  corrupt=bytearray(self.new);corrupt[16]^=1
  with self.assertRaises((ValueError,AssertionError)):core.verify(self.old,bytes(corrupt),self.tables,self.repl)
 def test_unselected_warning_payload_rejected(self):
  entries=core.read_resources(self.new,self.tables)
  icon=next(e for e in entries if e['path'].startswith('/res_sport/SPORT_NIGHT_ICON_') and e['flags']==0)
  corrupt=bytearray(self.new);corrupt[icon['offset']+10]^=1
  with self.assertRaises(ValueError):core.verify(self.old,bytes(corrupt),self.tables,self.repl)
 def test_only_selected_component_changes(self):
  config={'parts':{'left':{'enabled':True,'mode':'tint','color':'#274e7e','opacity':62}}}
  new,repl,groups,budgets,changes=core.prepare(config,image_loader)
  self.assertEqual([r['path'] for r in changes],core.PARTS['left']['paths'])
 def test_conversion_fits_and_transparency(self):
  source=Image.new('RGBA',(80,40),(255,0,0,255));raw=core.png(source)
  for fit in ('cover','contain','stretch'):
   result=core.convert_image(raw,[37,75],fit,colors=64);self.assertEqual(result.size,(37,75))
  original=Image.new('RGBA',(5,3),(4,5,6,0));original.putpixel((2,1),(50,100,150,80))
  transformed=core.decode(core.transform(core.png(original),{'mode':'image','opacity':50},raw))
  self.assertEqual(transformed.getpixel((0,0)),(4,5,6,0));self.assertEqual(transformed.getpixel((2,1))[3],40)
 def test_capacity_and_scope_guard(self):
  path=core.PARTS['wallpaper']['paths'][0]
  with self.assertRaisesRegex(ValueError,'พื้นที่'):core.pack(self.old,self.tables,self.entries,{path:b'x'*3_000_000})
  with self.assertRaises(ValueError):core.pack(self.old,self.tables,self.entries,{'/unknown':b'x'})
 def test_config_validation(self):
  for value in ({'parts':{'unknown':{}}},{'parts':{'ring':{'opacity':101}}},{'parts':{'ring':{'enabled':'yes'}}},{'parts':{'ring':{'x':float('nan')}}},{'parts':{'speed':{'opacity':50}}},{'parts':{'rpm_numbers':{'mode':'image'}}}):
   with self.assertRaises(ValueError):core.validate_config(value)
 def test_recolor_preserves_shapes_and_red_zone(self):
  config={'parts':{k:{'enabled':True,'mode':'tint','color':c,'opacity':100} for k,c in [('speed','#38bdf8'),('rpm_numbers','#b4ff60'),('rpm_accent','#a855f7')]}}
  new,repl,groups,budgets,changes=core.prepare(config,image_loader)
  self.assertEqual(len(changes),36)
  name='/res/Other/dark/sport/kedu.png';old_entry=next(e for e in self.entries if e['path']==name)
  src=core.decode(self.old[old_entry['offset']:old_entry['offset']+old_entry['length']]);out=core.decode(repl[name])
  pixels=list(src.get_flattened_data());red=next(i for i,p in enumerate(pixels) if p[3] and core.red_pixel(*p[:3]))
  x,y=red%src.width,red//src.width;self.assertEqual(out.getpixel((x,y)),src.getpixel((x,y)))
  for corruption in ('red','alpha'):
   bad=out.copy();r,g,b,a=bad.getpixel((x,y));bad.putpixel((x,y),(1,2,3,a) if corruption=='red' else (r,g,b,0));modified={**repl,name:core.png(bad)}
   candidate,_,_=core.pack(self.old,self.tables,self.entries,modified)
   with self.assertRaises(ValueError):core.verify(self.old,candidate,self.tables,modified)
 def test_atomic_project_write_and_interrupted_job_recovery(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);file=root/'project.json';journal.write_json(file,{'parts':{}})
   with mock.patch.object(journal.os,'replace',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):journal.write_json(file,{'parts':{'left':{}}})
   self.assertEqual(json.loads(file.read_text())['parts'],{});self.assertEqual(list(root.glob('*.tmp')),[])
   journal.write_json(root/'jobs.json',{'job':{'id':'job','kind':'device-install','status':'running'}})
   file.write_text('{broken',encoding='utf-8');studio=server.Studio(root,root/'exports')
   self.assertEqual(studio.jobs['job']['status'],'interrupted')
   with self.assertLogs(level='ERROR'):self.assertIsNone(studio.project())
   self.assertTrue(list(root.glob('project-unreadable-*.json')))
 def test_single_instance_lock(self):
  with tempfile.TemporaryDirectory() as directory:
   first=server.instance_lock(directory)
   try:self.assertIsNone(server.instance_lock(directory))
   finally:first.close()
   second=server.instance_lock(directory);self.assertIsNotNone(second);second.close()
 def test_abandoned_lock_requires_dead_owner(self):
  class Fake:
   alive=True;commands=[]
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def hash(self,path):return core.STOCK_SHA
   def run(self,cmd,timeout=90):
    self.commands.append(cmd)
    if cmd=='pidof Launcher':return '1341'
    if cmd=='cat /proc/uptime':return '12 12'
    if 'commit.lock/owner; then cat' in cmd:return '333 '+'a'*32+' '+'b'*8+'-'+('b'*4+'-')*3+'b'*12
    if cmd=='cat /proc/sys/kernel/random/boot_id':return 'b'*8+'-'+('b'*4+'-')*3+'b'*12
    if 'test -d /proc/333' in cmd:return 'ALIVE' if self.alive else 'EXITED'
    return ''
  with mock.patch.object(device,'Session',Fake):
   with self.assertRaises(ValueError):device.clear_commit_lock(self.root,'3'*32)
   self.assertFalse(any('&& rm ' in c for c in Fake.commands))
   Fake.alive=False;result=device.clear_commit_lock(self.root,'4'*32)
   self.assertTrue(result['launcher_unchanged']);self.assertTrue(any('&& rm ' in c for c in Fake.commands))
 def test_device_mocks_install_restore_and_preconditions(self):
  test=self
  class FakeSession:
   disk=core.STOCK_SHA;running=core.STOCK_SHA;stock=core.STOCK_SHA;commands=[];files={};uploads={};entered=0;missing_stock=True
   def __enter__(self):self.__class__.entered+=1;return self
   def __exit__(self,*a):pass
   def hash(self,path):
    if path=='/usr/bin/Launcher':return self.disk
    if path=='/proc/1341/exe':return self.running
    if path=='/dev/mmcblk0p3':return 'b'*64
    if path in (device.BASE+'/Launcher.stock','/usr/bin/Launcher.codex.original'):return self.stock
    return self.files[path]
   def upload(self,local,remote,progress=lambda s:None):
    raw=pathlib.Path(local).read_bytes();self.files[remote]=core.sha(raw);self.uploads[remote]=raw
   def run(self,cmd,timeout=90):
    cls=self.__class__;cls.commands.append(cmd)
    if cmd=='pidof Launcher':return '1341'
    if cmd=='cat /proc/uptime':return '500.00 499.99'
    if cmd=='uname -m':return 'aarch64'
    if cmd.startswith('df -k'):return '1200000'
    if cmd.startswith('if test -f'):
     if 'status.txt' in cmd:return 'INSTALLED_VERIFIED'
     if cmd.startswith('if test -f '+device.BASE+'/Launcher.stock'):return 'MISSING' if cls.missing_stock else 'FOUND'
     return 'FOUND'
    if cmd.startswith('cp -p /usr/bin/Launcher '+device.BASE+'/Launcher.stock'):cls.missing_stock=False;return ''
    if 'Launcher.previous' in cmd and cmd.startswith('mkdir'):cls.files[cmd.split('cp -p /usr/bin/Launcher ')[1].split(' ')[0]]=cls.disk;return ''
    if 'cp -p '+device.BASE+'/Launcher.stock' in cmd:
     target=cmd.split('cp -p '+device.BASE+'/Launcher.stock ')[1].split(' ')[0];cls.files[target]=cls.stock
    if cmd.startswith('dd '):cls.files[cmd.split('of=')[1].split(' ')[0]]=test.manifest['candidate_sha256'];return ''
    if cmd.startswith('nohup '):cls.disk=test.manifest['candidate_sha256'];return 'DISPATCHED'
    if 'mv -f ' in cmd and '/usr/bin/Launcher &&' not in cmd and 'commit.lock && /bin/sh -c' in cmd:cls.disk=core.STOCK_SHA
    return ''
  with mock.patch.object(device,'Session',FakeSession):
   report=device.install(self.folder,self.root,'a'*32)
   self.assertEqual(report['status'],'INSTALLED_VERIFIED_AWAIT_NORMAL_POWER_CYCLE')
   self.assertEqual(FakeSession.disk,self.manifest['candidate_sha256']);self.assertEqual(FakeSession.running,core.STOCK_SHA)
   self.assertTrue(any(c.startswith('cp -p /usr/bin/Launcher '+device.BASE+'/Launcher.stock') for c in FakeSession.commands))
   report=device.restore(self.root,'b'*32)  # Immediate undo before normal power cycle.
   self.assertTrue(report['boot_preserved']);self.assertEqual(FakeSession.disk,core.STOCK_SHA)
   commands='\n'.join(FakeSession.commands)
   if pathlib.Path('C:/Program Files/Git/bin/bash.exe').is_file():
    restore_command=next(c for c in FakeSession.commands if 'commit.lock && /bin/sh -c' in c)
    subprocess.run(['C:/Program Files/Git/bin/bash.exe','-n','-c',restore_command],check=True,capture_output=True)
    subprocess.run(['C:/Program Files/Git/bin/bash.exe','-n','-c',shlex.split(restore_command)[-1]],check=True,capture_output=True)
   self.assertNotIn('kill',commands);self.assertNotIn('reboot',commands)
   self.assertNotIn('of=/dev/',commands)
   script=next(raw for name,raw in FakeSession.uploads.items() if name.endswith('/install.sh')).decode()
   for fragment in ('test "$(pidof Launcher)"','test -x ','Launcher.previous','mv -f ','INSTALLED_VERIFIED'):
    self.assertIn(fragment,script)
   (self.root/'generated-install.sh').write_text(script,encoding='ascii')
   bash=pathlib.Path('C:/Program Files/Git/bin/bash.exe')
   if bash.is_file():subprocess.run([str(bash),'-n',str(self.root/'generated-install.sh')],check=True,capture_output=True)
   FakeSession.disk=FakeSession.running='f'*64;FakeSession.commands=[]
   with self.assertRaisesRegex(ValueError,'ไม่ตรง'):device.install(self.folder,self.root,'c'*32)
   self.assertFalse(any('cp -p' in c or c.startswith('dd ') for c in FakeSession.commands))
   FakeSession.disk=FakeSession.running=core.STOCK_SHA;FakeSession.stock='a'*64;FakeSession.commands=[]
   with self.assertRaisesRegex(ValueError,'ไม่ตรง'):device.restore(self.root,'d'*32)
   self.assertFalse(any('mv -f' in c for c in FakeSession.commands))
   device.LOCK.acquire()
   try:
    entered=FakeSession.entered
    with self.assertRaisesRegex(ValueError,'กำลังทำ'):device.check()
    self.assertEqual(FakeSession.entered,entered)
   finally:device.LOCK.release()
   FakeSession.disk='f'*64;FakeSession.running=core.STOCK_SHA;FakeSession.stock=core.STOCK_SHA
   repaired=device.restore(self.root,'e'*32);self.assertEqual(repaired['status'],'STOCK_RESTORED_AWAIT_NORMAL_POWER_CYCLE')
   FakeSession.disk=FakeSession.running=core.STOCK_SHA
   class DropBeforeReplace(FakeSession):
    def upload(self,*args,**kwargs):raise ConnectionError('Wi-Fi lost during upload')
   with mock.patch.object(device,'Session',DropBeforeReplace):
    with self.assertRaises(device.DeviceFailure) as err:device.install(self.folder,self.root,'1'*32)
    self.assertEqual(err.exception.details['status'],'FAILED_BEFORE_REPLACE')
    self.assertFalse(err.exception.details['write_intent'])
   class DropAfterDispatch(FakeSession):
    def run(self,cmd,timeout=90):
     result=super().run(cmd,timeout)
     if cmd.startswith('nohup '):raise ConnectionError('Connection lost after dispatch')
     return result
   with mock.patch.object(device,'Session',DropAfterDispatch):
    with self.assertRaises(device.DeviceFailure) as err:device.install(self.folder,self.root,'2'*32)
    self.assertEqual(err.exception.details['status'],'RESULT_UNKNOWN');self.assertTrue(err.exception.details['write_intent'])
   FakeSession.disk=self.manifest['candidate_sha256'];FakeSession.running=core.STOCK_SHA
   FakeSession.commands=[];resolved=device.reconcile(self.root)
   self.assertEqual(resolved['outcome'],'VERIFIED_ON_RECONNECT');self.assertTrue(resolved['can_restore']);self.assertFalse(resolved['can_install'])
   self.assertFalse(any('mv -f' in c or 'cp -p' in c or c.startswith('nohup') for c in FakeSession.commands))
   class StillRunning(FakeSession):
    def run(self,cmd,timeout=90):
     if '/worker.pid' in cmd:return '999'
     if '/proc/999/cmdline' in cmd:return device.BASE+'/'+'2'*32+'/install.sh'
     return super().run(cmd,timeout)
   with mock.patch.object(device,'Session',StillRunning):
    pending=device.reconcile(self.root);self.assertEqual(pending['outcome'],'REMOTE_JOB_RUNNING');self.assertFalse(pending['can_restore']);self.assertFalse(pending['can_install'])

if __name__=='__main__':unittest.main(verbosity=2)
