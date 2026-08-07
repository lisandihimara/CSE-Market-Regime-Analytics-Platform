"""
Load CSE dividend announcements, 2021-2025 (matches the daily price
data coverage used for the event study).

Ticker is parsed from the SECURITY field (e.g. "AEL-N-0000" -> "AEL")
to join against load_daily_prices.py's `ticker` column.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.excel_parser import read_cse_sheet

RAW_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Dividends.xls"
)

YEARS = ["2021", "2022", "2023", "2024", "2025"]

COLUMN_MAP = {
    "DATE OF ANNOUNCEMENT": "date_announced",
    "SECURITY": "security_id",
    "SHORT NAME": "short_name",
    "RATE OF DIVIDEND": "dividend_rate",
    "DATE OF EX": "date_ex",
    "DATE OF PAYMENT": "date_payment",
    "CUM PRICE": "cum_price",
    "EX PRICE": "ex_price",
}


def load_dividends(path: Path = RAW_PATH, years: list[str] = YEARS) -> pd.DataFrame:
    frames = []
    for year in years:
        try:
            df = read_cse_sheet(path, sheet_name=year, apply_na_cleanup=True)
        except Exception:
            continue
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns=COLUMN_MAP)
        keep = [c for c in COLUMN_MAP.values() if c in df.columns]
        if "security_id" not in df.columns:
            continue
        df = df[keep].copy()
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=list(COLUMN_MAP.values()) + ["ticker"])

    full = pd.concat(frames, ignore_index=True)
    full = full.dropna(subset=["security_id"])
    full["ticker"] = full["security_id"].astype(str).str.split("-").str[0].str.strip()

    for col in ["date_announced", "date_ex", "date_payment"]:
        if col in full.columns:
            full[col] = pd.to_datetime(full[col], errors="coerce")
    for col in ["dividend_rate", "cum_price", "ex_price"]:
        if col in full.columns:
            full[col] = pd.to_numeric(full[col], errors="coerce")

    full = full.dropna(subset=["date_ex", "ticker"])
    return full.reset_index(drop=True)


if __name__ == "__main__":
    from src.utils.validation import assert_not_empty, assert_no_nulls, report

    div = load_dividends()

    # Not persisted to data/interim/: unlike the other loaders, dividends
    # are read live by src/features/event_study.py via load_dividends()
    # rather than from a saved parquet, so there's no interim file for
    # this one by design.
    assert_not_empty(div, "dividends")
    assert_no_nulls(div, ["ticker", "date_ex"], "dividends")

    report(div, "dividends", date_col="date_ex")
