"""Check tracked publication files; report paths/categories without secret values."""
import pathlib,re,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
patterns={
 'GitHub token':rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',
 'AWS access key':rb'AKIA[A-Z0-9]{16}',
 'Google API key':rb'AIza[0-9A-Za-z_-]{35}',
 'Private key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'Local session token':rb'https?://127\.0\.0\.1:[0-9]+/\?token=[A-Za-z0-9_-]{20,}',
}
blocked={'.img','.fex','.bin','.exe','.zip','.ttf','.otf','.original','.log'}
errors=[]
for name in filter(None,names):
 path=root/name;raw=path.read_bytes();parts=pathlib.PurePosixPath(name).parts
 if path.suffix.lower() in blocked or parts[0] in ('data','private','exports','outputs','logs','.venv','dist','build') or path.name in ('session.json','jobs.json','project.json'):
  errors.append((name,'Private/generated file type'))
 if len(raw)>5*1024*1024:errors.append((name,'Unexpected large file'))
 if raw.startswith(b'\x7fELF') or raw.startswith(b'ANDROID!'):errors.append((name,'Vehicle firmware header'))
 for label,pattern in patterns.items():
  if re.search(pattern,raw):errors.append((name,label))
 if re.search(rb'[A-Z]:[\\/]Users[\\/][A-Za-z0-9_. -]+[\\/]',raw):errors.append((name,'Personal absolute path'))
for name,label in errors:print(name+': '+label)
if errors:sys.exit(1)
print('Public tracked-file checks passed:',len(list(filter(None,names))),'files')
