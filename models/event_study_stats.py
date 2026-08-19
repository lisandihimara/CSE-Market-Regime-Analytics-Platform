"""
Statistical testing on the dividend event study's cumulative abnormal
returns (CAR).

src/features/event_study.py builds the per-event CAR table (that's data
construction: pulling prices, computing abnormal returns, filtering bad
days). This module is the modeling/inference layer on top of it: is the
average CAR actually different from zero, or is the small positive/
negative mean we see just noise given the spread of the sample?

Test used: one-sample t-test on the CAR distribution against a null
hypothesis of mean CAR = 0 (the standard test in the MacKinlay 1997
event-study framework). Implemented directly with numpy/scipy rather
than assuming CAR is normally distributed at the individual-event level
-- with ~1,000 events the t-test's normality assumption is on the
sample mean (CLT), not on individual events, which holds reasonably
well here despite the fat-tailed per-event CAR distribution documented
in event_study.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


@dataclass
class CARTestResult:
    n_events: int
    mean_car: float
    std_car: float
    t_stat: float
    p_value: float
    significant_at_5pct: bool


def test_car_significance(car: pd.Series) -> CARTestResult:
    """One-sample t-test of H0: mean CAR = 0 against a two-sided
    alternative."""
    car = car.dropna()
    n = len(car)
    if n < 2:
        raise ValueError("need at least 2 events to run a t-test")

    t_stat, p_value = stats.ttest_1samp(car, popmean=0.0)
    return CARTestResult(
        n_events=n,
        mean_car=float(car.mean()),
        std_car=float(car.std(ddof=1)),
        t_stat=float(t_stat),
        p_value=float(p_value),
        significant_at_5pct=bool(p_value < 0.05),
    )


def test_car_by_sign(df: pd.DataFrame) -> pd.DataFrame:
    """Split events by whether the dividend rate rose or fell vs. the
    sample median, and test each group's mean CAR separately -- a quick
    way to check whether the market reacts differently to larger vs.
    smaller dividend payouts."""
    if "dividend_rate" not in df.columns:
        raise ValueError("expected a 'dividend_rate' column")

    median_rate = df["dividend_rate"].median()
    groups = {
        "below_median_dividend": df[df["dividend_rate"] < median_rate]["car"],
        "above_median_dividend": df[df["dividend_rate"] >= median_rate]["car"],
    }

    rows = []
    for label, car in groups.items():
        result = test_car_significance(car)
        rows.append({"group": label, **vars(result)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    path = PROCESSED_DIR / "event_study_dividends.parquet"
    if not path.exists():
        raise SystemExit(
            f"{path} not found -- run `python -m src.features.event_study` first"
        )

    study = pd.read_parquet(path)

    overall = test_car_significance(study["car"])
    print("--- Overall CAR significance (H0: mean CAR = 0) ---")
    print(f"n = {overall.n_events}, mean CAR = {overall.mean_car:.4%}, "
          f"t = {overall.t_stat:.3f}, p = {overall.p_value:.4f}")
    print("Significant at 5%:", overall.significant_at_5pct)

    print("\n--- By dividend size (above vs. below median rate) ---")
    by_size = test_car_by_sign(study)
    print(by_size[["group", "n_events", "mean_car", "t_stat", "p_value", "significant_at_5pct"]]
          .to_string(index=False))
