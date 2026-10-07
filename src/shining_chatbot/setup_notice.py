"""Build local setup guidance when the external SANUP-P checkout is incomplete."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def missing_setup_notice(root: Path, missing: Sequence[str]) -> str:
    """Describe how to configure SANUP-P and list missing relative paths."""
    powershell_prefix = chr(36) + "env:SANUP_P_ROOT = 'C:/SANUP-P'"
    return "\n".join((
        "SANUP-P 체크아웃의 절대 경로를 SANUP_P_ROOT에 설정한 뒤 앱을 다시 시작하세요.",
        "Linux/WSL: export SANUP_P_ROOT=/path/to/SANUP-P",
        f"Windows PowerShell: {powershell_prefix}",
        f"현재 SANUP_P_ROOT: {root}",
        "누락된 필수 파일:",
        *(f"- {path}" for path in missing),
    ))
