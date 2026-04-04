
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

def run(cmd):
    subprocess.run(cmd, check=True)

def main():
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    pip = VENV / "bin" / "pip"
    run([str(pip), "install", "-e", str(ROOT)])

    run([str(VENV / "bin" / "homelabctl"), "bootstrap-host"])

if __name__ == "__main__":
    main()
