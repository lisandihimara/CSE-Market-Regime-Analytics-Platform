"""
Build the feature set used for market regime detection.

Uses the ASPI (All Share Price Index) daily series as the primary
signal. Rolling windows are chosen to capture both short-term shocks
(20 trading days ~ 1 month) and medium-term trend (60 trading days
~ 1 quarter), which is a standard choice in regime-detection literature
(e.g. Ang & Bekaert style Markov-switching return/volatility models).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np

from src.ingestion.load_indices import load_market_indices_daily  # src.ingestion exists

INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"


def build_regime_features(index_name: str = "All Share Price Index") -> pd.DataFrame:
    idx_path = INTERIM_DIR / "market_indices_daily.parquet"
    if idx_path.exists():
        idx = pd.read_parquet(idx_path)
    else:
        idx = load_market_indices_daily()

    series = idx[idx["index_name"] == index_name].copy()
    series = series.sort_values("date").drop_duplicates(subset="date")
    series = series.set_index("date")["value"].rename("close")

    df = series.to_frame()
    df["daily_return"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))

    df["roll_return_20d"] = df["close"].pct_change(20)
    df["roll_vol_20d"] = df["daily_return"].rolling(20).std() * np.sqrt(252)
    df["roll_vol_60d"] = df["daily_return"].rolling(60).std() * np.sqrt(252)
    df["roll_return_60d"] = df["close"].pct_change(60)

    # drawdown from trailing 252-day (≈1yr) peak — useful regime signal,
    # separates "high vol recovery" from "high vol crash"
    trailing_peak = df["close"].rolling(252, min_periods=20).max()
    df["drawdown"] = df["close"] / trailing_peak - 1

    df = df.dropna(subset=["roll_return_20d", "roll_vol_20d"])
    df = df.reset_index()
    return df


if __name__ == "__main__":
    feats = build_regime_features()
    print(feats.shape)
    print(feats.tail())
    feats.to_parquet(INTERIM_DIR / "regime_features.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    feats.to_csv(INTERIM_DIR / "regime_features.csv", index=False)
    print("saved to", INTERIM_DIR / "regime_features.parquet")
