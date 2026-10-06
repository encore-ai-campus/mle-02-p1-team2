"""Optional launcher with an isolated official theme. Direct entry also works."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    package = Path(__file__).resolve().parent
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(package.parent / "Preventra_v2.py"),
        "--server.headless=true", "--server.address=127.0.0.1", "--server.port=8515",
        "--browser.gatherUsageStats=false", *sys.argv[1:],
    ], cwd=package / "theme", check=True)
