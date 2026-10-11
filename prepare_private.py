"""Prepare a user-owned, fingerprinted backup locally. No vehicle connection."""
import argparse, hashlib, os, pathlib, tempfile, zlib
import core, boot_lab
from journal import write_json

def atomic_bytes(path, data):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def prepare(launcher, boot=None, destination=None):
    target=pathlib.Path(destination or core.PRIVATE).expanduser().resolve()
    if target.is_relative_to(core.BASE):raise ValueError('Private bundle must be outside this repository')
    raw=pathlib.Path(launcher).read_bytes()
    core.require(core.sha(raw)==core.STOCK_SHA,'Launcher SHA-256 does not match the supported firmware; nothing imported')
    tables=core.tables_from_elf(raw);entries=core.read_resources(raw,tables)
    core.require(len(entries)==3076,'Unexpected resource count')
    boot_bytes=None
    if boot:
        boot_bytes=pathlib.Path(boot).read_bytes()
        core.require(core.sha(boot_bytes)==boot_lab.STOCK_SHA256,'Boot SHA-256 does not match; nothing imported')
    assets={}
    for e in entries:
        name=e['path'].lstrip('/')
        if not (name.startswith('res_sport/') or name.startswith('res/Other/dark/sport/') or name=='res/fonts/Plagiata-Regular.ttf'):continue
        path=(target/'assets'/name).resolve()
        core.require(path.is_relative_to(target/'assets'),'Invalid resource path')
        payload=raw[e['offset']:e['offset']+e['length']]
        core.require(e['flags'] in (0,1),'Unsupported resource compression')
        if e['flags']==1:payload=zlib.decompress(payload[4:])
        core.require(len(payload)<=32*1024*1024,'Resource too large')
        assets[name]=payload
    core.require(all(n.lstrip('/') in assets for n in core.ALLOWED),'Selected components missing')
    target.mkdir(parents=True,exist_ok=True)
    marker=target/'ready.json'
    # An interrupted import is never treated as a complete setup.
    marker.unlink(missing_ok=True)
    atomic_bytes(target/'data/Launcher.original',raw)
    if boot_bytes is not None:atomic_bytes(target/'data/boot.original.img',boot_bytes)
    for name,payload in assets.items():atomic_bytes(target/'assets'/name,payload)
    write_json(marker,{'launcher_sha256':core.sha(raw),'resources':len(entries),'assets':len(assets)})
    return {'directory':str(target),'assets':len(assets),'boot_imported':boot_bytes is not None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher',required=True,help='Your original Launcher backup; never a modified Launcher')
    parser.add_argument('--boot',help='Optional original boot partition backup')
    parser.add_argument('--private-dir',help='External folder; also set STUDIO_PRIVATE_DIR when running the app')
    args=parser.parse_args()
    result=prepare(args.launcher,args.boot,args.private_dir)
    print('Private bundle prepared:',result['directory']);print('Local extracted assets:',result['assets']);print('Boot imported:',result['boot_imported'])
if __name__=='__main__':main()
