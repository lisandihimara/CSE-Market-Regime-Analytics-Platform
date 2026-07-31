# CSE Market Regime & Sector Rotation Dashboard

A market-analytics platform built on official Colombo Stock Exchange (CSE)
statistics data: it detects market regimes (bull / crisis / recovery),
analyzes which sectors lead or lag in each regime, tracks foreign investor
flows, and runs an event study on dividend price reactions — all wired into
an interactive Streamlit dashboard.

**This is a practice project**, built to develop hands-on understanding of
CSE data before starting a separate, unrelated final-year research project.
It deliberately focuses on **market-level time series and event analysis**
rather than company-level classification — see [Project scope](#project-scope-and-why)
below.

## What's inside

| Page | What it shows |
|---|---|
| Market Overview | ASPI trend colored by detected regime, regime summary stats |
| Sector Rotation | Which sectors outperform in each regime |
| Foreign Activity | Net foreign vs. local investor flows over time |
| Company Explorer | Individual ticker price history |
| Event Study | Price reaction around dividend ex-dates (CAR distribution) |
| About / Methodology | Full data provenance, scope decisions, and limitations |

`notebooks/` has the exploratory work behind each stage — a raw-data
audit, EDA notebooks for regime detection, sector rotation, and the
event study, plus a fifth **cross-signal** notebook
(`05_cross_signal_eda.ipynb`) that combines regime, price behavior, and
foreign investor flow onto one shared daily table
(`data/processed/daily_master_panel.parquet`, built by
`src/features/daily_master_panel.py`) to explore relationships *across*
topics rather than within one. That table joins in monthly foreign-flow
data onto daily rows, so its analyses are done carefully at the correct
statistical grain (see the notebook itself for why that matters — it's
also where a naive mean-based reading of the data would have produced
a materially wrong conclusion, walked through explicitly). Every
notebook is runnable standalone via `jupyter notebook` from the
`notebooks/` folder (or `jupyter nbconvert --execute`
non-interactively).

Every table in `data/interim/` and `data/processed/` is saved as both
`.parquet` (what the pipeline itself reads — preserves dtypes, faster)
and `.csv` (so any table can also be opened directly in Excel/Sheets
for a quick manual look, no Python required).

`src/cleaning/tidy.py` and `src/utils/validation.py` are shared helpers
used across the ingestion loaders: `tidy.py` centralizes the
wide-to-long melt + numeric-coercion logic that more than one CSE file
needs, and `validation.py` centralizes the post-load sanity checks
(no nulls, no duplicate keys, no future dates, known-bad values not
leaking through) that every loader's `__main__` block runs before
saving to `data/interim/`. `src/models/event_study_stats.py` runs a
one-sample t-test on the event study's CAR distribution to check
whether the average price reaction is statistically distinguishable
from zero, on top of the descriptive stats `src/features/event_study.py`
already prints.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the pipeline (raw data → interim → processed):
python -m src.ingestion.load_daily_prices
python -m src.ingestion.load_indices
python -m src.ingestion.load_sector_data
python -m src.ingestion.load_foreign_activity
python -m src.ingestion.load_securities_master
python -m src.features.regime_features
python -m src.models.regime_detection
python -m src.features.sector_rotation
python -m src.features.event_study

# Launch the dashboard:
streamlit run app.py

# Run tests:
pytest tests/ -v
```

All processed outputs are already included in `data/interim/` and
`data/processed/` in this download, so you can skip straight to
`streamlit run app.py` if you just want to explore the dashboard.

## Project structure

```
cse-market-regime/
├── data/
│   ├── raw/               # original CSE source files (6 files actually used by the pipeline)
│   ├── interim/           # cleaned, tidy tables (parquet)
│   └── processed/         # regime timeline, sector rankings, event study
├── src/
│   ├── ingestion/          # one loader per CSE source file
│   ├── cleaning/           # shared tidy-data helpers (melt, numeric coercion)
│   ├── features/           # regime features, sector rotation, event study, daily master panel
│   ├── models/             # regime detection (KMeans) + event-study significance testing
│   └── utils/              # post-load validation / sanity-check helpers
├── notebooks/              # exploratory analysis: raw audit, regime, sector, event study, cross-signal
├── tests/                  # pipeline sanity tests (pytest)
├── app.py                  # Streamlit dashboard
└── requirements.txt
```

## Project scope and why

This dataset came with 34 CSE statistics files spanning 1985-2025. Building
one project that used all of it, at full historical depth, in every possible
analytical direction, was not realistic — so scope was narrowed deliberately,
and every narrowing decision is documented rather than silently applied:

- **Daily price data covers 2021-2025 only.** CSE's price archives before
  2021 use two other, structurally different formats: a per-company
  header-block layout for 2011-2020, and a minimal 3-column (date, ticker,
  price only) format for 1991-2000. Parsing all three eras generically would
  have been a bigger project than the analysis itself. 2021-2025 also
  happens to cover the most analytically interesting period — COVID
  recovery, the 2022 sovereign default, and the recovery since.
- **Sector rotation analysis covers 2021-2025 only.** CSE changed its sector
  classification scheme around 2016 (e.g. the old "Banks, Finance &
  Insurance" bucket splits into "Banks", "Insurance", and "Diversified
  Financials" separately post-switch). Old-scheme and new-scheme sector
  labels are **not** cross-mapped — that would require a real methodological
  crosswalk decision, not a data-cleaning fix.
- **No per-company sector master exists in this dataset.** CSE's "sector"
  files are already sector-level aggregates (they don't say which sector an
  individual ticker belongs to), so all sector analysis runs at the
  sector-index level.
- **Regime detection uses KMeans, not a Hidden Markov Model.** KMeans on
  rolling return/volatility/drawdown features is more transparent to
  validate for a practice project. It was checked against known events —
  COVID-19, the 2022 sovereign default, and the 2022 political crisis all
  correctly land in the detected "Crisis / Sell-off" regime — but an HMM
  regime-switching model is a natural next step, not built here.
- **The event study uses a simplified market-adjusted model** (assumes
  beta = 1 against ASPI) rather than a full market model with estimated
  per-stock beta.

## Data quality issues found and handled

Real institutional data is messy. These were found and fixed during
ingestion, not assumed away:

1. **Header rows sit at inconsistent positions** across files and years —
   solved with a reusable header-detection utility (`src/ingestion/excel_parser.py`)
   rather than one-off fixes per file.
2. **A title row was mistaken for a real header row** by an early version of
   the sector market cap parser, because the title also contained the
   substring "sector" — fixed by requiring an exact cell match instead of a
   substring search.
3. **Column positions drift across decades** — the SECTOR column sits at a
   different index in 2025-era sheets vs. 2006-era sheets in the same file.
4. **A literal string** `"Market Closed Due To COVID -19"` **appears in place
   of a number** in the foreign activity file — coerced to NaN like other
   known CSE placeholder tokens.
5. **Some tickers trade multiple share classes** (ordinary/non-voting) under
   the same company code, causing duplicate (ticker, date) rows in the price
   panel — resolved by restricting per-ticker analysis to ordinary (N)
   shares, which make up ~93% of all rows.
6. **A single dividend event initially produced a 98,500% cumulative
   abnormal return** — traced to one implausible daily price move in the raw
   source file. Daily returns beyond ±50% are now treated as data errors and
   excluded from the event study.
7. **One exact duplicate row** in the ASPI daily index series (2010-06-30)
   — caught by the test suite, not manual inspection, and then fixed at the
   loader level.
8. **Sector names have decades of spelling/abbreviation drift** ("Bank
   Finance Ins" vs "Banks, Finance & Insurance") — merged where it was
   clearly the same sector within one scheme; genuine taxonomy changes were
   left unmerged (see above).

## Limitations

- Historical daily prices before 2021 are not ingested (see scope section).
- Sector rotation analysis is limited to 2021-2025 and to sectors with at
  least 3 months of data in a given regime; some thin sectors still show
  large % swings from a small market-cap base — treat outliers with
  caution.
- Regime labels are rule-based on cluster centroids, not learned or
  formally validated beyond the 4 known-event sanity checks described above.
- The event study assumes beta = 1 for every stock; it does not correct for
  the mechanical ex-dividend price drop, which is not the same thing as a
  bearish market reaction.

## Suggested extensions

- Hidden Markov Model regime detection, compared against the KMeans result
- Market-model event study with estimated per-stock beta
- Ingest 2011-2020 and 1991-2000 price archives (different raw formats)
- ADF stationarity testing and a classical ARIMA/GARCH baseline for
  comparison against the ML-based regime detection — a natural bridge for
  an econometrics-focused review

## License

Code: MIT (see `LICENSE`). The underlying CSE market data is subject to the
Colombo Stock Exchange's own terms of use.
