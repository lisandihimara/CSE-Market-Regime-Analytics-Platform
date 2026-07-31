# Data Dictionary

Every table in `data/interim/` and `data/processed/`, one section per
table, in pipeline order. Each table exists as both `.parquet` (what the
code reads) and `.csv` (for opening directly in Excel/Sheets) — the
schema is identical in both.

Grain is stated for every table because several tables in this project
are joined together at points (`sector_rotation_merged`,
`daily_master_panel`), and mixing rows of different grain without
accounting for it is a real, documented risk in this project — see
`notebooks/05_cross_signal_eda.ipynb` for a worked example of what goes
wrong if you don't.

---

## `data/interim/daily_prices_2021_2025`

**Grain**: one row per (ticker, date, main_type, sub_type) — i.e. one row
per share class traded on a given day. **Rows**: 224,684. **Date range**:
2021-01-04 to 2025-12-31. **Source**: `Daily Shares Price List
-2021-2025.zip`, via `src/ingestion/load_daily_prices.py`.

| Column | Type | Description |
|---|---|---|
| `ticker` | string | CSE company code, e.g. `AAF` |
| `main_type` | string | Share class code. Observed values: `N` (ordinary — ~93% of rows, what most of this project's analysis uses), `P`, `R`, `X`, `U`, `W` (preference, rights, non-voting, unit trust, and warrant classes) |
| `sub_type` | string | Secondary class identifier. Stored as **string, not int** — some years' raw files encode this as `"0000"`, others as `"0"` or `"0.0"`; forcing to string avoids a silent type mismatch. Combined with `main_type`, this is what makes the row-level key unique (a ticker can have more than one `main_type`/`sub_type` combination trading on the same day) |
| `short_name` | string | CSE's abbreviated security name |
| `date` | datetime | Trading date |
| `high`, `low`, `close`, `open` | float | OHLC prices in LKR |
| `trade_volume` | float | Number of trades executed |
| `share_volume` | float | Number of shares traded |
| `turnover` | float | Value traded, in LKR |
| `source_file` | string | Which member of the raw ZIP this row came from — kept for tracing a bad row back to its origin file (lightweight data lineage) |

**Note**: `event_study.py` and `regime_features.py` both filter this table
to `main_type == "N"` before use, to avoid a duplicate-row problem caused
by multiple share classes sharing a ticker on the same day.

---

## `data/interim/market_indices_daily`

**Grain**: one row per (index_name, date). **Rows**: 194,221. **Date
range**: 1985-01-02 to 2025-12-31. **Source**: `Market Indices -
Daily.xls`, via `src/ingestion/load_indices.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Trading date |
| `index_name` | string | Which index/sector-index this value belongs to (see full list below) |
| `value` | float | Index level for that day |

**`index_name` values observed**: `All Share Price Index` (ASPI — the
main index most of this project's regime detection is built on),
`Milanka Price Index`, `S&P Sri Lanka 20`, plus 20 GICS sector indices
(`Banks Finance & Insurance`, `Beverage, Food & Tobacco`, `Chemicals &
Pharmaceuticals`, `Construction & Engineering`, `Diversified`, `Footwear
& Textile`, `Healthcare`, `Hotels & Travels`, `IT`, `Investment Trusts`,
`Land & Property`, `Manufacturing`, `Motors`, `Oil Palms`, `Plantations`,
`Power & Energy`, `Services`, `Stores & Supplies`, `Telecommunications`,
`Trading`).

**⚠️ Known open data-quality issue, not yet fixed**: one additional
`index_name` value, literally `"col_21"`, appears in this table — 960
rows, spanning 2021-12-21 to 2025-12-31, with plausible-looking index
values (range ~455-1,423). This is a **fallback name**, assigned by
`load_indices.py` when the raw file's header row has a genuinely blank
cell at that column position (see the `f"col_{i}"` fallback in the
loader). In plain terms: the raw source file appears to have added a
21st index/sector column at some point without labeling it in either of
the two header rows the loader reads — so the data is real, but its
actual identity (which index or sector this is) is currently unknown.
This was found while writing this data dictionary, not caught by the
existing test suite (`assert_no_nulls`/`assert_no_duplicates` don't
check for a fallback-named column, since neither the column name nor its
values are null). **Recommended fix**: manually inspect the raw file's
header rows 3-5 around that column position in a spreadsheet viewer to
identify the intended label, then add it to a name-correction map in the
loader — not done here, flagged for follow-up.

---

## `data/interim/sector_market_cap`

**Grain**: one row per (sector, date), date is always the 1st of a
month. **Rows**: 5,004. **Date range**: 2005-01-01 to 2025-12-01.
**Source**: `Sector Market Capitalisation.xls`, via
`src/ingestion/load_sector_data.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Always day 1 of the month — this is monthly data, not daily |
| `sector` | string | Sector name, normalized to Title Case with known aliases merged within the same taxonomy era (see `SECTOR_ALIASES` in the loader) |
| `market_cap` | float | Total market capitalization of that sector, in LKR, at month end |

Only 2021-2025 of this table is actually used downstream
(`sector_rotation.py` filters to that range) — see `README.md` →
Project scope for why the full 2005-2025 history isn't cross-mapped
across the pre/post-2016 sector taxonomy change.

---

## `data/interim/foreign_activity`

**Grain**: one row per (date, transaction_type, investor_type), date is
always the 1st of a month. **Rows**: 5,697. **Date range**: 1992-01-01
to 2025-12-03. **Source**: `Foreign Activity - Monthly.xlsx`, via
`src/ingestion/load_foreign_activity.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Monthly, always day 1 |
| `transaction_type` | string | `purchases`, `sales`, or `net` (purchases minus sales) |
| `investor_type` | string | `Foreign Companies`, `Foreign Individuals`, `Local Companies`, `Local Individuals`, `Total Foreign`, `Total Local` |
| `value` | float | Transaction value in LKR |

**Used elsewhere**: `daily_master_panel.py` filters this to
`transaction_type == "net"` and `investor_type == "Total Foreign"` to
get one clean "net foreign flow" figure per month, then broadcasts it
across each day of that month — see `daily_master_panel` below for the
grain caveat this creates.

---

## `data/interim/securities_master`

**Grain**: one row per ticker (a snapshot, not a time series). **Rows**:
280. **Source**: `Market Capitalisation of Listed Companies.xls`, via
`src/ingestion/load_securities_master.py`.

| Column | Type | Description |
|---|---|---|
| `ticker` | string | CSE company code |
| `security_type` | string | **Despite the column name, this holds the full security identifier** (e.g. `AAF.N0000`), not a simple category label like "Equity"/"Debenture" — that's how the raw source column ("SECURITY TYPE") is actually populated. Kept as-is, under its original name, rather than silently relabeling it, since renaming it might imply an interpretation of the raw data that hasn't actually been verified against CSE's own documentation |
| `company_name` | string | Full company name |
| `indexed_price` | float | CSE's indexed price value (index-basis price, not a raw trading price) |
| `indexed_quantity` | int | CSE's indexed quantity value |
| `market_cap` | float | Market capitalization, in LKR, as of the snapshot date |

**Known limitation**: no field here (or anywhere else in this dataset)
maps a ticker to its sector — see `README.md` → Project scope.

---

## `data/interim/regime_features` and `data/processed/regime_timeline`

**Grain**: one row per trading day (ASPI only). **Rows**: 9,752 (before
the final NaN-drop) / 9,712 (after, in `regime_timeline`). **Source**:
built from `market_indices_daily`, via `src/features/regime_features.py`
and `src/models/regime_detection.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Trading date |
| `close` | float | ASPI closing level |
| `daily_return` | float | Simple day-over-day % return. **This is what actually feeds the model** — see `log_return` note below |
| `log_return` | float | `ln(close / close.shift(1))`. Computed but **not currently used** by any downstream feature or the regime model — a known, minor piece of leftover technical debt, not a hidden design choice. It was cheap to compute and is the theoretically "more correct" return measure for additivity across time, but the switch to actually using it in the model features was never completed |
| `roll_return_20d`, `roll_return_60d` | float | 20/60-trading-day simple return (`pct_change(20)` / `pct_change(60)`) |
| `roll_vol_20d`, `roll_vol_60d` | float | Rolling standard deviation of `daily_return` over 20/60 days, **annualized** (× √252) |
| `drawdown` | float | `close / trailing_252d_max - 1`; 0 = at a 252-day high, negative = below it |
| `cluster` | int | *(regime_timeline only)* Raw KMeans cluster number (0-3) — not interpretable on its own |
| `regime` | string | *(regime_timeline only)* Human-readable label assigned to each cluster after fitting: `"Bull / Stable Growth"`, `"Volatile Recovery"`, `"Bear / Quiet Decline"`, or `"Crisis / Sell-off"` — see `label_cluster()` in `regime_detection.py` |

**Model inputs**: only `roll_return_20d`, `roll_vol_20d`, `roll_vol_60d`,
`drawdown` are actually used as KMeans features (`FEATURE_COLS` in
`regime_detection.py`) — `roll_return_60d` and `log_return` are computed
but not fed to the model.

---

## `data/processed/sector_rotation_merged`

**Grain**: one row per (sector, month), 2021-2025 only. **Rows**: 1,167.
**Source**: joins `sector_market_cap` with the monthly-mode of
`regime_timeline`, via `src/features/sector_rotation.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Month (1st of month) |
| `sector` | string | Sector name |
| `market_cap` | float | Sector market cap that month, LKR |
| `mom_return` | float | Month-over-month % change in that sector's market cap |
| `month` | datetime | Same value as `date` — a duplicate join-key column left over from the merge; harmless but redundant, worth cleaning up |
| `regime` | string | That month's regime, taken as the **mode** (most common) daily regime across the month's trading days |

## `data/processed/sector_rotation_ranking`

**Grain**: one row per (regime, sector) that has ≥3 months of data.
**Rows**: 62. **Source**: aggregates `sector_rotation_merged`.

| Column | Type | Description |
|---|---|---|
| `regime` | string | Regime label |
| `sector` | string | Sector name |
| `avg_monthly_return` | float | Mean of `mom_return` across all months that sector spent in that regime |
| `n_months` | int | How many months back that average — rows with `n_months < 3` are filtered out before this table is saved, since an average based on 1-2 months isn't trustworthy |

---

## `data/processed/event_study_dividends`

**Grain**: one row per dividend event. **Rows**: 1,027. **Source**: built
from `daily_prices_2021_2025` + `market_indices_daily` (ASPI) +
dividend announcements, via `src/features/event_study.py`.

| Column | Type | Description |
|---|---|---|
| `ticker` | string | CSE company code |
| `ex_date` | datetime | First trading day at or after the announced dividend ex-date |
| `dividend_rate` | float | Announced dividend rate, LKR per share |
| `car` | float | Cumulative Abnormal Return: sum of `(stock_return - market_return)` over the ±5-trading-day window around `ex_date`, after excluding any day with a >50% single-day return (treated as a data error) |
| `n_valid_days` | int | How many of the (up to) 11 window days actually had usable data and passed the return-plausibility filter |

**Statistical testing on this table** lives in
`src/models/event_study_stats.py`, not in this table itself — see that
module or `notebooks/04_event_study.ipynb` for the significance test
results (mean CAR ≈ −1.2%, p ≈ 0.004).

---

## `data/processed/daily_master_panel`

**Grain**: one row per trading day, 1985-04-02 to 2025-12-31 (starts
later than `regime_timeline` because the first ~20 days are dropped
where rolling features aren't yet available). **Rows**: 9,712. **Source**:
joins `regime_timeline` with `foreign_activity`, via
`src/features/daily_master_panel.py`.

| Column | Type | Description |
|---|---|---|
| `date` | datetime | Trading date |
| `close`, `daily_return`, `roll_return_20d`, `roll_vol_20d`, `roll_vol_60d`, `drawdown`, `regime` | — | Same as `regime_timeline`, see above |
| `foreign_net_flow_monthly` | float | **⚠️ Monthly value broadcast across every day in that month** — not a real daily observation. The same number repeats ~21 times per month. Populated for 83.6% of days (gaps are months before foreign-activity data starts, 1985-1991). Treating each repeated row as an independent daily observation in a correlation or significance test is a real statistical error (pseudo-replication) — `notebooks/05_cross_signal_eda.ipynb` handles this explicitly by re-aggregating to monthly grain before drawing any conclusion from this column, and demonstrates the naive vs. corrected approach side by side |

---

## Join keys, if you need to combine tables yourself

| To join... | ...with | Key |
|---|---|---|
| `regime_timeline` | `sector_rotation_merged` | `date` (regime_timeline) → `date`/`month` (sector_rotation_merged), both at month grain once aggregated |
| `regime_timeline` | `foreign_activity` | `date` truncated to month-start on both sides (see `daily_master_panel.py` for the exact pattern: `.values.astype("datetime64[M]")`) |
| `daily_prices_2021_2025` | `securities_master` | `ticker` |
| `event_study_dividends` | `daily_prices_2021_2025` | `ticker` + date range around `ex_date` |

No single file joins everything — see the project README's "why not one
combined dataset" discussion for why that's a deliberate choice, not a
gap.
