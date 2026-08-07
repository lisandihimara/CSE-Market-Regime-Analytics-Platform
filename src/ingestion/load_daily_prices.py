"""
Load CSE daily share prices, 2021-2025.

Scope note
----------
CSE's price archives before 2021 use two other, structurally different
layouts (per-company header blocks for 2011-2020; a minimal 3-column
format for 1991-2000). This loader intentionally covers 2021-2025 only,
which is internally consistent AND spans the period of interest for
regime detection (COVID recovery -> 2022 sovereign default crisis ->
recovery). See README "Limitations" for the historical-format note.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from src.ingestion.excel_parser import read_cse_sheet, build_from_raw

RAW_ZIP = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Daily Shares Price List -2021-2025.zip"
)

# Standardized output schema (raw column names vary slightly by year)
COLUMN_MAP = {
    "COMPANY ID": "ticker",
    " MAIN TYPE ": "main_type",
    "SUB TYPE": "sub_type",
    " SHORT NAME ": "short_name",
    "TRADING DATE": "date",
    " PRICE HIGH (Rs.)": "high",
    " PRICE LOW (Rs.)": "low",
    "CLOSE PRICE (Rs.)": "close",
    "OPEN PRICE (Rs.)": "open",
    "TRADE VOLUME (No.) ": "trade_volume",
    "SHARE VOLUME (No.) ": "share_volume",
    "TURNOVER (Rs.)": "turnover",
}

NUMERIC_COLS = ["high", "low", "close", "open", "trade_volume", "share_volume", "turnover"]


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    # normalize whitespace in column names before mapping
    df.columns = [c if c in COLUMN_MAP else c.strip() for c in df.columns]
    rename_map = {k.strip(): v for k, v in COLUMN_MAP.items()}
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=rename_map)

    keep = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[keep].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ticker/type/name columns come back as mixed str/float across
    # different source years (e.g. sub_type "0000" vs 0) — force to
    # string so downstream serialization (parquet) doesn't choke.
    for col in ["ticker", "main_type", "sub_type", "short_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def _read_member(zf: zipfile.ZipFile, member: str) -> pd.DataFrame:
    raw_bytes = zf.read(member)
    if member.lower().endswith(".csv"):
        # CSVs have the same title-row-before-header quirk as the Excel
        # files, so route through the shared header-detection logic
        # instead of assuming header=0.
        raw = pd.read_csv(io.BytesIO(raw_bytes), header=None, low_memory=False)
        df = build_from_raw(raw)
    else:
        tmp = io.BytesIO(raw_bytes)
        df = read_cse_sheet(tmp, sheet_name=0)
    return df


def load_daily_prices_2021_2025(zip_path: Path = RAW_ZIP) -> pd.DataFrame:
    """Return one tidy DataFrame covering all years in the 2021-2025 archive."""
    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        for member in members:
            df = _read_member(zf, member)
            df = _standardize(df)
            df["source_file"] = Path(member).name
            frames.append(df)

    full = pd.concat(frames, ignore_index=True)
    full = full.dropna(subset=["date", "ticker"])
    full = full.sort_values(["ticker", "date"]).reset_index(drop=True)
    return full


if __name__ == "__main__":
    from src.utils.validation import (
        assert_not_empty, assert_no_nulls, assert_no_duplicates,
        assert_no_future_dates, report,
    )

    prices = load_daily_prices_2021_2025()

    assert_not_empty(prices, "daily_prices")
    assert_no_nulls(prices, ["date", "ticker"], "daily_prices")
    assert_no_duplicates(prices, ["ticker", "date", "main_type", "sub_type"], "daily_prices")
    assert_no_future_dates(prices, "date", "daily_prices")

    INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(INTERIM_DIR / "daily_prices_2021_2025.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    prices.to_csv(INTERIM_DIR / "daily_prices_2021_2025.csv", index=False)
    report(prices, "daily_prices", date_col="date")
