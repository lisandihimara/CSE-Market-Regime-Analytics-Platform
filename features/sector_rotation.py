"""
Sector rotation analysis: which sectors outperform in each market regime.

Joins the regime timeline (daily) to sector market cap (monthly) by
mapping each month to its most common regime that month, then computes
each sector's month-over-month % change in market cap and ranks
average performance within each regime.

Scope note: only 2021-2025 is used here, both because that's where the
regime timeline is most reliable (see regime_detection.py) and because
using the full 2005-2025 sector history would mix the pre/post-2016
sector taxonomy change documented in load_sector_data.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.load_sector_data import load_sector_market_cap

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"

ANALYSIS_START = "2021-01-01"
ANALYSIS_END = "2025-12-31"


def _monthly_regime(regime_timeline: pd.DataFrame) -> pd.DataFrame:
    df = regime_timeline.copy()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    monthly = df.groupby("month")["regime"].agg(lambda s: s.mode().iloc[0]).reset_index()
    return monthly


def build_sector_rotation(regime_timeline: pd.DataFrame) -> pd.DataFrame:
    sector_path = INTERIM_DIR / "sector_market_cap.parquet"
    sectors = pd.read_parquet(sector_path) if sector_path.exists() else load_sector_market_cap()

    sectors = sectors[
        (sectors["date"] >= ANALYSIS_START) & (sectors["date"] <= ANALYSIS_END)
    ].copy()

    sectors = sectors.sort_values(["sector", "date"])
    sectors["mom_return"] = sectors.groupby("sector")["market_cap"].pct_change()

    monthly_regime = _monthly_regime(regime_timeline)
    merged = sectors.merge(monthly_regime, left_on="date", right_on="month", how="inner")
    merged = merged.dropna(subset=["mom_return"])

    return merged


def rank_sector_performance(merged: pd.DataFrame) -> pd.DataFrame:
    ranking = merged.groupby(["regime", "sector"])["mom_return"].agg(
        avg_monthly_return="mean", n_months="count"
    ).reset_index()
    ranking = ranking[ranking["n_months"] >= 3]  # drop thin samples
    ranking = ranking.sort_values(["regime", "avg_monthly_return"], ascending=[True, False])
    return ranking


if __name__ == "__main__":
    regime_timeline = pd.read_parquet(PROCESSED_DIR / "regime_timeline.parquet")
    merged = build_sector_rotation(regime_timeline)
    ranking = rank_sector_performance(merged)

    for regime in ranking["regime"].unique():
        print(f"\n=== Top 5 sectors during '{regime}' ===")
        print(ranking[ranking["regime"] == regime].head(5).to_string(index=False))

    merged.to_parquet(PROCESSED_DIR / "sector_rotation_merged.parquet", index=False)

    # CSV alongside parquet: parquet is what the rest of the pipeline reads

    # (preserves dtypes, faster); CSV is here purely so the table can be

    # opened directly in Excel/Sheets for a quick manual look.

    merged.to_csv(PROCESSED_DIR / "sector_rotation_merged.csv", index=False)
    ranking.to_parquet(PROCESSED_DIR / "sector_rotation_ranking.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    ranking.to_csv(PROCESSED_DIR / "sector_rotation_ranking.csv", index=False)
    print("\nsaved sector rotation outputs")
