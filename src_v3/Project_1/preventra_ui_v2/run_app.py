"""Optional launcher with an isolated official theme. Direct entry also works."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    package = Path(__file__).resolve().parent
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(package.parent / "preventra_plus.py"),
        "--server.headless=true",
        "--browser.gatherUsageStats=false", *sys.argv[1:],
    ], cwd=package / "theme", check=True)
