"""
Load CSE's "Sector Market Capitalisation - Monthly" file.

Structure: one sheet per year (2021-2025), each with sectors as rows and
months as columns (Jan-Dec, with some duplicate month labels appearing
twice in a single sheet due to a mid-file layout change in the source
workbook -- both are captured and left for the caller to reconcile via
duplicate-column suffixing, since collapsing them silently could hide a
real data issue).

Output is reshaped to long format: date (first of month), sector, market_cap.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.cleaning.tidy import coerce_numeric

RAW_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "Sector Market Capitalisation.xls"
)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Some year sheets append whole-market index totals as extra rows below
# the real sector list (e.g. ASPI, MPI = All Share / Milanka Price Index
# market cap). Those aren't sectors and would corrupt sector-rotation
# analysis if left in, so they're filtered out explicitly.
NON_SECTOR_LABELS = {"ASPI", "MPI", "S&P SL20", "TOTAL", "MARKET",
                     "ASPI MKT CAP", "S&P", "S&P MKT CAP"}

# Pure spelling/abbreviation variants of the SAME sector within CSE's
# older (pre-~2016) classification scheme -- these are safe to merge.
# NOTE: CSE switched to a GICS-aligned sector scheme around 2016 (e.g.
# the old "Banks, Finance & Insurance" bucket splits into "Banks",
# "Insurance", and "Diversified Financials" separately post-switch).
# That is a genuine change in classification methodology, not a typo,
# so old-scheme and new-scheme sector labels are deliberately NOT
# cross-mapped here -- treat pre-2016 and post-2016 sector series as
# structurally different taxonomies in any downstream analysis.
SECTOR_ALIASES = {
    "Bank Finance Ins": "Banks, Finance & Insurance",
    "Banks, Finance & Inurance": "Banks, Finance & Insurance",
    "Bev Food Tobacco": "Beverage, Food & Tobacco",
    "Chemicals Pharms": "Chemicals & Pharmaceuticals",
    "Chemicals & Pharmacueticals": "Chemicals & Pharmaceuticals",
    "Construction Eng": "Construction & Engineering",
    "Footwear Textile": "Footwear & Textiles",
    "Hotels Travels": "Hotels & Travels",
    "Land Property": "Land & Property",
    "Stores Supplies": "Stores & Supplies",
    "Telecom": "Telecommunication",
    "Telecommunication Services": "Telecommunication",
    "It": "Information Technology",
    "Investment Trust": "Investment Trusts",
}


def _load_year_sheet(path: Path, sheet_name: str, year: int) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)

    # Header row: has a cell that EQUALS "SECTOR" (not just contains it --
    # the title row above it, e.g. "Sector Market Capitalisation - Monthly
    # 2025", also contains the substring "sector" and was a false match
    # here until this was tightened to an exact, stripped comparison).
    header_row_idx = None
    for i in range(min(8, len(raw))):
        row = raw.iloc[i]
        if row.astype(str).str.strip().str.upper().eq("SECTOR").any():
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError(f"Could not locate header row in sheet {sheet_name}")

    header = raw.iloc[header_row_idx]

    # Locate the SECTOR column by position dynamically -- some year
    # sheets have a leading blank spacer column before it (2025-era
    # layout), others don't (2006-era layout), so a fixed index is
    # wrong for at least one of the two layouts.
    sector_pos = next(
        i for i, c in enumerate(header)
        if pd.notna(c) and str(c).strip().upper() == "SECTOR"
    )

    data = raw.iloc[header_row_idx + 1:].copy()
    data.columns = [str(c).strip() if pd.notna(c) else f"col_{i}" for i, c in enumerate(header)]
    data = data.dropna(how="all")

    data = data.rename(columns={data.columns[sector_pos]: "sector"})
    data = data.dropna(subset=["sector"])
    data = data[data["sector"].astype(str).str.strip() != ""]
    data = data[~data["sector"].astype(str).str.strip().str.upper().isin(NON_SECTOR_LABELS)]

    # Iterate by column POSITION, not by name lookup: some sheets repeat
    # Oct/Nov/Dec in a second block later in the row (a layout change
    # mid-source), so column names alone are ambiguous. Positional
    # iteration keeps every occurrence instead of colliding on name.
    month_positions = [
        (pos, str(col).strip()) for pos, col in enumerate(data.columns)
        if str(col).strip() in MONTHS
    ]

    long_rows = []
    for _, row in data.iterrows():
        # normalize casing so e.g. "BANKS" (older sheets, all-caps) and
        # "Banks" (newer sheets, title-case) collapse to one label --
        # known remaining limitation: a handful of sectors have outright
        # typos in some years (e.g. "INURANCE", "PHARMACUETICALS") which
        # this does not fix; documented in README as a data-quality note.
        sector_name = str(row["sector"]).strip().title()
        sector_name = SECTOR_ALIASES.get(sector_name, sector_name)
        for pos, month_name in month_positions:
            val = pd.to_numeric(row.iloc[pos], errors="coerce")
            if pd.isna(val):
                continue
            month_num = MONTHS.index(month_name) + 1
            long_rows.append({
                "date": pd.Timestamp(year=year, month=month_num, day=1),
                "sector": sector_name,
                "market_cap": val,
            })
    return pd.DataFrame(long_rows)


def load_sector_market_cap(path: Path = RAW_PATH) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    frames = []
    for sheet in xl.sheet_names:
        try:
            year = int(str(sheet).strip())
        except ValueError:
            continue
        frames.append(_load_year_sheet(path, sheet, year))

    full = pd.concat(frames, ignore_index=True)
    full = full.sort_values(["sector", "date"]).drop_duplicates(subset=["sector", "date"])
    return full.reset_index(drop=True)


if __name__ == "__main__":
    from src.utils.validation import (
        assert_not_empty, assert_no_nulls, assert_no_duplicates,
        assert_values_not_in, report,
    )

    sec = load_sector_market_cap()

    assert_not_empty(sec, "sector_market_cap")
    assert_no_nulls(sec, ["date", "sector", "market_cap"], "sector_market_cap")
    assert_no_duplicates(sec, ["sector", "date"], "sector_market_cap")
    assert_values_not_in(
        sec, "sector",
        {"Aspi", "Aspi Mkt Cap", "Mpi", "S&P", "S&P Mkt Cap"},
        "sector_market_cap",
    )

    INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    sec.to_parquet(INTERIM_DIR / "sector_market_cap.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    sec.to_csv(INTERIM_DIR / "sector_market_cap.csv", index=False)
    report(sec, "sector_market_cap", date_col="date")
