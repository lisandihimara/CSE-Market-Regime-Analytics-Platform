"""
Shared wide-to-long ("tidy") reshaping helpers used across the ingestion
loaders.

Several CSE source files (Market Indices - Daily, Sector Market
Capitalisation, Foreign Activity - Monthly) all share the same basic
shape once parsed: dates or months as columns, a categorical dimension
(index name / sector / investor type) as rows, and a numeric value in
each cell. Every loader for that shape needs the same two steps --
coerce each value column to numeric (treating any non-numeric CSE
placeholder, e.g. "Market Closed Due To COVID -19", as missing) and
melt from wide to long -- so that logic lives here once instead of
being re-implemented per loader.

Loaders with a genuinely different raw layout (e.g.
load_foreign_activity.py's fixed section-header row map) don't fit this
generic shape and are intentionally left doing their own thing rather
than being forced through a shared function that doesn't match their
structure -- see that loader's docstring.
"""
from __future__ import annotations

import pandas as pd


def coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce the given columns to numeric, turning any non-numeric cell
    (typos, placeholder strings like 'Market Closed Due To COVID -19',
    blank cells) into NaN rather than raising or silently keeping a
    mixed-type column."""
    df = df.copy()
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def melt_wide_to_long(
    df: pd.DataFrame,
    id_vars: str | list[str],
    value_vars: list[str],
    var_name: str,
    value_name: str,
    drop_na_value: bool = True,
    dedupe_subset: list[str] | None = None,
) -> pd.DataFrame:
    """Melt a wide (id columns + many value columns) table into long
    (one row per id/category/value) format, with the missing-value and
    duplicate-row handling every wide-format CSE loader needs:

    - drops rows where the value is NaN after melting (a wide table
      with mostly-empty cells would otherwise produce a mostly-empty
      long table)
    - optionally drops duplicate (id, category) rows, since more than
      one CSE source file has been found to contain an exact duplicate
      row for the same key (see README data-quality notes)
    """
    long_df = df.melt(id_vars=id_vars, value_vars=value_vars,
                       var_name=var_name, value_name=value_name)
    if drop_na_value:
        long_df = long_df.dropna(subset=[value_name])
    if dedupe_subset:
        long_df = long_df.drop_duplicates(subset=dedupe_subset)
    return long_df.reset_index(drop=True)
