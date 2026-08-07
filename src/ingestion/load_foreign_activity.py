"""
Load CSE's "Foreign Activity - Monthly" file.

Structure: one sheet, dates running across 409 columns (1992-01 to
2025-12) as the header row, and rows organized into three hierarchical
blocks (each row label repeats within a block):

    Purchases and Sales      <- section header, no data
      Purchases              <- section header, no data
        Foreign Companies
        Foreign Individuals
        Local Companies
        Local Individuals
      Sales                  <- section header, no data
        Foreign Companies
        Foreign Individuals  (source has a typo: "Foreign Inviduals")
        Local Companies
        Local Individuals
    Nett Purchases/(Sales)   <- section header, no data
      Foreign Companies
      Foreign Individuals
      Total Foreign
      Local Companies
      Local Individuals
      Total Local

Because of the section-header rows this isn't a good fit for the
generic single-header-row detector -- the row layout is fixed and
documented CSE-side, so it's mapped explicitly here rather than
inferred heuristically (safer than guessing wrong on a hierarchy).

Also note: one cell (Purchases, March 2020) contains the literal string
"Market Closed Due To COVID -19" instead of a number -- this is coerced
to NaN like any other non-numeric CSE placeholder.

Output: long format with columns date, transaction_type
(purchases/sales/net), investor_type, value.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Foreign Activity - Monthly.xlsx"
)

# row_index -> (transaction_type, investor_type)
ROW_MAP = {
    3: ("purchases", "Foreign Companies"),
    4: ("purchases", "Foreign Individuals"),
    5: ("purchases", "Local Companies"),
    6: ("purchases", "Local Individuals"),
    8: ("sales", "Foreign Companies"),
    9: ("sales", "Foreign Individuals"),
    10: ("sales", "Local Companies"),
    11: ("sales", "Local Individuals"),
    13: ("net", "Foreign Companies"),
    14: ("net", "Foreign Individuals"),
    15: ("net", "Total Foreign"),
    16: ("net", "Local Companies"),
    17: ("net", "Local Individuals"),
    18: ("net", "Total Local"),
}


def load_foreign_activity(path: Path = RAW_PATH) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None)

    date_header = raw.iloc[0, 1:]
    dates = pd.to_datetime(date_header, errors="coerce")

    long_rows = []
    for row_idx, (txn_type, investor_type) in ROW_MAP.items():
        row = raw.iloc[row_idx, 1:]
        values = pd.to_numeric(row, errors="coerce")
        for date, val in zip(dates, values):
            if pd.isna(date) or pd.isna(val):
                continue
            long_rows.append({
                "date": date,
                "transaction_type": txn_type,
                "investor_type": investor_type,
                "value": val,
            })

    df = pd.DataFrame(long_rows).sort_values(["transaction_type", "investor_type", "date"])
    return df.reset_index(drop=True)


if __name__ == "__main__":
    from src.utils.validation import (
        assert_not_empty, assert_no_nulls, assert_no_duplicates, report,
    )

    fa = load_foreign_activity()

    assert_not_empty(fa, "foreign_activity")
    assert_no_nulls(fa, ["date", "transaction_type", "investor_type", "value"], "foreign_activity")
    assert_no_duplicates(fa, ["date", "transaction_type", "investor_type"], "foreign_activity")

    # sanity check: the known COVID gap should not appear as a value
    # (the literal string "Market Closed Due To COVID -19" should have
    # been coerced to NaN and dropped, not survived as a stray value)
    covid_month = fa[(fa["date"] == "2020-03-01") & (fa["transaction_type"] == "purchases")]
    assert covid_month.empty, "expected the March 2020 COVID closure cell to be dropped, not present"

    INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    fa.to_parquet(INTERIM_DIR / "foreign_activity.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    fa.to_csv(INTERIM_DIR / "foreign_activity.csv", index=False)
    report(fa, "foreign_activity", date_col="date")
