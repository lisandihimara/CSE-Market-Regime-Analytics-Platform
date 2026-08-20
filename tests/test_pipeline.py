"""
Basic sanity tests for the ingestion and feature pipelines.

These are lightweight smoke tests — they check shape, dtype, and
known invariants (no future dates, no duplicate keys, known crisis
events land in the expected regime) rather than exact values, since
exact values will shift if CSE revises historical data.

Run with: pytest tests/
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"


def _skip_if_missing(path: Path):
    if not path.exists():
        pytest.skip(f"{path} not built yet — run the relevant pipeline step first")


class TestDailyPrices:
    def test_shape_and_types(self):
        path = INTERIM / "daily_prices_2021_2025.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        assert len(df) > 0
        assert df["date"].min() >= pd.Timestamp("2021-01-01")
        assert df["date"].max() <= pd.Timestamp("2026-01-01")
        assert df["ticker"].notna().all()

    def test_no_future_dates(self):
        path = INTERIM / "daily_prices_2021_2025.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        assert (df["date"] <= pd.Timestamp.today()).all()


class TestMarketIndices:
    def test_aspi_present(self):
        path = INTERIM / "market_indices_daily.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        assert "All Share Price Index" in df["index_name"].unique()

    def test_no_duplicate_index_date_pairs(self):
        path = INTERIM / "market_indices_daily.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        aspi = df[df["index_name"] == "All Share Price Index"]
        assert not aspi.duplicated(subset="date").any()


class TestSectorMarketCap:
    def test_no_index_totals_leaked_as_sectors(self):
        path = INTERIM / "sector_market_cap.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        leaked = {"Aspi", "Aspi Mkt Cap", "Mpi", "S&P", "S&P Mkt Cap"}
        assert not set(df["sector"].unique()) & leaked


class TestRegimeDetection:
    def test_known_crisis_events_detected(self):
        path = PROCESSED / "regime_timeline.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)

        known_crises = ["2020-03-20", "2022-04-12", "2022-07-09"]
        for date_str in known_crises:
            window = df[
                (df["date"] >= pd.Timestamp(date_str) - pd.Timedelta(days=5)) &
                (df["date"] <= pd.Timestamp(date_str) + pd.Timedelta(days=15))
            ]
            if window.empty:
                continue
            assert "Crisis" in window["regime"].mode().iloc[0], (
                f"Expected a Crisis-labeled regime around {date_str}"
            )


class TestEventStudy:
    def test_no_extreme_outliers_remain(self):
        path = PROCESSED / "event_study_dividends.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        # after the >50% daily-return filter, CAR should stay in a
        # plausible range for a ±5-day window
        assert df["car"].abs().max() < 2.0


class TestDailyMasterPanel:
    def test_shape_and_no_duplicate_dates(self):
        path = PROCESSED / "daily_master_panel.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        assert len(df) > 0
        assert not df["date"].duplicated().any()
        assert df["close"].notna().all()
        assert df["regime"].notna().all()

    def test_foreign_flow_is_step_shaped_within_a_month(self):
        # regression guard for the monthly-broadcast join: every day in
        # the same calendar month must carry the *same*
        # foreign_net_flow_monthly value (that's the whole point of the
        # caveat documented in daily_master_panel.py -- if this ever
        # varied within a month, the join logic would be broken)
        path = PROCESSED / "daily_master_panel.parquet"
        _skip_if_missing(path)
        df = pd.read_parquet(path)
        df = df.dropna(subset=["foreign_net_flow_monthly"])
        month_key = df["date"].values.astype("datetime64[M]")
        n_distinct_per_month = (
            df.assign(_month=month_key)
            .groupby("_month")["foreign_net_flow_monthly"]
            .nunique()
        )
        assert (n_distinct_per_month == 1).all()
