"""
Load a ticker -> company name / security type reference table.

Source: "21Market Capitalisation of Listed Companies.xls" — chosen over
"16 List of Quoted Securities..." because it already keys one row per
company at the COMPANY CODE level (matches the `ticker` field used in
load_daily_prices.py), whereas the securities list keys by SECURITY ID
(e.g. "AAF-N-0000", "AAF/BD/18/12/27" for bonds) with multiple rows per
company across equity/debt instruments.

Known limitation: this dataset does not include a per-company sector
classification anywhere. The "sector" files (Sector Market Cap,
GICS-Daily) are sector-level aggregates CSE already computed — they do
not map an individual ticker to a sector. Sector-rotation analysis in
this project therefore runs at the sector-index level (see
load_sector_data.py), not by joining individual companies to sectors.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.excel_parser import read_cse_sheet

RAW_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Market Capitalisation of Listed Companies.xls"
)

COLUMN_MAP = {
    "COMPANY CODE": "ticker",
    "SECURITY TYPE": "security_type",
    "COMPANY NAME": "company_name",
    "INDEXED PRICE (Rs)": "indexed_price",
    "INDEXED QUANTITY (No.)": "indexed_quantity",
    "MARKET CAP (Rs.)": "market_cap",
}


def load_securities_master(path: Path = RAW_PATH, sheet_name: str = "2025") -> pd.DataFrame:
    df = read_cse_sheet(path, sheet_name=sheet_name)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items()})
    keep = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[keep].copy()

    df["ticker"] = df["ticker"].astype(str).str.strip()
    df["company_name"] = df["company_name"].astype(str).str.strip()
    for col in ["indexed_price", "indexed_quantity", "market_cap"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["ticker"]).drop_duplicates(subset=["ticker"])
    return df.reset_index(drop=True)


if __name__ == "__main__":
    from src.utils.validation import assert_not_empty, assert_no_nulls, assert_no_duplicates, report

    master = load_securities_master()

    assert_not_empty(master, "securities_master")
    assert_no_nulls(master, ["ticker", "company_name"], "securities_master")
    assert_no_duplicates(master, ["ticker"], "securities_master")

    INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    master.to_parquet(INTERIM_DIR / "securities_master.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    master.to_csv(INTERIM_DIR / "securities_master.csv", index=False)
    report(master, "securities_master")
