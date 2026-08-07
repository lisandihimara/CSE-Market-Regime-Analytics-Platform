"""
Generic reader for CSE's messy Excel exports.

Every CSE statistics file shares the same quirks:
  - 2-4 blank / title rows before the real header
  - Header row detection isn't fixed (varies file to file)
  - Known garbage strings sitting in numeric columns
    (e.g. "Market Closed Due To COVID -19", "-", "n/a")
  - Multiple sheets, sometimes one sheet per year

This module centralizes that handling so every loader in
src/ingestion/ can reuse the same logic instead of re-solving
header detection per file.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

# Strings CSE uses in place of a real numeric value.
KNOWN_NA_TOKENS = {
    "-", "n/a", "na", "nil", "", " ",
    "market closed due to covid -19",
    "market closed due to covid-19",
}


def _looks_like_header_row(row: pd.Series, min_non_null: int = 2) -> bool:
    """Heuristic: a header row has several short, non-numeric string cells."""
    non_null = row.dropna()
    if len(non_null) < min_non_null:
        return False
    text_like = non_null.apply(
        lambda v: isinstance(v, str) and not re.fullmatch(r"[\d.,\-\s]+", v)
    )
    return text_like.sum() >= min_non_null


def find_header_row(raw: pd.DataFrame, search_rows: int = 10) -> int:
    """
    Scan the first `search_rows` rows of a header-less read and return
    the index most likely to be the real column header row.
    """
    best_idx, best_score = 0, -1
    for i in range(min(search_rows, len(raw))):
        row = raw.iloc[i]
        score = row.notna().sum()
        if _looks_like_header_row(row) and score > best_score:
            best_idx, best_score = i, score
    return best_idx


def clean_token(val):
    """Normalize known CSE 'not a number' tokens to actual NaN."""
    if isinstance(val, str):
        if val.strip().lower() in KNOWN_NA_TOKENS:
            return pd.NA
    return val


def read_cse_sheet(
    path,
    sheet_name: str | int = 0,
    header_row: Optional[int] = None,
    apply_na_cleanup: bool = True,
) -> pd.DataFrame:
    """
    Read one sheet from a CSE Excel export with automatic header detection.

    Parameters
    ----------
    path : file path (str/Path) OR an in-memory buffer (e.g. io.BytesIO)
    sheet_name : sheet name or index
    header_row : force a specific header row index; if None, auto-detect
    apply_na_cleanup : replace known garbage tokens with NaN
    """
    if isinstance(path, (str, Path)):
        path = Path(path)
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)

    if header_row is None:
        header_row = find_header_row(raw)

    header = raw.iloc[header_row]
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [
        str(c).strip() if pd.notna(c) else f"col_{i}"
        for i, c in enumerate(header)
    ]
    df = df.dropna(how="all").reset_index(drop=True)

    if apply_na_cleanup:
        df = df.map(clean_token)

    return df


def build_from_raw(raw: pd.DataFrame, header_row: Optional[int] = None,
                    apply_na_cleanup: bool = True) -> pd.DataFrame:
    """
    Same header-detection + cleanup logic as read_cse_sheet, but starting
    from an already-loaded header-less DataFrame. Lets CSV and Excel
    sources share one code path.
    """
    if header_row is None:
        header_row = find_header_row(raw)

    header = raw.iloc[header_row]
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [
        str(c).strip() if pd.notna(c) else f"col_{i}"
        for i, c in enumerate(header)
    ]
    df = df.dropna(how="all").reset_index(drop=True)

    if apply_na_cleanup:
        df = df.map(clean_token)

    return df


def read_cse_all_sheets(
    path: str | Path,
    header_row: Optional[int] = None,
) -> dict[str, pd.DataFrame]:
    """Read every sheet in a CSE workbook (used for files split by year)."""
    xl = pd.ExcelFile(path)
    return {
        sheet: read_cse_sheet(path, sheet_name=sheet, header_row=header_row)
        for sheet in xl.sheet_names
    }
