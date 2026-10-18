"""Audit Git's public source selection without printing credential values."""
from pathlib import Path
import json
import re
import subprocess
from native_privacy import PATH_RULES

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_PARTS={'.qdt-home','.release-work','.venv','node_modules','target','dist','release',
               '.claude','.codex','.agents','.codex-sessions','review-history','QDT_Output'}
PRIVATE_NAMES={'engine-settings.json','review-session.json','auth.json','settings.local.json'}
RULES={
    'Google API key':rb'AIza[0-9A-Za-z_-]{35}',
    'provider secret':rb'\bsk-(?:proj-|ant-)[A-Za-z0-9_-]{20,}',
    'GitHub token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
    'AWS access key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'developer home path':rb'(?i)[C-Z]:[\\/]+(?:Users[\\/]+(?!Public\b|Default\b)[^\\/\s]+|OneDrive[\\/])',
    'absolute Rust source path':PATH_RULES['absolute Rust source path'].pattern.encode(),
    'build cache path':PATH_RULES['build cache path'].pattern.encode(),
}

def main():
    output=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
    paths=sorted(set(p.decode('utf-8') for p in output.split(b'\0') if p))
    findings=[]
    for relative in paths:
        path=Path(relative)
        if any(p in PRIVATE_PARTS for p in path.parts) or path.name in PRIVATE_NAMES or path.name.startswith('.env') or path.suffix.lower() in {'.log','.stdout','.stderr','.db','.sqlite','.pdf','.exe','.zip','.pdb'}:
            findings.append({'path':relative,'rule':'private/generated file'})
        content=(ROOT/path).read_bytes()
        # This scanner contains the descriptions of the patterns, not secrets.
        for name,pattern in RULES.items():
            for match in re.finditer(pattern,content):
                findings.append({'path':relative,'rule':name,'line':content[:match.start()].count(b'\n')+1})
    print(json.dumps({'ok':not findings,'files':len(paths),'findings':findings},ensure_ascii=False,indent=2))
    return bool(findings)

if __name__=='__main__':raise SystemExit(main())
