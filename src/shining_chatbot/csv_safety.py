"""Safety helpers for values exported to spreadsheet-compatible CSV files."""

from __future__ import annotations


_FORMULA_PREFIXES = {"=", "+", "-", "@"}
_LEADING_NONCONTENT = {"\x00", "\ufeff"}


def safe_spreadsheet_cell(value: object) -> object:
    """Prefix text that spreadsheet apps could interpret as an executable formula."""
    if not isinstance(value, str):
        return value
    text = str(value)
    first = next(
        (character for character in text if not character.isspace() and character not in _LEADING_NONCONTENT),
        "",
    )
    return f"'{text}" if first in _FORMULA_PREFIXES else text
