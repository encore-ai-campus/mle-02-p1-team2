"""Resolve SANUP-P paths without importing the Streamlit application."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


DEFAULT_SANUP_P_ROOT = Path(r"C:\SANUP-P")

_REQUIRED_EXTERNAL_FILES = (
    "src/retriever.py",
    "src/rag_chain.py",
    "data/personal/corpus/chunks.jsonl",
    "data/personal/corpus/index_meta.json",
    "data/personal/corpus/index_meta_semantic.json",
    "chroma_db/personal/chroma.sqlite3",
)


def resolve_sanup_root(environ: Mapping[str, str] | None = None) -> Path:
    """Return SANUP_P_ROOT when set, retaining the historical Windows default."""
    values = os.environ if environ is None else environ
    configured = values.get("SANUP_P_ROOT", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_SANUP_P_ROOT


def sanup_python_path(root: Path, *, windows: bool | None = None) -> Path:
    """Return the external repository's venv interpreter for this platform."""
    use_windows_layout = os.name == "nt" if windows is None else windows
    venv = Path(root) / ".venv"
    if use_windows_layout:
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def required_sanup_paths(root: Path, *, windows: bool | None = None) -> tuple[Path, ...]:
    """List the interpreter and external files required by the RAG bridge."""
    root = Path(root)
    return (
        sanup_python_path(root, windows=windows),
        *(root / path for path in _REQUIRED_EXTERNAL_FILES),
    )


def missing_sanup_files(root: Path, *, windows: bool | None = None) -> list[str]:
    """Return missing paths relative to the configured SANUP-P root."""
    root = Path(root)
    return [
        path.relative_to(root).as_posix()
        for path in required_sanup_paths(root, windows=windows)
        if not path.is_file()
    ]


def sanup_bridge_command(root: Path, bridge: Path, *, windows: bool | None = None) -> list[str]:
    """Build the bridge command using the same interpreter checked at startup."""
    root = Path(root)
    return [
        str(sanup_python_path(root, windows=windows)),
        "-X",
        "utf8",
        str(bridge),
        str(root),
    ]
