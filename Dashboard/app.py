"""
CSE Market Regime & Sector Rotation Dashboard.

Run with: streamlit run app.py

Pages:
  - Market Overview: ASPI trend, regime timeline
  - Sector Rotation: which sectors lead/lag by regime
  - Foreign Activity: net foreign investor flows
  - Company Explorer: individual ticker price history
  - Event Study: dividend ex-date price reaction explorer
  - About / Methodology: data provenance and limitations
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(page_title="CSE Market Regime Dashboard", layout="wide")

REGIME_COLORS = {
    "Bull / Stable Growth": "#2ca02c",
    "Volatile Recovery": "#ff7f0e",
    "Crisis / Sell-off": "#d62728",
    "Bear / Quiet Decline": "#7f7f7f",
}


@st.cache_data
def load_data():
    data = {}
    for name, path in [
        ("regimes", PROCESSED / "regime_timeline.parquet"),
        ("sector_ranking", PROCESSED / "sector_rotation_ranking.parquet"),
        ("sector_merged", PROCESSED / "sector_rotation_merged.parquet"),
        ("event_study", PROCESSED / "event_study_dividends.parquet"),
        ("foreign_activity", INTERIM / "foreign_activity.parquet"),
        ("securities", INTERIM / "securities_master.parquet"),
        ("prices", INTERIM / "daily_prices_2021_2025.parquet"),
    ]:
        data[name] = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    return data


data = load_data()

st.sidebar.title("CSE Market Dashboard")
page = st.sidebar.radio(
    "Navigate",
    ["Market Overview", "Sector Rotation", "Foreign Activity",
     "Company Explorer", "Event Study", "About / Methodology"],
)

# ---------------------------------------------------------------- Overview
if page == "Market Overview":
    st.title("Market Overview — ASPI & Detected Regimes")
    regimes = data["regimes"]

    if regimes.empty:
        st.warning("Regime data not found. Run `python -m src.models.regime_detection` first.")
    else:
        fig = go.Figure()
        for regime, color in REGIME_COLORS.items():
            subset = regimes[regimes["regime"] == regime]
            if subset.empty:
                continue
            fig.add_trace(go.Scatter(
                x=subset["date"], y=subset["close"], mode="markers",
                name=regime, marker=dict(size=3, color=color),
            ))
        fig.update_layout(
            title="ASPI colored by detected market regime",
            xaxis_title="Date", yaxis_title="ASPI",
            height=500, legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Latest ASPI", f"{regimes['close'].iloc[-1]:,.0f}")
        col2.metric("Current regime", regimes["regime"].iloc[-1])
        col3.metric("Data span", f"{regimes['date'].min():%Y-%m} → {regimes['date'].max():%Y-%m}")

        st.subheader("Regime summary statistics")
        summary = regimes.groupby("regime").agg(
            trading_days=("date", "count"),
            avg_20d_return=("roll_return_20d", "mean"),
            avg_annualized_vol=("roll_vol_20d", "mean"),
            avg_drawdown=("drawdown", "mean"),
        ).round(4)
        st.dataframe(summary, use_container_width=True)

        st.caption(
            "Regimes are detected via KMeans clustering on rolling return/volatility/"
            "drawdown features, then labeled by rule (not learned). Cross-checked "
            "against known events: COVID-19 (2020-03), the 2022 sovereign default, "
            "and the 2022 political crisis all correctly fall in 'Crisis / Sell-off'. "
            "See About / Methodology for details."
        )

# ---------------------------------------------------------------- Sector Rotation
elif page == "Sector Rotation":
    st.title("Sector Rotation by Market Regime")
    ranking = data["sector_ranking"]

    if ranking.empty:
        st.warning("Sector rotation data not found. Run `python -m src.features.sector_rotation` first.")
    else:
        st.caption(
            "Analysis window: 2021-2025 only, to stay within one consistent sector "
            "classification scheme (CSE changed sector taxonomy around 2016 — see "
            "About / Methodology). Some thin sectors show extreme % swings due to a "
            "small market-cap base; treat outliers with caution."
        )
        regime_options = ranking["regime"].unique().tolist()
        selected_regime = st.selectbox("Select regime", regime_options)

        subset = ranking[ranking["regime"] == selected_regime].sort_values(
            "avg_monthly_return", ascending=False
        )
        fig = px.bar(
            subset.head(15), x="avg_monthly_return", y="sector", orientation="h",
            title=f"Top sectors during '{selected_regime}'",
            labels={"avg_monthly_return": "Avg monthly market-cap growth", "sector": ""},
        )
        fig.update_layout(height=500, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(subset, use_container_width=True)

# ---------------------------------------------------------------- Foreign Activity
elif page == "Foreign Activity":
    st.title("Foreign Investor Activity")
    fa = data["foreign_activity"]

    if fa.empty:
        st.warning("Foreign activity data not found.")
    else:
        net = fa[fa["transaction_type"] == "net"]
        investor_options = net["investor_type"].unique().tolist()
        selected = st.multiselect("Investor category", investor_options,
                                   default=["Total Foreign", "Total Local"])

        subset = net[net["investor_type"].isin(selected)]
        subset = subset[subset["date"] >= "2018-01-01"]

        fig = px.line(
            subset, x="date", y="value", color="investor_type",
            title="Net purchases (Rs.) — positive = net buying",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Net = Purchases − Sales for that investor category. Sri Lanka's "
            "2022 sovereign default period is visible as a shift in foreign vs "
            "local flows — worth comparing against the Market Overview regime "
            "timeline."
        )

# ---------------------------------------------------------------- Company Explorer
elif page == "Company Explorer":
    st.title("Company Price Explorer")
    prices = data["prices"]
    securities = data["securities"]

    if prices.empty:
        st.warning("Price data not found.")
    else:
        ord_prices = prices[prices["main_type"] == "N"]
        tickers = sorted(ord_prices["ticker"].unique())
        default_idx = tickers.index("COMB") if "COMB" in tickers else 0
        ticker = st.selectbox("Select ticker", tickers, index=default_idx)

        company_row = securities[securities["ticker"] == ticker]
        if not company_row.empty:
            st.caption(f"**{company_row.iloc[0]['company_name']}**")

        hist = ord_prices[ord_prices["ticker"] == ticker].sort_values("date")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["date"], y=hist["close"], mode="lines", name="Close"))
        fig.update_layout(title=f"{ticker} — closing price", height=450,
                           xaxis_title="Date", yaxis_title="Price (Rs.)")
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Latest close", f"Rs. {hist['close'].iloc[-1]:,.2f}" if len(hist) else "n/a")
        if len(hist) > 20:
            ret_20d = hist["close"].iloc[-1] / hist["close"].iloc[-21] - 1
            col2.metric("20-day return", f"{ret_20d:.1%}")
        col3.metric("Trading days on record", len(hist))

# ---------------------------------------------------------------- Event Study
elif page == "Event Study":
    st.title("Dividend Event Study")
    study = data["event_study"]

    if study.empty:
        st.warning("Event study data not found. Run `python -m src.features.event_study` first.")
    else:
        st.caption(
            "Cumulative Abnormal Return (CAR) = stock return − ASPI return, summed "
            "over a ±5 trading-day window around the dividend ex-date. Simplified "
            "market-adjusted model (assumes beta=1); a handful of implausible daily "
            "returns (>50%, likely data errors in the raw source) are filtered out. "
            "See About / Methodology."
        )
        col1, col2, col3 = st.columns(3)
        col1.metric("Events analyzed", len(study))
        col2.metric("Median CAR", f"{study['car'].median():.1%}")
        col3.metric("Share with positive CAR", f"{(study['car'] > 0).mean():.1%}")

        fig = px.histogram(study, x="car", nbins=60, title="Distribution of CAR around ex-dividend dates")
        fig.update_layout(height=400, xaxis_title="Cumulative Abnormal Return")
        st.plotly_chart(fig, use_container_width=True)

        ticker_filter = st.selectbox("Filter by ticker (optional)",
                                      ["All"] + sorted(study["ticker"].unique().tolist()))
        table = study if ticker_filter == "All" else study[study["ticker"] == ticker_filter]
        st.dataframe(table.sort_values("ex_date", ascending=False), use_container_width=True)

# ---------------------------------------------------------------- About
else:
    st.title("About / Methodology")
    st.markdown("""
This is a **practice project** built to develop hands-on understanding of
Colombo Stock Exchange (CSE) statistics data before starting a separate,
unrelated final-year research project (firm-level financial distress
prediction). It intentionally focuses on **market-level time series and
event analysis** rather than company-level classification.

### Scope decisions (documented, not hidden)
- **Daily price data**: 2021-2025 only. CSE's historical price archives use
  two other, structurally incompatible formats before 2021 (per-company
  header blocks for 2011-2020; a minimal 3-column format for 1991-2000).
  Parsing all three eras generically was judged out of scope for a practice
  project and is noted as a future extension.
- **Sector taxonomy**: CSE changed its sector classification scheme around
  2016 (old ~21-category scheme → GICS-aligned scheme). Sector-rotation
  analysis here is restricted to 2021-2025 to stay within one consistent
  taxonomy; old and new sector labels are deliberately **not** cross-mapped.
- **No per-company sector master file exists** in this dataset — CSE's
  "sector" files are already sector-level aggregates. Sector rotation
  therefore runs at the sector-index level, not via a company→sector join.
- **Regime detection**: KMeans (k=4) on rolling return/volatility/drawdown
  features, with clusters labeled by rule based on their centroid
  statistics — not a Hidden Markov Model. Sanity-checked against known
  events: COVID-19 market closure, the 2022 sovereign default, and the 2022
  political crisis all correctly land in the detected "Crisis / Sell-off"
  regime.
- **Event study**: simplified market-adjusted model (beta = 1), not a full
  market model with estimated beta. Daily returns beyond ±50% are treated
  as data errors and excluded (one dividend event initially showed a
  98,500% CAR, traced to a single implausible day's return in the raw
  source file).

### Known data-quality issues found and handled
- Header rows are inconsistently positioned across files and years —
  handled with a reusable header-detection utility.
- A literal string `"Market Closed Due To COVID -19"` appears in place of a
  numeric value in the foreign activity file — coerced to NaN.
- Some tickers trade multiple share classes (ordinary/non-voting) under the
  same company code, causing duplicate (ticker, date) rows — resolved by
  restricting to ordinary (N) shares for per-ticker analysis.
- Sector names have decades of spelling/abbreviation drift ("Bank Finance
  Ins" vs "Banks, Finance & Insurance") — merged where safe; genuine
  taxonomy changes were not merged.

### Suggested next steps (not built here)
- Hidden Markov Model regime detection as a comparison to the KMeans approach
- Market-model event study with estimated per-stock beta
- Historical price ingestion for 2011-2020 and 1991-2000 (different formats)
    """)
