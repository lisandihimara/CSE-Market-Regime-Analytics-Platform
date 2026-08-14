"""
Event study: measure abnormal stock returns around dividend ex-dates.

Method (market model, simplified single-factor):
  1. For each event, take a window of trading days around the ex-date.
  2. Compute the stock's raw return each day in the window.
  3. Compute the ASPI's raw return each day in the window (the market
     benchmark).
  4. Abnormal return (AR) = stock return - market return.
  5. Cumulative abnormal return (CAR) = sum of AR over the window.

This is the standard event-study framework (MacKinlay 1997), simplified
by using a 1:1 market-adjusted model (beta=1) rather than estimating
each stock's beta from a pre-event estimation window -- a reasonable
simplification for a practice project, documented here rather than
silently assumed. A market-model version with estimated beta is a
natural next step, noted in the README.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.load_corporate_actions import load_dividends

INTERIM_DIR = Path(__file__).resolve().parents[2] / "data" / "interim"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

WINDOW_BEFORE = 5   # trading days before ex-date
WINDOW_AFTER = 5    # trading days after ex-date

# CSE's raw price files occasionally contain implausible single-day
# jumps (verified: one dividend event produced a 98,500% CAR, traced to
# a single day's return of >900x — almost certainly an unadjusted stock
# split or a data entry error in the source file, not a real trading
# day). Daily returns beyond this bound are treated as data errors and
# excluded from the event window rather than silently averaged in.
MAX_PLAUSIBLE_DAILY_RETURN = 0.50  # 50%


def _load_prices_and_market() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = pd.read_parquet(INTERIM_DIR / "daily_prices_2021_2025.parquet")
    # Some tickers trade multiple share classes under the same COMPANY ID
    # (e.g. "AAF" has both ordinary/voting [N] and non-voting [P] shares),
    # which caused duplicate (ticker, date) rows and collided in the
    # event-study lookup below. Restricting to main_type == "N" (ordinary
    # shares, ~93% of all rows) resolves this cleanly and matches what
    # "the stock price" conventionally refers to; documented here rather
    # than silently deduping and picking an arbitrary row.
    prices = prices[prices["main_type"] == "N"]
    prices = prices[["ticker", "date", "close"]].dropna().sort_values(["ticker", "date"])
    prices = prices.drop_duplicates(subset=["ticker", "date"])
    prices["stock_return"] = prices.groupby("ticker")["close"].pct_change()

    market = pd.read_parquet(INTERIM_DIR / "market_indices_daily.parquet")
    market = market[market["index_name"] == "All Share Price Index"][["date", "value"]]
    market = market.drop_duplicates(subset=["date"]).sort_values("date")
    market = market.rename(columns={"value": "aspi_close"})
    market["market_return"] = market["aspi_close"].pct_change()

    return prices, market


def run_event_study(max_events: int | None = None) -> pd.DataFrame:
    prices, market = _load_prices_and_market()
    trading_days = sorted(prices["date"].unique())
    day_index = {d: i for i, d in enumerate(trading_days)}

    dividends = load_dividends()
    dividends = dividends[dividends["ticker"].isin(prices["ticker"].unique())]
    if max_events:
        dividends = dividends.head(max_events)

    price_lookup = prices.set_index(["ticker", "date"])["stock_return"]
    market_lookup = market.set_index("date")["market_return"]

    results = []
    for _, ev in dividends.iterrows():
        ex_date = ev["date_ex"]
        ticker = ev["ticker"]

        # find nearest trading day at/after ex_date
        candidates = [d for d in trading_days if d >= ex_date]
        if not candidates:
            continue
        anchor = candidates[0]
        anchor_idx = day_index[anchor]

        window_days = trading_days[
            max(0, anchor_idx - WINDOW_BEFORE): anchor_idx + WINDOW_AFTER + 1
        ]

        car = 0.0
        n_valid = 0
        for offset, day in enumerate(window_days, start=-WINDOW_BEFORE):
            try:
                stock_ret = price_lookup.loc[(ticker, day)]
                mkt_ret = market_lookup.loc[day]
            except KeyError:
                continue
            if pd.isna(stock_ret) or pd.isna(mkt_ret):
                continue
            if abs(stock_ret) > MAX_PLAUSIBLE_DAILY_RETURN:
                continue  # likely data error, not a real price move
            ar = stock_ret - mkt_ret
            car += ar
            n_valid += 1

        if n_valid == 0:
            continue

        results.append({
            "ticker": ticker,
            "ex_date": ex_date,
            "dividend_rate": ev.get("dividend_rate"),
            "car": car,
            "n_valid_days": n_valid,
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    study = run_event_study()
    print(study.shape)
    print("\nMean CAR around dividend ex-dates:", study["car"].mean())
    print("Median CAR (more robust to outliers):", study["car"].median())
    print("Share of events with positive CAR:", (study["car"] > 0).mean())
    extreme = study[study["car"].abs() > 1.0]
    print(f"\nEvents with |CAR| > 100% after filtering (worth manual review): {len(extreme)}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    study.to_parquet(PROCESSED_DIR / "event_study_dividends.parquet", index=False)
    # CSV alongside parquet: parquet is what the rest of the pipeline reads
    # (preserves dtypes, faster); CSV is here purely so the table can be
    # opened directly in Excel/Sheets for a quick manual look.
    study.to_csv(PROCESSED_DIR / "event_study_dividends.csv", index=False)
    print("\nsaved to", PROCESSED_DIR / "event_study_dividends.parquet")
