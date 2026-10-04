"""Use the repository's canonical services without copying their implementation."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[3] / "apps" / "accident_assistant" / "services")]
