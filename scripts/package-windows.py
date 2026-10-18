"""Assemble a clean Windows x64 distribution, without copying a user environment."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
ASSETS = ('doclayout_yolo_docstructbench_imgsz1024.onnx', 'SourceHanSerifKR-Regular.ttf')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--name',default='PaperStudyTranslator-0.1.0-windows-x64')
    args=parser.parse_args()
    if sys.version_info[:2] != (3,12): raise SystemExit('Build with Python 3.12 x64.')
    if Path(args.name).name != args.name: raise SystemExit('name must be a directory name')
    for p in [args.exe, *(args.assets / n for n in ASSETS)]:
        if not p.is_file(): raise SystemExit(f'Missing required input: {p}')
    dest=ROOT/'release'/args.name
    dest.mkdir(parents=True,exist_ok=False)
    py=dest/'runtime/python'; py.mkdir(parents=True)
    cache=ROOT/'.release-work/downloads'; cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'python-3.12.10-embed-amd64.zip'
    if not archive.exists(): urllib.request.urlretrieve(PYTHON_URL,archive)
    with zipfile.ZipFile(archive) as z: z.extractall(py)
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',
        '--only-binary=:all:','--no-binary=kiwipiepy-model','--no-compile','--target',str(py/'Lib/site-packages'),
        '-r',str(ROOT/'requirements-windows.lock.txt')],check=True)
    # pip's optional command launchers embed the build interpreter's absolute
    # path. The application uses Python modules directly, so omit those launchers.
    for name in ('bin','Scripts'):
        launchers=(py/'Lib/site-packages'/name).resolve()
        if launchers.is_relative_to(dest.resolve()) and launchers.is_dir():
            shutil.rmtree(launchers)
    (py/'python312._pth').write_text('\n'.join([
        'python312.zip','.','Lib/site-packages','../../services/scholar-translator',
        '../../services/translator-core/src','../../services/agent-adapters/src',
        '../../services/mixed-renderer','import site','']),encoding='utf-8')
    def ignore(directory,names):
        return [n for n in names if n in {'__pycache__','.pytest_cache','tests'}
                or n.endswith(('.pyc','.pyo','.egg-info')) or n.startswith('test_')]
    for name in ('scholar-translator','translator-core','agent-adapters','mixed-renderer'):
        shutil.copytree(ROOT/'services'/name,dest/'services'/name,ignore=ignore)
    shutil.copytree(ROOT/'knowledge-base',dest/'knowledge-base')
    shutil.copytree(ROOT/'licenses',dest/'licenses')
    shutil.copytree(ROOT/'docs',dest/'docs')
    assets=dest/'runtime/assets';assets.mkdir()
    for name in ASSETS: shutil.copy2(args.assets/name,assets/name)
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,dest/name)
    (dest/'scripts').mkdir()
    shutil.copy2(ROOT/'scripts/runtime-check.py',dest/'scripts/runtime-check.py')
    shutil.copy2(args.exe,dest/'PaperStudyTranslator.exe')
    (dest/'Check-Runtime.cmd').write_text('@echo off\r\nstart /wait "" "%~dp0PaperStudyTranslator.exe" --check-runtime "%TEMP%\\PaperStudyTranslator-check.json"\r\ntype "%TEMP%\\PaperStudyTranslator-check.json"\r\npause\r\n',encoding='ascii')
    (dest/'build-info.json').write_text(json.dumps({'version':'0.1.0','python_url':PYTHON_URL,
        'python_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'requirements_sha256':hashlib.sha256((ROOT/'requirements-windows.lock.txt').read_bytes()).hexdigest()},indent=2)+'\n')
    print(f'Package prepared: {dest}',flush=True)

if __name__=='__main__': main()
