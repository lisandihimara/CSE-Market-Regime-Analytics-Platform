"""
Reusable sanity checks run after each ingestion load step.

These are deliberately lightweight, generic assertions (no duplicate
keys, no nulls in required columns, no dates in the future, etc.) --
the kind of check every loader in src/ingestion needs in some form.
Before this module existed, each loader's __main__ block re-implemented
a version of these checks inline (see git history / README data-quality
notes for the bugs some of these were written to catch, e.g. the
2010-06-30 duplicate ASPI row and the sector-total-leaked-as-sector
issue). Centralizing them here means a fix or a new check benefits
every loader at once, and a loader's __main__ block reads as "load,
validate, report" rather than repeating boilerplate.

These are intentionally NOT pytest tests: they run as part of normal
pipeline execution (`python -m src.ingestion.load_x`) and raise
immediately on bad data, so a broken loader fails loudly at the source
rather than silently producing bad interim/processed files that only
get caught later by tests/test_pipeline.py.
"""
from __future__ import annotations

import pandas as pd


class ValidationError(AssertionError):
    """Raised when a loaded DataFrame fails a pipeline sanity check."""


def assert_not_empty(df: pd.DataFrame, name: str) -> None:
    if len(df) == 0:
        raise ValidationError(f"[{name}] loaded 0 rows -- check the raw source file/path")


def assert_no_nulls(df: pd.DataFrame, columns: list[str], name: str) -> None:
    for col in columns:
        n_null = df[col].isna().sum()
        if n_null:
            raise ValidationError(
                f"[{name}] column '{col}' has {n_null} null value(s) "
                f"but is required to be fully populated"
            )


def assert_no_duplicates(df: pd.DataFrame, subset: list[str], name: str) -> None:
    n_dupe = df.duplicated(subset=subset).sum()
    if n_dupe:
        raise ValidationError(
            f"[{name}] found {n_dupe} duplicate row(s) on key {subset} -- "
            f"expected one row per {', '.join(subset)}"
        )


def assert_no_future_dates(df: pd.DataFrame, date_col: str, name: str) -> None:
    today = pd.Timestamp.today().normalize()
    n_future = (df[date_col] > today).sum()
    if n_future:
        raise ValidationError(
            f"[{name}] found {n_future} row(s) with '{date_col}' after today "
            f"({today.date()}) -- likely a date-parsing bug"
        )


def assert_date_range(
    df: pd.DataFrame,
    date_col: str,
    name: str,
    min_date: str | None = None,
    max_date: str | None = None,
) -> None:
    if min_date is not None and df[date_col].min() < pd.Timestamp(min_date):
        raise ValidationError(
            f"[{name}] earliest '{date_col}' ({df[date_col].min().date()}) is "
            f"before expected minimum {min_date}"
        )
    if max_date is not None and df[date_col].max() > pd.Timestamp(max_date):
        raise ValidationError(
            f"[{name}] latest '{date_col}' ({df[date_col].max().date()}) is "
            f"after expected maximum {max_date}"
        )


def assert_values_not_in(df: pd.DataFrame, column: str, forbidden: set, name: str) -> None:
    """Guard against known bad labels leaking into a categorical column
    (e.g. index totals like 'ASPI'/'MPI' leaking into a sector column)."""
    leaked = set(df[column].unique()) & forbidden
    if leaked:
        raise ValidationError(f"[{name}] forbidden values leaked into '{column}': {leaked}")


def report(df: pd.DataFrame, name: str, date_col: str | None = None) -> None:
    """Print a one-line load summary. Call this at the end of a loader's
    __main__ block once validation has passed, so every loader prints in
    a consistent format."""
    msg = f"[{name}] OK -- {len(df):,} rows"
    if date_col is not None and date_col in df.columns and len(df):
        msg += f", {date_col} range {df[date_col].min().date()} -> {df[date_col].max().date()}"
    print(msg)
