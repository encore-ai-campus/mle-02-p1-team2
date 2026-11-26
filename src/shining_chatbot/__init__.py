"""Command line entry point for the Streamlit app."""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    app_path = Path(__file__).with_name("app.py")
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path)])
    )
