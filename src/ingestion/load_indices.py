"""
Load CSE's "Market Indices - Daily" file.

Quirk specific to this file: the header is split across TWO rows, not one.
Row 3 (0-indexed) holds "S&P Sri Lanka 20" and the 20 GICS sector index
names; row 4 holds "All Share Price Index" / "Milanka Price Index" for
columns 1-2 only. A generic single-row header detector picks row 3 (it
has more non-null cells), which silently loses the ASPI/Milanka labels.
So this loader merges the two header rows explicitly instead of reusing
the generic detector.

Output is reshaped to long format: date, index_name, value — one row
per index per day. This is the format the regime-detection module
expects (it primarily needs the ASPI series, but sector indices are
kept for later sector-rotation cross-checks).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.cleaning.tidy import coerce_numeric, melt_wide_to_long

RAW_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Market Indices - Daily.xls"
)

HEADER_ROW_SECTOR = 3   # S&P SL20 + sector index names
HEADER_ROW_ASPI = 4     # ASPI / Milanka names (cols 1-2 only)
DATA_START_ROW = 5


def load_market_indices_daily(path: Path = RAW_PATH) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None)

    sector_header = raw.iloc[HEADER_ROW_SECTOR]
    aspi_header = raw.iloc[HEADER_ROW_ASPI]

    col_names = ["date"]
    for i in range(1, raw.shape[1]):
        name = aspi_header[i] if pd.notna(aspi_header[i]) else sector_header[i]
        col_names.append(str(name).strip() if pd.notna(name) else f"col_{i}")

    data = raw.iloc[DATA_START_ROW:].copy()
    data.columns = col_names
    data = data.dropna(subset=["date"]).reset_index(drop=True)

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    value_cols = [c for c in data.columns if c != "date"]
    data = coerce_numeric(data, value_cols)
    data = data.dropna(subset=["date"])

    # source has one exact duplicate row (2010-06-30, All Share Price
    # Index) — same date, same value, almost certainly a copy-paste
    # duplicate in the raw file rather than two distinct observations.
    long_df = melt_wide_to_long(
        data, id_vars="date", value_vars=value_cols,
        var_name="index_name", value_name="value",
        dedupe_subset=["index_name", "date"],
    )
    return long_df.sort_values(["index_name", "date"]).reset_index(drop=True)


if __name__ == "__main__":
    from src.utils.validation import (
        assert_not_empty, assert_no_nulls, assert_no_duplicates, report,
    )

    idx = load_market_indices_daily()

    assert_not_empty(idx, "market_indices_daily")
    assert_no_nulls(idx, ["date", "index_name", "value"], "market_indices_daily")
    assert_no_duplicates(idx, ["index_name", "date"], "market_indices_daily")
    assert "All Share Price Index" in idx["index_name"].unique(), \
        "ASPI missing from market_indices_daily -- header-merge logic may be broken"

    INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(INTERIM_DIR / "market_indices_daily.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    idx.to_csv(INTERIM_DIR / "market_indices_daily.csv", index=False)
    report(idx, "market_indices_daily", date_col="date")
