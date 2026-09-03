"""Quick data explorer for processed datasets."""
from pathlib import Path
import pandas as pd
import numpy as np

PROCESSED = Path(__file__).resolve().parent / "data" / "processed"

# Data files to examine
files = {
    "daily_prices_2021_2025": "Daily stock prices",
    "foreign_activity": "Foreign investor flows",
    "market_indices_daily": "Market indices (ASPI)",
    "regime_features": "Market regime features",
    "sector_market_cap": "Sector market capitalization",
    "securities_master": "Securities master reference",
}

print("=" * 80)
print("PROCESSED DATA EXPLORER")
print("=" * 80)

for fname, description in files.items():
    csv_path = PROCESSED / f"{fname}.csv"
    if not csv_path.exists():
        print(f"\n❌ {description}: NOT FOUND")
        continue
    
    print(f"\n{'=' * 80}")
    print(f"📊 {description.upper()}")
    print(f"File: {fname}.csv")
    print("=" * 80)
    
    df = pd.read_csv(csv_path)
    
    # Basic info
    print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"Memory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    # Date range if available
    date_cols = [col for col in df.columns if 'date' in col.lower()]
    if date_cols:
        for date_col in date_cols:
            try:
                dates = pd.to_datetime(df[date_col])
                print(f"Date range ({date_col}): {dates.min().date()} to {dates.max().date()}")
            except:
                pass
    
    # Columns
    print(f"\nColumns ({df.shape[1]}):")
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null = df[col].notna().sum()
        nulls = df[col].isna().sum()
        print(f"  • {col:30s} {dtype:12s} ({non_null:6,} non-null, {nulls:6,} null)")
    
    # Sample data
    print(f"\nFirst 3 rows:")
    print(df.head(3).to_string())
    
    # Statistics for numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        print(f"\nNumeric summary:")
        print(df[numeric_cols].describe().to_string())

print("\n" + "=" * 80)
print("END OF DATA EXPLORATION")
print("=" * 80)
