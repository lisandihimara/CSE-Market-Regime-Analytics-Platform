"""
Detect market regimes in the ASPI time series.

Approach: KMeans clustering (k=4) on standardized rolling
return/volatility/drawdown features, chosen over a Hidden Markov Model
for this practice project because it's more transparent to interpret
and validate against known historical events -- HMM regime-switching
is noted as a natural extension in the README rather than built here,
to keep the modeling honest about what was actually validated.

Clusters are then LABELED (not just numbered) by inspecting each
cluster's mean return/volatility, so "regime 2" becomes something like
"Crisis / High Volatility" -- this labeling step is manual/rule-based,
not learned, and is the main subjective judgment call in this module.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.features.regime_features import build_regime_features

INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

FEATURE_COLS = ["roll_return_20d", "roll_vol_20d", "roll_vol_60d", "drawdown"]

# Known Sri Lankan market events used only to SANITY-CHECK the detected
# regimes against reality post-hoc — not fed into the clustering itself.
KNOWN_EVENTS = {
    "2019-04-21": "Easter Sunday attacks",
    "2020-03-20": "COVID-19 market closure begins",
    "2022-04-12": "Sri Lanka sovereign default declared",
    "2022-07-09": "Presidential crisis / political upheaval",
}


def label_cluster(mean_return: float, mean_vol: float, overall_vol_median: float) -> str:
    """Rule-based translation from cluster centroid stats to a human label."""
    high_vol = mean_vol > overall_vol_median
    if high_vol and mean_return < 0:
        return "Crisis / Sell-off"
    if high_vol and mean_return >= 0:
        return "Volatile Recovery"
    if not high_vol and mean_return >= 0:
        return "Bull / Stable Growth"
    return "Bear / Quiet Decline"


def detect_regimes(n_clusters: int = 4, random_state: int = 42) -> pd.DataFrame:
    df = build_regime_features()
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)

    X = df[FEATURE_COLS].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    df["cluster"] = km.fit_predict(X_scaled)

    overall_vol_median = df["roll_vol_20d"].median()
    cluster_stats = df.groupby("cluster")[["roll_return_20d", "roll_vol_20d"]].mean()
    cluster_labels = {
        c: label_cluster(row["roll_return_20d"], row["roll_vol_20d"], overall_vol_median)
        for c, row in cluster_stats.iterrows()
    }
    df["regime"] = df["cluster"].map(cluster_labels)

    return df


def summarize_regimes(df: pd.DataFrame) -> pd.DataFrame:
    summary = df.groupby("regime").agg(
        n_days=("date", "count"),
        avg_20d_return=("roll_return_20d", "mean"),
        avg_ann_vol=("roll_vol_20d", "mean"),
        avg_drawdown=("drawdown", "mean"),
    ).sort_values("avg_ann_vol")
    return summary


if __name__ == "__main__":
    regimes = detect_regimes()
    print(regimes[["date", "close", "regime"]].tail(15))

    print("\n--- Regime summary ---")
    print(summarize_regimes(regimes))

    print("\n--- Sanity check against known events ---")
    for date_str, event in KNOWN_EVENTS.items():
        window = regimes[
            (regimes["date"] >= pd.Timestamp(date_str) - pd.Timedelta(days=5)) &
            (regimes["date"] <= pd.Timestamp(date_str) + pd.Timedelta(days=15))
        ]
        if len(window):
            regime_at_event = window["regime"].mode().iloc[0] if len(window["regime"].mode()) else "n/a"
            print(f"{date_str} ({event}): detected regime = {regime_at_event}")
        else:
            print(f"{date_str} ({event}): no data in window")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    regimes.to_parquet(PROCESSED_DIR / "regime_timeline.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    regimes.to_csv(PROCESSED_DIR / "regime_timeline.csv", index=False)
    print("\nsaved to", PROCESSED_DIR / "regime_timeline.parquet")
