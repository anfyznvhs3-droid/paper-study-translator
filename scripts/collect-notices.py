"""Collect original dependency license notices after npm ci / Cargo fetch."""
from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def collect():
    metadata=json.loads(subprocess.check_output(['cargo','metadata','--locked','--offline',
        '--format-version','1','--filter-platform','x86_64-pc-windows-msvc'],cwd=ROOT/'apps/desktop/src-tauri'))
    entries=[]
    for package in metadata['packages']:
        if not package.get('source'):continue
        entries.append(('rust',package['name'],package['version'],
            Path(package['manifest_path']).parent,package.get('license') or 'See original notice',package.get('repository') or ''))
    modules=ROOT/'apps/desktop/node_modules'
    for p in modules.glob('**/package.json'):
        if any(x in {'test','tests','fixtures'} for x in p.relative_to(modules).parts):continue
        try:package=json.loads(p.read_text(encoding='utf-8'))
        except (ValueError,UnicodeError):continue
        if not package.get('name') or not package.get('version'):continue
        repository=package.get('repository','')
        if isinstance(repository,dict):repository=repository.get('url','')
        entries.append(('javascript',package['name'],package['version'],p.parent,
            str(package.get('license','See original notice')),repository))
    index=['# Dependency licenses','',
        'Original license notices collected from the locked build dependencies.',
        'Build-only and platform-specific dependencies may also be listed.',
        'Python wheel notices are retained in the release runtime site-packages.',
        '', '| Ecosystem | Package | License | Source |','| --- | --- | --- | --- |']
    count=0
    for ecosystem,name,version,directory,license,repository in sorted(set(entries)):
        slug=(name+'-'+version).replace('/','__').replace('@','')
        folder=ROOT/'licenses/dependencies'/ecosystem/slug
        for p in directory.iterdir():
            if p.is_file() and p.name.upper().startswith(('LICENSE','LICENCE','COPYING','NOTICE','COPYRIGHT')):
                folder.mkdir(parents=True,exist_ok=True)
                (folder/p.name).write_bytes(p.read_bytes());count+=1
        index.append(f'| {ecosystem} | {name} {version} | {license} | {repository} |')
    (ROOT/'licenses/DEPENDENCIES.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    print(f'Collected {count} original notices from {len(entries)} dependency records.')

if __name__=='__main__':collect()
