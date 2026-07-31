# Data Sources

All raw data originates from the Colombo Stock Exchange (CSE)'s official
statistics exports. This document covers what was actually used, what
wasn't, and why — the original export the project started from contained
roughly 33 files; only 6 are used by this pipeline.

## Provenance and license

Source: Colombo Stock Exchange (CSE) official statistics downloads,
exported as a "2025 Q4" batch (the raw files themselves cover a much
wider historical range than that export date suggests — see per-file date
ranges below). The underlying market data is subject to CSE's own terms
of use, not this project's MIT license (see root `LICENSE` — that license
covers this project's code only).

`data/raw/` is gitignored in this repository (see `.gitignore`) — it is
not redistributed via version control. If you need the raw files, they
must be obtained directly from CSE or from whoever provided this dataset
originally.

---

## Files actually used by the pipeline

| Raw file | Used by | Contains | Date range in this file |
|---|---|---|---|
| `Daily Shares Price List -2021-2025.zip` | `src/ingestion/load_daily_prices.py` | Daily OHLC prices, volumes, and turnover for every listed security, one file per period inside the archive | 2021-01-04 → 2025-12-31 |
| `Market Indices - Daily.xls` | `src/ingestion/load_indices.py` | Daily closing levels for ASPI, Milanka, S&P Sri Lanka 20, and 20 GICS sector indices | 1985-01-02 → 2025-12-31 |
| `Sector Market Capitalisation.xls` | `src/ingestion/load_sector_data.py` | Monthly sector-level market capitalization, one workbook sheet per year | 2005-01-01 → 2025-12-01 (only 2021-2025 actually used — see scope note below) |
| `Foreign Activity - Monthly.xlsx` | `src/ingestion/load_foreign_activity.py` | Monthly foreign vs. local investor purchases/sales/net activity, split by companies vs. individuals | 1992-01-01 → 2025-12-03 |
| `Market Capitalisation of Listed Companies.xls` | `src/ingestion/load_securities_master.py` | A snapshot: one row per listed company, with ticker, name, and market cap | Single snapshot (2025 sheet), not a time series |
| `Dividends.xls` | `src/ingestion/load_corporate_actions.py` | Dividend announcements: ticker, ex-date, rate. **Not saved to `data/interim/`** — read live by `event_study.py` rather than cached, since only one downstream script needs it | 2020-12-15 → 2025-12-11 |

**Why these 6 specifically**: each is the source of exactly one thing
this project's analysis needs (regime detection needs the index file;
sector rotation needs the sector file; the event study needs prices +
dividends; the dashboard's foreign-activity page needs the foreign-flow
file; the securities master resolves ticker → company name). No file was
included "just in case" — every file here maps to a specific loader and
a specific downstream use.

---

## Files that existed in the original export but were NOT used

For transparency — these were part of the original ~33-file CSE export
this project started from, and were deliberately left out of this
trimmed `data/raw/`:

| Category | Examples | Why excluded |
|---|---|---|
| **Pre-2021 daily price archives** | 1991-2000 and 2011-2020 price files | Structurally different raw format from the 2021-2025 file (different column layout per era) — parsing all three eras would have been a bigger project than the analysis itself. This is the single largest chunk of excluded data, and the project's biggest documented scope limitation (see root `README.md` → Project scope) |
| **Per-stock beta** | `Beta Value.xls` | Exists in the original export and is directly relevant to the event study's biggest stated simplification (it currently assumes beta = 1 for every stock instead of an estimated per-stock beta) — a real, known gap, not an oversight; see root `README.md` → Suggested extensions |
| **Other corporate actions** | Scrip dividends, capitalization of reserves (bonus issues), rights issues, share splits, new listings & de-listings | Only dividends were ingested; the event-study methodology could in principle be extended to these other event types, but wasn't |
| **Additional market/sector detail** | Market Indices - Monthly, Total Returns Indices, Market Ratios, Sector Trading Statistics, Sector Ratios, Sector Domestic & Foreign Analysis, Sector Foreign Purchases & Sales | Overlapping or more granular versions of data already covered by the 6 files used; not needed for this project's specific analyses |
| **Other** | CDS Activities, List of Quoted Securities, Debt Trading Statistics, Block Trades, Foreign Holding-Annual, GICS-Daily | Outside this project's scope (debt market, custody/settlement activity, not equity market regime/sector/event analysis) |

None of these were used to derive any table in `data/interim/` or
`data/processed/` — if a number in this project's dashboard or notebooks
looks like it should come from one of these files, it doesn't; check the
data dictionary (`docs/data_dictionary.md`) for where it actually comes
from instead.

---

## A note on file naming

The 6 files listed above are stored under simplified names (e.g.
`Market Indices - Daily.xls`, not the original export's
`07Market Indices - Daily.xls` with its numeric prefix and `2025 Q4/`
subfolder). This was a deliberate cleanup — the numeric prefixes were an
artifact of the export batch's own ordering, not meaningful identifiers,
and every `src/ingestion/*.py` loader's `RAW_PATH` was updated to match
the simplified names. If you're re-adding a fresh CSE export to this
project, either rename the incoming files to match the paths in each
loader's `RAW_PATH`, or update `RAW_PATH` in the relevant loader instead
— whichever is less error-prone for your workflow.
