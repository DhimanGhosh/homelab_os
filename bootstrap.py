#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'

def run(cmd):
    subprocess.run(cmd, check=True)

if not VENV.exists():
    run([sys.executable, '-m', 'venv', str(VENV)])
py = VENV / 'bin' / 'python'
pip = VENV / 'bin' / 'pip'
run([str(py), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'])
run([str(pip), 'install', '-e', str(ROOT)])
if (ROOT / '.env.example').exists() and not (ROOT / '.env').exists():
    (ROOT / '.env').write_text((ROOT / '.env.example').read_text(encoding='utf-8'), encoding='utf-8')
print('Bootstrap completed.')
