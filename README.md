# 📈 CSE Market Regime & Sector Rotation Dashboard

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Pandas](https://img.shields.io/badge/Pandas-2.2-orange)
![Scikit--Learn](https://img.shields.io/badge/Scikit--Learn-1.5-f7931e)
![SciPy](https://img.shields.io/badge/SciPy-Hypothesis%20Testing-8CAAE6)
![Plotly](https://img.shields.io/badge/Plotly-Interactive%20Charts-3f4f75)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Pytest](https://img.shields.io/badge/Tested%20with-Pytest-0A9EDC)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-lightgrey)

A market-analytics platform built on official **Colombo Stock Exchange (CSE)**
statistics data: it detects market regimes (bull / crisis / recovery),
analyzes which sectors lead or lag in each regime, tracks foreign investor
flows, and runs a formal event study on dividend price reactions — all wired
into an interactive Streamlit dashboard.

> **This is a practice project**, built to develop hands-on experience with
> real, messy CSE data before starting a separate, unrelated final-year
> research project. It deliberately focuses on **market-level time series
> and event analysis** rather than company-level classification — every
> scoping decision is documented, not silently applied (see
> [Project scope](#-project-scope-and-why) below).

---

## 📌 Business Problem

> How can data-driven techniques be used to identify different market
> regimes in the CSE, and what does that reveal about sector behaviour and
> price reactions to corporate events within each regime?

Traditional market analysis leans on manually reading charts and historical
trends. This project instead builds a repeatable, testable pipeline —
unsupervised clustering for regime detection, statistical hypothesis testing
for the event study, and transparent aggregation for sector rotation — so
every conclusion can be traced back to code and data, not eyeballing a chart.

---

## 🎯 Objectives

- Ingest and clean real, messy CSE source files (inconsistent headers,
  placeholder values, taxonomy drift across decades)
- Engineer return/volatility/drawdown features from the ASPI index
- Detect market regimes with unsupervised machine learning (KMeans),
  validated against known historical market events
- Rank sector performance within each detected regime
- Run a formal event study — with a statistical significance test — on how
  stock prices react around dividend ex-dates
- Explore cross-signal relationships (regime, volatility, foreign flow) on
  one shared daily timeline, done carefully at the correct statistical grain
- Surface all of the above through an interactive Streamlit dashboard

---

## 🏗️ Pipeline Architecture

```
Raw CSE Excel/ZIP files (data/raw/)
        │
        ▼   src/ingestion/*.py  (+ src/cleaning/tidy.py, src/utils/validation.py)
Cleaned, tidy tables (data/interim/)
        │
        ▼   src/features/*.py
Engineered features (rolling return/vol, drawdown, monthly sector returns)
        │
        ▼   src/models/*.py
Regime timeline (KMeans) · Event study CAR + t-test (data/processed/)
        │
        ▼   app.py
Interactive Streamlit dashboard
```

---

## 📊 What's Inside (Dashboard)

| Page | What it shows |
|---|---|
| Market Overview | ASPI trend colored by detected regime, regime summary stats |
| Sector Rotation | Which sectors outperform in each regime |
| Foreign Activity | Net foreign vs. local investor flows over time |
| Company Explorer | Individual ticker price history |
| Event Study | Price reaction around dividend ex-dates (CAR distribution) |
| About / Methodology | Full data provenance, scope decisions, and limitations |

## 📓 Notebooks

| Notebook | Focus |
|---|---|
| `01_data_audit.ipynb` | Raw-file structure, header quirks, data-quality issues found |
| `02_regime_eda.ipynb` | ASPI by detected regime, validation against known crisis events |
| `03_sector_rotation_eda.ipynb` | Sector performance ranked within each regime |
| `04_event_study.ipynb` | CAR distribution around dividend ex-dates, significance testing |
| `05_cross_signal_eda.ipynb` | Regime + price + foreign flow on one shared daily table — handled carefully at the correct statistical grain to avoid pseudo-replication |

Every notebook is runnable standalone via `jupyter notebook` from the
`notebooks/` folder, or non-interactively via `jupyter nbconvert --execute`.

## 🧩 Shared Helpers & Statistical Modeling

- **`src/cleaning/tidy.py`** — shared wide-to-long melt + numeric-coercion
  helpers used across ingestion loaders.
- **`src/utils/validation.py`** — post-load sanity checks (no nulls, no
  duplicate keys, no future dates, no leaked bad labels) that every
  loader's `__main__` block runs before saving to `data/interim/`.
- **`src/models/event_study_stats.py`** — a one-sample t-test (SciPy) on
  the event study's CAR distribution, checking whether the average price
  reaction is statistically distinguishable from zero.
- **Dual output format** — every table in `data/interim/` and
  `data/processed/` saves as both `.parquet` (what the pipeline reads —
  preserves dtypes, faster) and `.csv` (so any table opens directly in
  Excel/Sheets, no Python required).

---

## ⚙️ Installation & Setup

```bash
git clone https://github.com/lisandihimara/CSE-Market-Regime-Analytics-Platform.git
cd CSE-Market-Regime-Analytics-Platform

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## ▶️ Running the Pipeline

```bash
# Ingestion — raw files → cleaned interim tables
python -m src.ingestion.load_daily_prices
python -m src.ingestion.load_indices
python -m src.ingestion.load_sector_data
python -m src.ingestion.load_foreign_activity
python -m src.ingestion.load_securities_master
python -m src.ingestion.load_corporate_actions

# Feature engineering + modeling
python -m src.features.regime_features
python -m src.models.regime_detection
python -m src.features.sector_rotation
python -m src.features.event_study
python -m src.models.event_study_stats
python -m src.features.daily_master_panel
```

## 🖥️ Running the Dashboard

```bash
streamlit run app.py
```

All processed outputs are already included in `data/interim/` and
`data/processed/` in this download, so you can skip straight to
`streamlit run app.py` if you just want to explore the dashboard without
rebuilding the pipeline.

## 🧪 Running Tests

```bash
pytest tests/ -v
```

9 tests across 6 classes in `tests/test_pipeline.py`, covering data-shape
invariants, duplicate-key checks, and regression guards for specific
bugs found during development (e.g. no event should ever again produce
an implausible >100% CAR).

---

## 📂 Repository Structure

```text
CSE-Market-Regime-Analytics-Platform/
│
├── Dashboard/                     # Streamlit dashboard components
│
├── data/
│   ├── raw/                       # Original CSE source data
│   ├── interim/                   # Cleaned and tidy datasets
│   └── processed/                 # Model and analysis outputs
│
├── docs/                          # Project documentation and supporting materials
│
├── features/                      # Feature engineering and analytical transformations
│
├── models/                        # Machine learning and statistical models
│
├── notebooks/                     # Exploratory analysis and methodology notebooks
│
├── src/                           # Data ingestion and preprocessing source code
│
├── tests/                         # Pytest test suite
│
├── utils/                         # Shared validation and utility functions
│
├── requirements.txt               # Python dependencies
├── .gitignore                     # Files and folders excluded from Git
├── LICENSE                        # Project usage and copyright terms
├── LEARNING_NOTES.md              # Phase-by-phase learning journal
└── README.md                      # Project documentation
---

## 🔍 Project Scope and Why

This dataset came with 34 CSE statistics files spanning 1985–2025. Using
all of it, at full historical depth, in every possible analytical
direction, wasn't realistic — so scope was narrowed deliberately, and
every narrowing decision is documented rather than silently applied:

- **Daily price data covers 2021–2025 only.** CSE's pre-2021 price archives
  use two other, structurally different formats. Parsing all three eras
  generically would have been a bigger project than the analysis itself —
  and 2021–2025 covers the most analytically interesting period: COVID
  recovery, the 2022 sovereign default, and the recovery since.
- **Sector rotation analysis covers 2021–2025 only.** CSE changed its
  sector classification scheme around 2016. Old-scheme and new-scheme
  sector labels are **not** cross-mapped — that would require a real
  methodological crosswalk decision, not a data-cleaning fix.
- **No per-company sector master exists in this dataset** — CSE's sector
  files are already sector-level aggregates, so all sector analysis runs
  at the sector-index level, not per company.
- **Regime detection uses KMeans, not a Hidden Markov Model.** More
  transparent to validate for a practice project — checked against known
  events (COVID-19, the 2022 sovereign default, the 2022 political crisis
  all correctly land in the detected "Crisis / Sell-off" regime) — but an
  HMM regime-switching model, which would explicitly model regime
  persistence over time, is a natural next step, not built here.
- **The event study uses a simplified market-adjusted model** (assumes
  beta = 1 against ASPI) rather than a full market model with estimated
  per-stock beta.

## 🐛 Data Quality Issues Found and Handled

Real institutional data is messy. These were found and fixed during
ingestion, not assumed away:

1. **Header rows sit at inconsistent positions** across files and years —
   solved with a reusable header-detection utility (`src/ingestion/excel_parser.py`).
2. **A title row was mistaken for a real header row** by an early version
   of the sector parser, because the title also contained the substring
   "sector" — fixed by requiring an exact cell match instead of substring search.
3. **Column positions drift across decades** — the SECTOR column sits at a
   different index in 2025-era sheets vs. 2006-era sheets in the same file.
4. **A literal placeholder string** (`"Market Closed Due To COVID -19"`)
   **appears in place of a number** in the foreign activity file — coerced
   to NaN like other known CSE placeholder tokens.
5. **Some tickers trade multiple share classes** under the same company
   code, causing duplicate rows in the price panel — resolved by
   restricting per-ticker analysis to ordinary (N) shares.
6. **A single dividend event initially produced a 98,500% cumulative
   abnormal return** — traced to one implausible daily price move in the
   raw source. Daily returns beyond ±50% are now treated as data errors
   and excluded from the event study.
7. **One exact duplicate row** in the ASPI daily index series (2010-06-30)
   — caught by the test suite, then fixed at the loader level.
8. **Sector names have decades of spelling/abbreviation drift** — merged
   where clearly the same sector within one taxonomy era; genuine
   taxonomy changes were left unmerged (see scope, above).

## ⚠️ Limitations

- Historical daily prices before 2021 are not ingested (see scope).
- Sector rotation is limited to 2021–2025 and to sectors with at least 3
  months of data in a given regime; some thin sectors still show large %
  swings from a small market-cap base.
- Regime labels are rule-based on cluster centroids, not learned or
  formally validated beyond 4 known-event sanity checks.
- The event study assumes beta = 1 for every stock and does not correct
  for the mechanical ex-dividend price drop, which is not the same thing
  as a bearish market reaction.
- `daily_master_panel`'s foreign-flow column is monthly data broadcast
  across daily rows — analyses on it must account for that grain, or risk
  a pseudo-replication error (demonstrated directly in notebook 05).

## 🚀 Suggested Extensions

- Hidden Markov Model regime detection, compared against the KMeans result
- Market-model event study with estimated per-stock beta
- Ingest the 2011–2020 and 1991–2000 price archives (different raw formats)
- ADF stationarity testing and a classical ARIMA/GARCH baseline, as a
  bridge for an econometrics-focused review
- Formal lead-lag testing (e.g. Granger causality) on the foreign-flow /
  regime-transition relationship explored informally in notebook 05

---

## ✅ Key Outcomes

This project demonstrates the ability to:

- Build an end-to-end pipeline from real, messy source files to a tested,
  interactive analytics product
- Apply unsupervised machine learning (KMeans) to an open-ended,
  unlabeled problem, with domain-knowledge validation in place of ground truth
- Design and run a formal statistical hypothesis test (event study CAR
  significance) and interpret it correctly, including its assumptions
- Recognize and correct a real analytical pitfall (pseudo-replication in
  monthly-into-daily joins) rather than just avoid it in theory
- Write pipeline-level data validation and regression tests, not just
  exploratory notebooks
- Communicate scope decisions and limitations explicitly, rather than
  overstating what the analysis supports

---

## ⚠️ Disclaimer

This project is developed for educational and research purposes. The
insights generated by this platform should not be considered financial
advice or used as a guarantee for investment decisions.

## 📄 License

Code: Copyright © 2026 S.Lisandi Himara. All rights reserved.
The repository is publicly available for portfolio and educational review. Reuse, redistribution, modification or incorporation into other projects requires permission from the author. The underlying CSE market data remains subject to the Colombo Stock Exchange's terms of use.

## 👩‍💻 Author

**S.Lisandi Himara**
BSc (Hons) Data Science & Business Analytics
General Sir John Kotelawala Defence University (KDU)

## ⭐ Acknowledgements

- Colombo Stock Exchange, for the underlying market data
- The open-source Python data science community
- Academic research in event-study methodology (MacKinlay, 1997) and
  tidy data principles (Wickham, 2014), both directly applied in this project

If you found this project useful, consider giving it a ⭐ on GitHub.
