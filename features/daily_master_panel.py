"""
Builds a single "daily master panel": one row per trading day, combining
the regime timeline (ASPI price/returns/volatility/regime) with foreign
investor net flow.

This is deliberately a *different* kind of output from
regime_timeline.parquet / sector_rotation_merged.parquet /
event_study_dividends.parquet. Those three are each the correct,
single, analysis-ready table *for their own topic* (regime detection,
sector rotation, the dividend event study respectively) -- but none of
them puts regime, price behavior, and foreign flow side by side on a
shared daily axis, which is what you need to explore *cross-signal*
questions ("does foreign selling tend to happen before or during a
Crisis regime?") rather than within-topic ones.

IMPORTANT GRAIN CAVEAT (read this before analyzing the output):
foreign_activity.parquet is MONTHLY data. To put it on a daily axis,
each month's single foreign-flow value is broadcast (repeated) across
every trading day in that month. This means:
  - the foreign_net_flow_monthly column is NOT a daily observation --
    it's the same number repeated ~21 times per month
  - treating each day's repeated value as an independent daily
    observation in a correlation/statistical test would be a real
    statistical error (pseudo-replication: it silently inflates your
    apparent sample size and can make a weak relationship look
    artificially significant)
  - notebooks/05_cross_signal_eda.ipynb demonstrates this pitfall
    directly and shows the corrected monthly-grain approach alongside
    the naive daily one, rather than only warning about it in prose
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"


def build_daily_master_panel(
    regime_timeline: pd.DataFrame | None = None,
    foreign_activity: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if regime_timeline is None:
        regime_timeline = pd.read_parquet(PROCESSED_DIR / "regime_timeline.parquet")
    if foreign_activity is None:
        foreign_activity = pd.read_parquet(INTERIM_DIR / "foreign_activity.parquet")

    panel = regime_timeline[
        ["date", "close", "daily_return", "roll_return_20d",
         "roll_vol_20d", "roll_vol_60d", "drawdown", "regime"]
    ].copy()
    panel = panel.sort_values("date").reset_index(drop=True)

    # "net" / "Total Foreign" is the single monthly net foreign flow
    # figure (foreign purchases minus foreign sales, all foreign
    # investor types combined) -- the cleanest single column for a
    # "was foreign money net buying or selling this month" signal.
    foreign_net = foreign_activity[
        (foreign_activity["transaction_type"] == "net")
        & (foreign_activity["investor_type"] == "Total Foreign")
    ][["date", "value"]].rename(columns={"value": "foreign_net_flow_monthly"})

    panel["year_month"] = panel["date"].values.astype("datetime64[M]")
    foreign_net["year_month"] = foreign_net["date"].values.astype("datetime64[M]")

    panel = panel.merge(
        foreign_net[["year_month", "foreign_net_flow_monthly"]],
        on="year_month", how="left",
    )
    panel = panel.drop(columns="year_month")

    return panel


if __name__ == "__main__":
    from src.utils.validation import assert_not_empty, assert_no_nulls, assert_no_duplicates, report

    panel = build_daily_master_panel()

    assert_not_empty(panel, "daily_master_panel")
    assert_no_nulls(panel, ["date", "close", "regime"], "daily_master_panel")
    assert_no_duplicates(panel, ["date"], "daily_master_panel")

    coverage = panel["foreign_net_flow_monthly"].notna().mean()
    print(f"foreign_net_flow_monthly populated for {coverage:.1%} of days "
          f"(gaps are months with no matching foreign-activity data)")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PROCESSED_DIR / "daily_master_panel.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    panel.to_csv(PROCESSED_DIR / "daily_master_panel.csv", index=False)
    report(panel, "daily_master_panel", date_col="date")
